#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
并行LLM文档理解节点
将文档按接口拆分成多个片段，并行调用LLM加速处理
"""

import json
import os
import asyncio
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple
from models.state import AgentState
from utils.logger import logger
from deepseek_client_simple import call_deepseek_llm


# 系统提示词 - 用于单个接口解析
INTERFACE_SYSTEM_PROMPT = """你是一个智能接口解析器，专门解析产品设计文档中的单个功能块，生成接口语义模型。

你需要解析的内容是Markdown格式的grid块，格式如下：
```grid
grid_column:
  - width_ratio: 50
    content: |
        左侧内容，通常是图片/原型/示意图
  - width_ratio: 50
    content: |
        右侧内容，通常是字段列表、维度、指标
```

你的任务：
1. **优先使用上下文信息**：从上下文中提取接口的准确名称（如文档标题、章节标题等）
2. 解析这个功能块的内容
3. 识别接口类型
4. 提取字段信息
5. 生成单个接口的JSON

**重要**：接口名称应该基于上下文中的标题，而不是根据内容推测！如果上下文中有"用户管理"等标题，应该使用这个作为接口名称。

接口类型识别规则：
- **filter_dimension**: 包含筛选条件、过滤字段、查询参数的功能块
- **data_display**: 展示数据列表、明细、表格内容的功能块
- **analytics_metric**: 包含指标、统计、计算值的功能块
- **trend_analysis**: 包含时间序列、趋势图、对比分析的功能块
- **summary_dashboard**: 综合概览、汇总信息、仪表板功能块
- **export_report**: 导出、报表、下载相关的功能块
- **configuration**: 配置设置、参数管理相关的功能块
- **custom_action**: 自定义操作、特殊业务逻辑的功能块

字段处理规则：
- 忽略图片/示意图/参考口径（包含"参考口径:"的行不要输出）
- 对每个有效字段生成结构：
  - name：保留文档里的原始名字
  - expression：把 name 翻成英文占位符（公司ID→companyId，消耗→cost，天→day，CTR→ctr等）
  - data_type：维度一般是string，指标是number，时间是date，布尔值是boolean
  - required：如果判断是关键条件（如公司ID、时间），设为true，否则false

输出格式（必须是JSON）：
{
  "id": "api_功能英文名",
  "name": "功能中文名",
  "type": "接口类型",
  "dimensions": [ // 查询条件字段
    {"name": "字段名", "expression": "englishName", "data_type": "string", "required": true/false}
  ],
  "metrics": [ // 数值指标字段
    {"name": "指标名", "expression": "englishName", "data_type": "number", "required": true/false}
  ]
}

只输出JSON，不要包含其他文字。"""


def extract_grid_blocks(content: str) -> List[Tuple[str, int]]:
    """
    从文档内容中提取所有的grid块

    Returns:
        List of (grid_content, start_line_number)
    """
    grid_blocks = []
    lines = content.split('\n')
    in_grid = False
    grid_start = 0
    grid_content = []

    for i, line in enumerate(lines):
        if line.strip().startswith('```grid'):
            if not in_grid:
                in_grid = True
                grid_start = i
                grid_content = []
            grid_content.append(line)
        elif line.strip() == '```' and in_grid:
            grid_content.append(line)
            grid_blocks.append(('\n'.join(grid_content), grid_start))
            in_grid = False
        elif in_grid:
            grid_content.append(line)

    return grid_blocks


def extract_context_around_grid(content: str, grid_start: int, context_size: int = 8) -> str:
    """
    提取grid块周围的上下文（标题等）
    支持多种标题格式和文档结构
    """
    lines = content.split('\n')
    start = max(0, grid_start - context_size)
    end = min(len(lines), grid_start + context_size)

    context_lines = []
    for i in range(start, end):
        if i < grid_start:
            line = lines[i].strip()
            # 支持多种标题格式和文档结构
            if (line.startswith('#') or line.startswith('##') or line.startswith('###') or  # markdown标题
                line.endswith('：') or line.endswith(':') or  # 冒号结尾的标题
                (len(line) < 50 and line and not line.startswith('```') and not line.startswith('!'))):  # 短行标题
                context_lines.append(lines[i])
        elif i >= grid_start:
            # grid块本身会完整包含
            break

    # 如果没有找到明确的标题，尝试寻找最近的非空行
    if not context_lines:
        for i in range(start, grid_start):
            line = lines[i].strip()
            if line and not line.startswith('```') and not line.startswith('!') and len(line) < 100:
                context_lines.append(lines[i])
                break

    return '\n'.join(context_lines)


def find_grid_position_in_document(grid_content: str, full_document: str) -> int:
    """
    在完整文档中找到grid块的真正起始行号
    """
    lines = full_document.split('\n')
    grid_lines = grid_content.split('\n')

    # 寻找grid块的起始位置（查找第一个以```grid开头的行）
    for i, line in enumerate(lines):
        if line.strip().startswith('```grid'):
            # 检查接下来的几行是否匹配grid内容
            match_found = True
            for j, grid_line in enumerate(grid_lines[:1]):  # 只检查前几行以提高效率
                if i + j < len(lines) and lines[i + j].strip() != grid_line.strip():
                    match_found = False
                    break
            if match_found:
                return i
        elif len(grid_lines) > 0 and i + len(grid_lines) <= len(lines):
            # 也尝试直接内容匹配
            document_slice = lines[i:i+len(grid_lines)]
            if document_slice == grid_lines:
                return i

    # 如果找不到精确匹配，尝试简单的字符串搜索
    if grid_content in full_document:
        # 计算grid内容在文档中的起始行
        before_content = full_document.split(grid_content)[0]
        return before_content.count('\n')

    # 最后回退到返回0
    return 0


def parse_single_interface(grid_block_with_context: Tuple[str, str, int]) -> Dict[str, Any]:
    """
    解析单个grid块为接口定义

    Args:
        grid_block_with_context: (grid_content, context, block_index)

    Returns:
        接口定义字典
    """
    grid_content, context, block_index = grid_block_with_context

    try:
        # 构建用户提示词
        user_prompt = f"""请解析下面这个功能块，生成对应的接口定义。

上下文信息：
{context}

功能块内容：
{grid_content}

请根据功能块的内容智能识别接口类型，并提取字段信息。输出JSON格式。"""

        # 调用LLM
        response = call_deepseek_llm(
            system_prompt=INTERFACE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model="deepseek-chat",
            temperature=0.1,
            max_tokens=2000  # 单个接口token较少
        )

        # 解析响应
        try:
            interface_data = json.loads(response)
            # 添加元数据
            interface_data['_block_index'] = block_index
            interface_data['_grid_content'] = grid_content
            return interface_data
        except json.JSONDecodeError:
            logger.warning(f"Block {block_index} LLM响应不是合法JSON: {response[:100]}...")
            return {
                "error": "JSON解析失败",
                "_block_index": block_index,
                "_grid_content": grid_content,
                "_raw_response": response
            }

    except Exception as e:
        logger.error(f"解析Block {block_index}时发生错误: {str(e)}")
        return {
            "error": str(e),
            "_block_index": block_index,
            "_grid_content": grid_content
        }


def split_document_for_parallel_processing(content: str, max_interfaces_per_chunk: int = 3) -> List[str]:
    """
    将文档分割成适合并行处理的块
    每个块包含多个grid块，但不超过max_interfaces_per_chunk
    """
    grid_blocks = extract_grid_blocks(content)

    if not grid_blocks:
        return [content]  # 如果没有grid块，返回原始内容

    chunks = []
    current_chunk_blocks = []
    current_chunk_size = 0

    for grid_content, grid_start in grid_blocks:
        if current_chunk_size >= max_interfaces_per_chunk:
            # 当前的块已满，开始新块
            if current_chunk_blocks:
                chunk_content = '\n\n'.join(current_chunk_blocks)
                chunks.append(chunk_content)
            current_chunk_blocks = [grid_content]
            current_chunk_size = 1
        else:
            current_chunk_blocks.append(grid_content)
            current_chunk_size += 1

    # 添加最后一个块
    if current_chunk_blocks:
        chunk_content = '\n\n'.join(current_chunk_blocks)
        chunks.append(chunk_content)

    return chunks


def parse_interfaces_chunk(chunk_content: str, chunk_index: int, full_document: str = "") -> List[Dict[str, Any]]:
    """
    解析一个文档块中的所有接口
    """
    grid_blocks = extract_grid_blocks(chunk_content)

    if not grid_blocks:
        return []

    # 准备并行处理的参数
    parse_tasks = []
    for i, (grid_content, grid_start) in enumerate(grid_blocks):
        # 使用完整文档提取上下文，而不是只使用分割后的块
        if full_document:
            # 在完整文档中找到这个grid块的真正位置
            # 通过搜索grid内容在完整文档中的位置来找到真正的行号
            actual_start = find_grid_position_in_document(grid_content, full_document)
            context = extract_context_around_grid(full_document, actual_start)
        else:
            # 回退到使用块内容
            context = extract_context_around_grid(chunk_content, grid_start)
        block_index = chunk_index * 10 + i  # 确保索引唯一
        parse_tasks.append((grid_content, context, block_index))

    # 并行处理
    interfaces = []
    with ThreadPoolExecutor(max_workers=min(3, len(parse_tasks))) as executor:
        future_to_interface = {
            executor.submit(parse_single_interface, task): task
            for task in parse_tasks
        }

        for future in as_completed(future_to_interface):
            try:
                interface_result = future.result(timeout=60)  # 60秒超时
                interfaces.append(interface_result)
            except Exception as e:
                task = future_to_interface[future]
                logger.error(f"并行处理接口时发生错误: {str(e)}, task: {task[2]}")
                interfaces.append({
                    "error": str(e),
                    "_block_index": task[2],
                    "_grid_content": task[0]
                })

    return interfaces


def merge_interfaces_to_ism(interfaces: List[Dict[str, Any]], doc_meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    将多个接口定义合并为完整的ISM结构
    """
    ism = {
        "doc_meta": doc_meta,
        "interfaces": [],
        "__pending__": []
    }

    # 成功解析的接口
    successful_interfaces = []

    # 失败和待处理的项
    pending_items = []

    for interface in interfaces:
        if "error" in interface:
            # 处理失败的接口
            pending_items.append(f"接口解析失败 (Block {interface.get('_block_index', 'unknown')}): {interface['error']}")
            if '_grid_content' in interface:
                pending_items.append(f"原始内容: {interface['_grid_content'][:200]}...")
        elif not interface.get("id"):
            # 缺少必要字段的接口
            pending_items.append(f"接口缺少ID (Block {interface.get('_block_index', 'unknown')})")
            if '_grid_content' in interface:
                pending_items.append(f"原始内容: {interface['_grid_content'][:200]}...")
        else:
            # 成功的接口，清理内部元数据
            clean_interface = {k: v for k, v in interface.items()
                             if not k.startswith('_') and k != "error"}
            successful_interfaces.append(clean_interface)

    # 按block_index排序接口
    successful_interfaces.sort(key=lambda x: x.get('_block_index', 0))

    # 清理接口中的排序字段
    for interface in successful_interfaces:
        interface.pop('_block_index', None)

    ism["interfaces"] = successful_interfaces
    ism["__pending__"] = pending_items

    return ism


def understand_doc_parallel(state: AgentState) -> AgentState:
    """
    并行版本的文档理解节点

    职责：把飞书文档内容按接口拆分，并行调用LLM生成ISM
    约束：只能写：ism
    """
    trace_id = state["trace_id"]
    step_name = "understand_doc_parallel"

    # 获取输入数据
    raw_docs = state["raw_docs"]
    feishu_urls = state.get("feishu_urls", [])
    templates = state.get("templates", [])

    logger.start(trace_id, step_name, "开始并行解析多个文档内容，生成合并的ISM",
                extra={
                    "docs_count": len(raw_docs),
                    "total_length": sum(len(doc) for doc in raw_docs),
                    "has_templates": len(templates) > 0
                })

    try:
        # 1. 合并多个文档内容
        combined_content = ""
        for i, doc in enumerate(raw_docs):
            combined_content += f"\n\n=== 文档 {i+1} ===\n{doc}"

        # 2. 提取主要URL
        primary_feishu_url = feishu_urls[0] if feishu_urls else None

        # 3. 准备文档元数据
        doc_meta = {
            "title": "并行解析文档",
            "url": primary_feishu_url or "",
            "version": "latest",
            "parsing_mode": "parallel"
        }

        # 尝试从文档中提取标题
        lines = combined_content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                doc_meta["title"] = line[2:].strip()
                break

        if len(feishu_urls) > 1:
            doc_meta["source_urls"] = feishu_urls
            doc_meta["source_count"] = len(feishu_urls)

        # 4. 检查文档中是否有grid块
        grid_blocks = extract_grid_blocks(combined_content)

        if not grid_blocks:
            logger.warning(trace_id, step_name, "文档中没有发现grid块，使用原有逻辑")
            # 如果没有grid块，回退到原有的单次调用逻辑
            from nodes.understand_doc import understand_doc
            return understand_doc(state)

        logger.info(trace_id, step_name, f"发现 {len(grid_blocks)} 个grid块，开始并行处理",
                   extra={"grid_blocks_count": len(grid_blocks)})

        # 5. 分割文档为并行处理的块
        chunks = split_document_for_parallel_processing(combined_content, max_interfaces_per_chunk=2)

        logger.info(trace_id, step_name, f"文档分割为 {len(chunks)} 个块进行并行处理",
                   extra={"chunks_count": len(chunks)})

        # 6. 并行处理所有块
        all_interfaces = []
        with ThreadPoolExecutor(max_workers=min(5, len(chunks))) as executor:
            future_to_chunk = {
                executor.submit(parse_interfaces_chunk, chunk, i, combined_content): (chunk, i)
                for i, chunk in enumerate(chunks)
            }

            for future in as_completed(future_to_chunk):
                chunk, chunk_index = future_to_chunk[future]
                try:
                    interfaces = future.result(timeout=120)  # 2分钟超时
                    all_interfaces.extend(interfaces)
                    logger.info(trace_id, step_name, f"块 {chunk_index} 处理完成，解析出 {len(interfaces)} 个接口")
                except Exception as e:
                    logger.error(trace_id, step_name, f"块 {chunk_index} 处理失败: {str(e)}")
                    # 添加失败信息到pending
                    all_interfaces.append({
                        "error": f"块处理失败: {str(e)}",
                        "_block_index": chunk_index * 100,
                        "_grid_content": chunk[:500] + "..." if len(chunk) > 500 else chunk
                    })

        logger.info(trace_id, step_name, f"所有块处理完成，共解析出 {len(all_interfaces)} 个接口",
                   extra={"total_interfaces": len(all_interfaces)})

        # 7. 合并接口为完整的ISM
        ism = merge_interfaces_to_ism(all_interfaces, doc_meta)

        # 8. 写入state
        result_state = state.copy()
        result_state["ism"] = ism

        logger.end(trace_id, step_name, "并行ISM生成完成",
                  extra={
                      "interfaces_count": len(ism.get("interfaces", [])),
                      "pending_count": len(ism["__pending__"]),
                      "doc_title": ism["doc_meta"].get("title", "未知"),
                      "processed_docs": len(raw_docs),
                      "grid_blocks_found": len(grid_blocks),
                      "parallel_chunks": len(chunks)
                  })

        return result_state

    except Exception as e:
        logger.error(trace_id, step_name, "并行ISM生成过程中发生错误", extra={"error": str(e)})

        # 构造错误兜底ISM
        fallback_ism = {
            "doc_meta": {
                "title": "并行处理出错的文档",
                "url": feishu_urls[0] if feishu_urls else "",
                "version": "latest",
                "parsing_mode": "parallel_failed"
            },
            "interfaces": [],
            "__pending__": [
                f"并行处理过程中发生错误: {str(e)}",
                "需要人工检查和补全或回退到单次处理模式"
            ]
        }

        result_state = state.copy()
        result_state["ism"] = fallback_ism

        logger.end(trace_id, step_name, "ISM生成完成（错误兜底）",
                  extra={
                      "interfaces_count": 0,
                      "pending_count": len(fallback_ism["__pending__"])
                  })

        return result_state


# 兼容性函数，保持原有的函数名
def understand_doc(state: AgentState) -> AgentState:
    """
    文档理解节点 - 自动选择并行或串行处理模式
    """
    return understand_doc_parallel(state)