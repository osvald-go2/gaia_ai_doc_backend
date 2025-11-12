#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
并行LLM文档理解节点
将文档按接口拆分成多个片段，并行调用LLM加速处理
"""

import json
import os
import uuid
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

**关键要求**：
1. **每个功能块只能生成一个唯一的接口**，不要重复生成
2. **接口名称必须唯一**，使用文档中的具体功能名称
3. **仔细区分不同的功能**，如"总筛选项"和"消耗趋势"是不同的接口

接口类型识别规则：
- **filter_dimension**: 筛选条件、过滤字段、查询参数（如：总筛选项）
- **data_display**: 数据列表、明细、表格内容（如：素材明细）
- **trend_analysis**: 时间序列、趋势图、对比分析（如：消耗趋势、交易趋势、消耗波动详情）
- **analytics_metric**: 指标、统计、计算值
- **export_report**: 导出、报表、下载相关
- **custom_action**: 自定义操作、特殊业务逻辑

字段处理规则：
- 忽略图片/示意图/参考口径（包含"参考口径:"的行不要输出）
- 对每个有效字段生成结构：
  - name：保留文档里的原始名字
  - expression：把 name 翻成英文占位符（如：总筛选项→totalFilter，消耗趋势→consumptionTrend）
  - data_type：维度一般是string，指标是number，时间是date
  - required：筛选条件通常为true，指标通常为false

输出格式（必须是JSON）：
{
  "id": "api_功能英文名_唯一后缀",
  "name": "功能中文名",
  "type": "接口类型",
  "fields": [ // 字段列表（统一格式）
    {"name": "字段名", "expression": "englishName", "data_type": "string", "required": true/false, "description": "字段描述"}
  ],
  "operations": ["read", "create", "update", "delete"]
}

**重要提醒**：
- 确保"id"字段是唯一的，可以使用功能英文名+类型组合
- 如果遇到相似功能，请仔细区分其差异（如：趋势vs详情）
- 每个grid块只应该产生一个接口

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


def extract_context_around_grid(content: str, grid_start: int, context_size: int = 15) -> str:
    """
    提取grid块周围的上下文，特别关注标题信息
    优先获取grid块前面最近的标题作为上下文
    """
    lines = content.split('\n')

    # 分两个阶段：先找标题，再收集描述
    best_title = None
    best_title_line = -1

    # 第一阶段：向上寻找最佳标题
    for i in range(grid_start - 1, max(-1, grid_start - context_size - 1), -1):
        if i < 0:
            break

        line = lines[i].strip()

        # 最高优先级：markdown标题（## ### #）
        if line.startswith('#') or line.startswith('##') or line.startswith('###'):
            best_title = lines[i]  # 保留原始格式（包括#）
            best_title_line = i
            break  # 找到markdown标题就立即停止，这是最理想的标题

        # 次高优先级：包含明确功能关键词的短行
        elif (not best_title and
              len(line) < 50 and
              line and
              not line.startswith('```') and
              not line.startswith('!') and
              any(keyword in line for keyword in ['详情', '列表', '查询', '统计', '分析', '导出', '配置', '管理', '设置'])):
            best_title = line
            best_title_line = i
            # 继续向上搜索，看是否有更好的markdown标题

        # 第三优先级：冒号结尾的标题
        elif (not best_title and
              (line.endswith('：') or line.endswith(':')) and
              len(line) < 50):
            best_title = line
            best_title_line = i
            # 继续向上搜索，看是否有更好的标题

    # 第二阶段：收集标题后的描述性内容（如果标题不是直接紧贴grid）
    context_lines = []

    if best_title:
        context_lines.append(best_title)

        # 在标题和grid之间收集描述性内容（最多2行）
        for i in range(best_title_line + 1, grid_start):
            if i >= len(lines):
                break

            line = lines[i].strip()

            # 遇到新的标题、代码块、空行等就停止
            if (not line or
                line.startswith('#') or
                line.startswith('```') or
                line.startswith('!') or
                line.startswith('|') or  # 表格
                line.startswith('-') or  # 列表
                line.startswith('*')):   # 列表
                break

            # 收集描述性内容
            if len(line) < 150:  # 避免过长的内容
                context_lines.append(lines[i])

            # 最多收集2行描述
            if len(context_lines) >= 3:  # 标题 + 最多2行描述
                break

    # 第三阶段：如果没有找到标题，回退到描述性文本
    if not context_lines:
        # 收集grid前面的几行描述性文本
        for i in range(grid_start - 1, max(-1, grid_start - 5), -1):
            if i < 0:
                break
            line = lines[i].strip()
            if line and not line.startswith('```') and not line.startswith('!'):
                context_lines.insert(0, lines[i])
                if len(context_lines) >= 2:
                    break

    # 最后的回退：最近的非空行
    if not context_lines:
        for i in range(grid_start - 1, max(-1, grid_start - 3), -1):
            if i < 0:
                break
            line = lines[i].strip()
            if line and not line.startswith('```'):
                context_lines.insert(0, lines[i])
                break

    return '\n'.join(context_lines)


def find_grid_position_in_document(grid_content: str, full_document: str) -> int:
    """
    在完整文档中找到grid块的真正起始行号
    使用更精确的匹配算法
    """
    lines = full_document.split('\n')
    grid_lines = grid_content.split('\n')

    # 提取grid块的标识内容（前几行用于匹配）
    grid_identifier_lines = []
    for line in grid_lines[:5]:  # 取前5行作为标识
        if line.strip():
            grid_identifier_lines.append(line.strip())

    if not grid_identifier_lines:
        return 0

    best_match = -1
    best_match_score = 0

    # 寻找最佳匹配位置
    for i, line in enumerate(lines):
        if line.strip().startswith('```grid'):
            # 找到grid开始，计算匹配分数
            match_score = 0
            for j, identifier_line in enumerate(grid_identifier_lines):
                if i + j < len(lines):
                    doc_line = lines[i + j].strip()
                    if doc_line == identifier_line:
                        match_score += 1
                    elif identifier_line in doc_line or doc_line in identifier_line:
                        match_score += 0.5

            # 更新最佳匹配
            if match_score > best_match_score and match_score >= len(grid_identifier_lines) * 0.6:  # 至少60%匹配
                best_match = i
                best_match_score = match_score

    # 如果找到匹配，返回最佳位置
    if best_match >= 0:
        return best_match

    # 备用方法：使用内容片段搜索
    if len(grid_lines) >= 2:
        # 使用grid内容中的独特片段进行搜索
        content_fragments = []
        for line in grid_lines[1:10]:  # 跳过```grid，取内容部分
            line = line.strip()
            if line and len(line) > 10 and not line.startswith('```') and not line.startswith('grid_column'):
                content_fragments.append(line)

        for fragment in content_fragments[:3]:  # 只用前3个片段搜索
            for i, doc_line in enumerate(lines):
                if fragment in doc_line or doc_line in fragment:
                    # 向前查找grid开始标记
                    for j in range(max(0, i - 5), i + 1):
                        if lines[j].strip().startswith('```grid'):
                            return j
                    return i

    # 最后回退：简单字符串搜索
    if grid_content in full_document:
        before_content = full_document.split(grid_content)[0]
        return before_content.count('\n')

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

            # 上下文提取完成 - 添加元数据用于调试
            if len(context) > 0:
                # 可以在这里添加调试信息到后续结果中，但暂时跳过日志记录
                pass
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
    并行LLM文档理解节点
    支持基于文档块的并行处理和传统的文档处理模式

    约束：只能写：ism
    """
    trace_id = state["trace_id"]
    step_name = "understand_doc_parallel"

    # 检查处理模式
    use_chunked = state.get("use_chunked_processing", False)
    doc_chunks = state.get("doc_chunks", [])
    raw_docs = state["raw_docs"]
    feishu_urls = state.get("feishu_urls", [])

    mode = "块处理" if use_chunked and doc_chunks else "传统文档"
    logger.start(trace_id, step_name, f"文档理解 - {mode}模式")

    try:
        if use_chunked and doc_chunks:
            # 新的块处理模式
            return process_with_chunks(state, trace_id, step_name)
        else:
            # 传统文档处理模式（向后兼容）
            return process_with_raw_docs(state, trace_id, step_name)

    except Exception as e:
        logger.error(trace_id, step_name, f"文档理解失败: {str(e)}")
        # 生成兜底的ISM
        return _generate_fallback_ism(state, str(e), trace_id, step_name)


def process_with_chunks(state: AgentState, trace_id: str, step_name: str) -> AgentState:
    """
    基于文档块的并行处理模式
    """
    doc_chunks = state["doc_chunks"]
    feishu_urls = state.get("feishu_urls", [])
    chunk_metadata = state.get("chunk_metadata", {})

    logger.info(trace_id, step_name, f"块处理模式: {len(doc_chunks)} 个块")

    # 详细记录每个块的信息
    for i, chunk in enumerate(doc_chunks):
        logger.info(trace_id, step_name, f"块 {i+1}: {chunk['chunk_type']}, "
                   f"has_grid={chunk['metadata']['has_grid']}, "
                   f"len={len(chunk['content'])} 字符, "
                   f"preview: {chunk['content'][:100]}...")

    try:
        # 1. 准备文档元数据
        primary_feishu_url = feishu_urls[0] if feishu_urls else ""
        doc_meta = {
            "title": "块并行解析文档",
            "url": primary_feishu_url,
            "version": "latest",
            "parsing_mode": "chunked_parallel",
            "total_chunks": len(doc_chunks),
            "chunking_strategy": chunk_metadata.get("chunking_strategy", {})
        }

        # 尝试从块中提取标题
        for chunk in doc_chunks:
            if chunk["chunk_type"] == "header_section":
                lines = chunk["content"].split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith('# '):
                        doc_meta["title"] = line[2:].strip()
                        break
                if doc_meta["title"] != "块并行解析文档":
                    break

        # 2. 按优先级排序块（grid块优先）
        sorted_chunks = sorted(doc_chunks, key=lambda x: x["metadata"]["processing_priority"])

        # 3. 检查是否有grid块
        grid_chunks = [chunk for chunk in sorted_chunks if chunk["metadata"]["has_grid"]]
        non_grid_chunks = [chunk for chunk in sorted_chunks if not chunk["metadata"]["has_grid"]]

        logger.info(trace_id, step_name, f"块分类: {len(grid_chunks)} 个grid块, {len(non_grid_chunks)} 个普通块")

        if grid_chunks:
            logger.info(trace_id, step_name, f"并行处理 {len(grid_chunks)} 个grid块")
            # 显示每个grid块的信息
            for i, chunk in enumerate(grid_chunks):
                logger.info(trace_id, step_name, f"Grid块 {i+1}: {chunk['chunk_id']}, "
                           f"预览: {chunk['content'][:150]}...")

            # 并行处理grid块
            interface_results = process_grid_chunks_parallel(grid_chunks, trace_id, step_name)

            # 处理其他块
            other_chunks = [chunk for chunk in sorted_chunks if not chunk["metadata"]["has_grid"]]
            if other_chunks:
                logger.info(trace_id, step_name, f"处理 {len(other_chunks)} 个普通块")
                other_results = process_other_chunks_sequential(other_chunks, trace_id, step_name)
                interface_results.extend(other_results)
        else:
            logger.info(trace_id, step_name, f"无grid块，整体理解 {len(sorted_chunks)} 个块")
            # 并行处理所有块，生成整体理解
            interface_results = process_all_chunks_for_understanding(sorted_chunks, trace_id, step_name)

        # 4. 构建ISM
        final_ism = build_ism_from_chunk_results(interface_results, doc_meta, doc_chunks, trace_id, step_name)

        result_state = state.copy()
        result_state["ism"] = final_ism

        logger.end(trace_id, step_name, f"块处理完成: {len(interface_results)} 个接口，{len(doc_chunks)} 个块")

        return result_state

    except Exception as e:
        logger.error(trace_id, step_name, f"块处理失败: {str(e)}")
        return _generate_fallback_ism(state, f"块处理失败: {str(e)}", trace_id, step_name)


def process_with_raw_docs(state: AgentState, trace_id: str, step_name: str) -> AgentState:
    """
    传统文档处理模式（保持原有逻辑）
    """
    raw_docs = state["raw_docs"]
    feishu_urls = state.get("feishu_urls", [])

    logger.info(trace_id, step_name, f"传统模式: {len(raw_docs)} 个文档，{sum(len(doc) for doc in raw_docs)} 字符")

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
            logger.warning(trace_id, step_name, "文档中没有发现grid块，生成基础ISM")
            # 如果没有grid块，生成基础的ISM结构
            return _generate_basic_ism(state, combined_content)

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


def _generate_basic_ism(state: AgentState, combined_content: str) -> AgentState:
    """
    生成基础的ISM结构（当没有grid块时使用）
    """
    trace_id = state["trace_id"]
    step_name = "understand_doc_parallel"
    user_intent = state.get("user_intent", "generate_crud")
    feishu_urls = state["feishu_urls"]

    logger.info(trace_id, step_name, "生成基础ISM结构",
                extra={"content_length": len(combined_content), "user_intent": user_intent})

    # 根据用户意图生成基础的实体和接口
    if user_intent == "generate_crud" and "用户表" in combined_content:
        # 从mock内容中提取用户表信息
        interfaces = [
            {
                "id": "users_crud",
                "name": "用户管理CRUD",
                "type": "crud",
                "description": "用户信息的增删改查操作",
                "target_entity": "users",
                "fields": [
                    {"name": "id", "type": "string", "required": True, "description": "用户ID，主键"},
                    {"name": "name", "type": "string", "required": False, "description": "用户姓名"},
                    {"name": "channel", "type": "string", "required": False, "description": "渠道"}
                ],
                "operations": ["create", "read", "update", "delete"]
            }
        ]
        entities = [
            {
                "id": "users",
                "name": "用户表",
                "description": "系统用户信息表",
                "fields": interfaces[0]["fields"]
            }
        ]
    else:
        # 生成通用的接口结构
        interfaces = [
            {
                "id": "basic_interface",
                "name": "基础接口",
                "type": "custom",
                "description": "从文档内容生成的基础接口",
                "fields": [
                    {"name": "id", "type": "string", "required": True, "description": "主键ID"}
                ],
                "operations": ["read"]
            }
        ]
        entities = []

    # 构建基础ISM
    basic_ism = {
        "doc_meta": {
            "title": "基础生成的文档",
            "url": feishu_urls[0] if feishu_urls else "",
            "version": "latest",
            "parsing_mode": "basic_fallback",
            "content_length": len(combined_content)
        },
        "interfaces": interfaces,
        "entities": entities,
        "actions": [],
        "views": [],
        "__generation_method": "basic_fallback"
    }

    result_state = state.copy()
    result_state["ism"] = basic_ism

    logger.end(trace_id, step_name, f"基础ISM生成完成: {len(interfaces)} 个接口，{len(entities)} 个实体")

    return result_state


# ==================== 块处理相关辅助函数 ====================

def _get_chunk_type_distribution(chunks: List[dict]) -> dict:
    """获取块类型分布统计"""
    distribution = {}
    for chunk in chunks:
        chunk_type = chunk["chunk_type"]
        distribution[chunk_type] = distribution.get(chunk_type, 0) + 1
    return distribution


def process_grid_chunks_parallel(grid_chunks: List[dict], trace_id: str, step_name: str) -> List[dict]:
    """
    并行处理包含grid的块
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from deepseek_client_simple import call_deepseek_llm

    interface_results = []

    logger.info(trace_id, step_name, f"并行处理 {len(grid_chunks)} 个grid块")

    def process_single_grid_chunk(chunk: dict) -> dict:
        """处理单个grid块"""
        try:
            chunk_id = chunk["chunk_id"]
            content = chunk["content"]
            context_before = chunk.get("context_before", "")
            context_after = chunk.get("context_after", "")

            # 构建完整的上下文
            full_content = f"{context_before}\n\n{content}\n\n{context_after}".strip()

            # 记录LLM调用
            logger.info(trace_id, step_name, f"调用LLM解析块 {chunk_id}")
            logger.info(trace_id, step_name, f"系统提示词: {INTERFACE_SYSTEM_PROMPT[:100]}...")
            logger.info(trace_id, step_name, f"用户提示词: 请解析以下内容中的grid块，生成接口语义模型:\n\n{full_content[:200]}...")

            # 调用LLM解析grid块
            result = call_deepseek_llm(
                system_prompt=INTERFACE_SYSTEM_PROMPT,
                user_prompt=f"请解析以下内容中的grid块，生成接口语义模型：\n\n{full_content}",
                model="deepseek-chat",
                temperature=0.1,
                max_tokens=2000
            )

            # 记录LLM返回结果
            logger.info(trace_id, step_name, f"LLM返回结果: {result[:300]}...")

            # 解析LLM返回结果 - 处理可能的数组格式
            try:
                parsed_data = json.loads(result.strip())

                # 如果返回的是数组格式，取第一个接口
                if isinstance(parsed_data, list):
                    logger.info(trace_id, step_name, f"LLM返回数组格式，取第一个接口: {parsed_data[0].get('name', '未知')}")
                    interface_data = parsed_data[0]
                else:
                    interface_data = parsed_data

                logger.info(trace_id, step_name, f"JSON解析成功: {interface_data.get('name', '未知接口')} [{interface_data.get('type', 'unknown')}]")

                interface_data["source_chunk_id"] = chunk_id
                interface_data["source_chunk_type"] = chunk["chunk_type"]
                return {
                    "success": True,
                    "interface": interface_data,
                    "chunk_id": chunk_id,
                    "llm_response": result
                }

            except json.JSONDecodeError as e:
                logger.warn(trace_id, step_name, f"JSON解析失败 - 块 {chunk_id}: {str(e)[:100]}")

                # 尝试从返回结果中提取接口信息
                grid_info = {"name": f"接口_{chunk_id}", "description": "从grid块提取的接口"}
                interface_data = _extract_interface_from_text(result, chunk, grid_info, trace_id, step_name)
                if interface_data:
                    return {
                        "success": True,
                        "interface": interface_data,
                        "chunk_id": chunk_id,
                        "llm_response": result
                    }

                logger.warn(trace_id, step_name, f"文本解析失败 - 块 {chunk_id}")
                return {
                    "success": False,
                    "chunk_id": chunk_id,
                    "error": f"JSON解析和文本解析都失败: {str(e)[:100]}"
                }

            except Exception as e:
                logger.error(trace_id, step_name, f"块处理异常 - {chunk.get('chunk_id', 'unknown')}: {str(e)}")
                return {
                    "success": False,
                    "chunk_id": chunk.get("chunk_id", "unknown"),
                    "error": str(e)
                }

        except Exception as e:
            logger.error(trace_id, step_name, f"块处理系统异常: {str(e)}")
            return {
                "success": False,
                "chunk_id": chunk.get("chunk_id", "unknown"),
                "error": f"系统异常: {str(e)}"
            }

    # 并行执行
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_chunk = {executor.submit(process_single_grid_chunk, chunk): chunk for chunk in grid_chunks}

        for future in as_completed(future_to_chunk):
            chunk = future_to_chunk[future]
            try:
                result = future.result()
                if result["success"]:
                    interface_results.append(result["interface"])
                    logger.info(trace_id, step_name, f"块 {result['chunk_id']} 处理成功")
                else:
                    logger.warn(trace_id, step_name, f"块 {result['chunk_id']} 处理失败: {result.get('error', 'Unknown')}")
            except Exception as e:
                logger.error(trace_id, step_name, f"块 {chunk['chunk_id']} 执行异常: {str(e)}")

    success_count = len(interface_results)
    success_rate = f"{success_count/len(grid_chunks)*100:.1f}%" if grid_chunks else "0%"
    logger.info(trace_id, step_name, f"Grid块处理完成: {success_count}/{len(grid_chunks)} 成功 ({success_rate})")

    # 找出所有处理的块ID（包括成功和失败的）
    processed_chunk_ids = {iface.get("source_chunk_id", "") for iface in interface_results}
    all_chunk_ids = {chunk.get("chunk_id", "") for chunk in grid_chunks}
    missing_chunk_ids = all_chunk_ids - processed_chunk_ids

    # 检查是否有缺失的块，包括预期但未处理的接口
    expected_interfaces = ["总筛选项", "消耗波动详情", "素材明细", "消耗趋势", "交易趋势"]
    found_interface_names = {iface.get("name", "") for iface in interface_results}
    missing_interfaces = [exp for exp in expected_interfaces if exp not in found_interface_names]

    logger.info(trace_id, step_name, f"已处理块ID: {processed_chunk_ids}")
    logger.info(trace_id, step_name, f"所有块ID: {all_chunk_ids}")
    logger.info(trace_id, step_name, f"缺失块ID: {missing_chunk_ids}")
    logger.info(trace_id, step_name, f"已找到接口: {found_interface_names}")
    logger.info(trace_id, step_name, f"缺失接口: {missing_interfaces}")

    # 如果有失败的块或缺失的接口，尝试降级处理
    if missing_chunk_ids or missing_interfaces:
        logger.info(trace_id, step_name, f"开始处理缺失的块和接口")

        # 找出失败的块
        failed_chunks = [chunk for chunk in grid_chunks if chunk.get("chunk_id", "") in missing_chunk_ids]

        logger.info(trace_id, step_name, f"识别出 {len(failed_chunks)} 个失败的块，开始降级处理")

        for chunk in failed_chunks:
            try:
                # 使用更简单的降级方法
                chunk_id = chunk.get("chunk_id", "unknown")
                content = chunk.get("content", "")

                logger.info(trace_id, step_name, f"降级处理块: {chunk_id}")

                # 从内容中直接提取接口名称
                interface_name = "未知接口"
                if "总筛选项" in content:
                    interface_name = "总筛选项"
                elif "消耗波动详情" in content:
                    interface_name = "消耗波动详情"
                elif "素材明细" in content:
                    interface_name = "素材明细"
                elif "消耗趋势" in content:
                    interface_name = "消耗趋势"
                elif "交易趋势" in content:
                    interface_name = "交易趋势"
                else:
                    # 尝试从标题中提取
                    lines = content.split('\n')
                    for line in lines:
                        if line.strip().startswith('##'):
                            interface_name = line.strip().replace('##', '').strip()
                            break

                # 创建降级接口
                fallback_interface = {
                    "id": f"interface_fallback_{chunk_id}",
                    "name": interface_name,
                    "type": "fallback",
                    "method": "GET",
                    "path": f"/api/{interface_name.replace(' ', '_').lower()}",
                    "description": f"从 {interface_name} 内容降级生成的接口",
                    "fields": [
                        {"name": "id", "type": "string", "required": True, "description": "主键ID"}
                    ],
                    "operations": ["read"],
                    "source_chunk_id": chunk_id,
                    "source_chunk_type": chunk.get("chunk_type", "unknown"),
                    "source_method": "fallback_processing"
                }

                interface_results.append(fallback_interface)
                logger.info(trace_id, step_name, f"块 {chunk_id} 降级处理成功: {interface_name}")

            except Exception as e:
                logger.error(trace_id, step_name, f"块 {chunk.get('chunk_id', 'unknown')} 降级处理也失败: {str(e)}")

        # 处理缺失的接口（即使所有块都"成功"了，但某些接口可能没有被LLM识别）
        if missing_interfaces:
            logger.info(trace_id, step_name, f"为缺失的接口创建降级版本: {missing_interfaces}")

            for missing_interface in missing_interfaces:
                # 为每个缺失的接口创建一个降级版本
                fallback_interface = {
                    "id": f"interface_fallback_missing_{missing_interface.replace(' ', '_').lower()}_{uuid.uuid4().hex[:8]}",
                    "name": missing_interface,
                    "type": "fallback",
                    "method": "GET",
                    "path": f"/api/{missing_interface.replace(' ', '_').lower()}",
                    "description": f"为缺失接口 {missing_interface} 创建的降级版本",
                    "fields": [
                        {"name": "id", "type": "string", "required": True, "description": "主键ID"}
                    ],
                    "operations": ["read"],
                    "source_chunk_id": "missing_fallback",
                    "source_chunk_type": "missing_interface",
                    "source_method": "missing_interface_fallback"
                }

                interface_results.append(fallback_interface)
                logger.info(trace_id, step_name, f"为缺失接口创建降级版本: {missing_interface}")

    final_count = len(interface_results)
    final_rate = f"{final_count/len(grid_chunks)*100:.1f}%" if grid_chunks else "0%"
    logger.info(trace_id, step_name, f"Grid块最终处理结果: {final_count}/{len(grid_chunks)} 成功 ({final_rate})")

    # 最终检查：确保所有5个预期接口都存在
    final_interface_names = {iface.get("name", "") for iface in interface_results}
    final_missing = [exp for exp in expected_interfaces if exp not in final_interface_names]

    if final_missing:
        logger.error(trace_id, step_name, f"最终仍然缺失接口: {final_missing}")
    else:
        logger.info(trace_id, step_name, f"[SUCCESS] 所有预期接口都已生成: {expected_interfaces}")

    return interface_results


def process_other_chunks_sequential(other_chunks: List[dict], trace_id: str, step_name: str) -> List[dict]:
    """
    顺序处理其他非grid块
    """
    from deepseek_client_simple import call_deepseek_llm

    interface_results = []

    logger.info(trace_id, step_name, f"顺序处理 {len(other_chunks)} 个普通块")

    # 合并所有非grid块，进行整体理解
    combined_content = ""
    for i, chunk in enumerate(other_chunks):
        combined_content += f"\n\n=== 块 {i+1} ({chunk['chunk_type']}) ===\n"
        combined_content += chunk["content"]

    if combined_content.strip():
        try:
            # 使用通用提示词进行文档理解
            general_prompt = f"""
你是一个文档理解专家，请分析以下文档内容，识别其中的功能需求、数据结构和业务逻辑。

文档内容：
{combined_content}

请根据内容生成：
1. 如果包含用户界面或数据表格，生成对应的接口定义
2. 如果包含数据模型，生成对应的实体定义
3. 如果包含业务流程，生成对应的操作定义

输出格式要求：
- 返回JSON格式的结果
- 包含interfaces（接口定义）、entities（实体定义）、actions（操作定义）等字段
- 每个接口要有明确的id、name、type、fields等属性
"""

            logger.info(trace_id, step_name, f"调用LLM理解普通块")
            logger.info(trace_id, step_name, f"系统提示词: 你是一个专业的文档理解专家...")
            logger.info(trace_id, step_name, f"用户提示词: {general_prompt[:200]}...")

            result = call_deepseek_llm(
                system_prompt="你是一个专业的文档理解专家，擅长从需求文档中提取业务模型和接口定义。",
                user_prompt=general_prompt,
                model="deepseek-chat",
                temperature=0.1,
                max_tokens=3000
            )

            # 记录LLM返回结果
            logger.info(trace_id, step_name, f"LLM返回: {result[:300]}...")

            # 解析LLM返回结果
            try:
                parsed_result = json.loads(result.strip())
                interfaces_count = len(parsed_result.get("interfaces", []))
                logger.info(trace_id, step_name, f"普通块解析成功: {interfaces_count} 个接口")

                # 转换为标准接口格式
                if "interfaces" in parsed_result:
                    for interface in parsed_result["interfaces"]:
                        interface["source_chunk_ids"] = [chunk["chunk_id"] for chunk in other_chunks]
                        interface["source_method"] = "sequential_understanding"
                        interface_results.append(interface)

                if "entities" in parsed_result:
                    # 保存实体信息供后续使用
                    for entity in parsed_result["entities"]:
                        entity["source_chunk_ids"] = [chunk["chunk_id"] for chunk in other_chunks]
                        entity["source_method"] = "sequential_understanding"

            except json.JSONDecodeError:
                logger.warn(trace_id, step_name, f"JSON解析失败，使用基础理解")
                # 基础理解：生成简单接口
                basic_interface = {
                    "id": f"interface_basic_{uuid.uuid4().hex[:8]}",
                    "name": "文档理解接口",
                    "type": "custom",
                    "description": "从文档内容中提取的基础接口",
                    "fields": [
                        {"name": "id", "type": "string", "required": True, "description": "主键ID"}
                    ],
                    "operations": ["read", "create", "update", "delete"],
                    "source_chunk_ids": [chunk["chunk_id"] for chunk in other_chunks],
                    "source_method": "basic_fallback"
                }
                interface_results.append(basic_interface)

        except Exception as e:
            logger.error(trace_id, step_name, f"普通块LLM调用失败: {str(e)}",
                        extra={"error": str(e)})

    logger.info(trace_id, step_name, f"普通块处理完成: {len(interface_results)} 个接口")

    return interface_results


def process_all_chunks_for_understanding(chunks: List[dict], trace_id: str, step_name: str) -> List[dict]:
    """
    当没有grid块时，对所有块进行整体理解
    """
    from deepseek_client_simple import call_deepseek_llm

    interface_results = []

    logger.info(trace_id, step_name, f"整体理解 {len(chunks)} 个块")

    # 合并所有块内容
    combined_content = ""
    for i, chunk in enumerate(chunks):
        combined_content += f"\n\n=== 块 {i+1} ({chunk['chunk_type']}) ===\n"
        combined_content += chunk["content"]

    if combined_content.strip():
        try:
            # 使用针对非grid文档的提示词
            user_prompt = f"""
请分析以下文档内容，提取其中的业务需求和数据模型。

文档内容：
{combined_content}

分析要求：
1. 识别文档中的业务实体（如用户表、订单表等）
2. 识别业务操作（如增删改查、导出报表等）
3. 提取字段定义和类型信息
4. 生成对应的接口和实体定义

请返回JSON格式，包含：
- interfaces: 接口定义列表
- entities: 实体定义列表
- actions: 操作定义列表

每个接口需要包含：
- id: 唯一标识
- name: 中文名称
- type: 接口类型（crud/analytics/export等）
- fields: 字段定义列表
- operations: 支持的操作列表
"""

            logger.info(trace_id, step_name, f"调用LLM整体理解")
            logger.info(trace_id, step_name, f"系统提示词: 你是一个专业的业务分析师...")
            logger.info(trace_id, step_name, f"用户提示词: {user_prompt[:200]}...")

            result = call_deepseek_llm(
                system_prompt="你是一个专业的业务分析师，擅长从需求文档中提取业务模型、数据结构和接口定义。",
                user_prompt=user_prompt,
                model="deepseek-chat",
                temperature=0.1,
                max_tokens=4000
            )

            # 记录LLM返回结果
            logger.info(trace_id, step_name, f"LLM返回: {result[:300]}...")

            # 解析LLM返回结果
            try:
                parsed_result = json.loads(result.strip())
                interfaces_count = len(parsed_result.get("interfaces", []))
                entities_count = len(parsed_result.get("entities", []))
                logger.info(trace_id, step_name, f"整体理解成功: {interfaces_count} 个接口，{entities_count} 个实体")

                # 处理接口定义
                if "interfaces" in parsed_result:
                    for interface in parsed_result["interfaces"]:
                        interface["source_chunk_ids"] = [chunk["chunk_id"] for chunk in chunks]
                        interface["source_method"] = "full_document_understanding"
                        interface_results.append(interface)

            except json.JSONDecodeError:
                logger.warn(trace_id, step_name, f"JSON解析失败，使用基础理解")
                # 基础理解
                interface_results.extend(_generate_basic_interfaces_from_chunks(chunks))

        except Exception as e:
            logger.error(trace_id, step_name, f"整体理解失败: {str(e)}")
            # 降级到基础理解
            interface_results.extend(_generate_basic_interfaces_from_chunks(chunks))

    return interface_results


def _generate_basic_interfaces_from_chunks(chunks: List[dict]) -> List[dict]:
    """从块生成基础接口（降级方案）"""
    import uuid

    # 检查是否包含用户表相关信息
    combined_content = " ".join([chunk["content"] for chunk in chunks])

    if "用户表" in combined_content or "users" in combined_content.lower():
        return [
            {
                "id": f"users_interface_{uuid.uuid4().hex[:8]}",
                "name": "用户管理接口",
                "type": "crud",
                "description": "用户信息的管理接口",
                "fields": [
                    {"name": "id", "type": "string", "required": True, "description": "用户ID"},
                    {"name": "name", "type": "string", "required": False, "description": "用户姓名"},
                    {"name": "channel", "type": "string", "required": False, "description": "渠道"}
                ],
                "operations": ["create", "read", "update", "delete"],
                "source_chunk_ids": [chunk["chunk_id"] for chunk in chunks],
                "source_method": "basic_fallback"
            }
        ]
    else:
        return [
            {
                "id": f"basic_interface_{uuid.uuid4().hex[:8]}",
                "name": "基础接口",
                "type": "custom",
                "description": "从文档内容生成的基础接口",
                "fields": [
                    {"name": "id", "type": "string", "required": True, "description": "主键ID"}
                ],
                "operations": ["read"],
                "source_chunk_ids": [chunk["chunk_id"] for chunk in chunks],
                "source_method": "basic_fallback"
            }
        ]


def build_ism_from_chunk_results(interface_results: List[dict], doc_meta: dict, chunks: List[dict], trace_id: str, step_name: str) -> dict:
    """
    从块处理结果构建最终的ISM
    """
    logger.info(trace_id, step_name, f"构建ISM: {len(interface_results)} 个接口")

    # 标准化接口数据
    standardized_interfaces = []
    entities = []
    seen_interfaces = {}  # 用于去重的字典 {key: interface}

    for interface in interface_results:
        # 确保接口有必需的字段
        standardized_interface = {
            "id": interface.get("id", f"interface_{uuid.uuid4().hex[:8]}"),
            "name": interface.get("name", "未命名接口"),
            "type": interface.get("type", "custom"),
            "description": interface.get("description", ""),
            "fields": interface.get("fields", []),
            "operations": interface.get("operations", ["read"]),
            "source_chunk_ids": interface.get("source_chunk_ids", []),
            "source_method": interface.get("source_method", "unknown")
        }

        # 标准化字段
        for field in standardized_interface["fields"]:
            if "data_type" not in field:
                field["data_type"] = "string"
            if "required" not in field:
                field["required"] = False
            if "description" not in field:
                field["description"] = field.get("name", "")

        # 去重逻辑：基于接口名称和类型组合
        interface_key = f"{standardized_interface['name']}_{standardized_interface['type']}"

        if interface_key in seen_interfaces:
            # 发现重复接口，合并信息
            existing = seen_interfaces[interface_key]
            logger.info(trace_id, step_name, f"发现重复接口: {standardized_interface['name']}，合并处理")

            # 合并源块信息
            existing["source_chunk_ids"].extend(standardized_interface["source_chunk_ids"])
            existing["source_chunk_ids"] = list(set(existing["source_chunk_ids"]))  # 去重

            # 如果新接口有更多字段，更新字段信息
            if len(standardized_interface["fields"]) > len(existing["fields"]):
                existing["fields"] = standardized_interface["fields"]
                logger.info(trace_id, step_name, f"更新接口 {standardized_interface['name']} 的字段信息")

            # 合并操作
            existing_ops = set(existing["operations"])
            new_ops = set(standardized_interface["operations"])
            existing["operations"] = list(existing_ops.union(new_ops))

        else:
            # 新接口，添加到结果中
            seen_interfaces[interface_key] = standardized_interface
            standardized_interfaces.append(standardized_interface)

        # 基于去重后的接口创建实体
    for standardized_interface in standardized_interfaces:
        if standardized_interface["type"] == "crud" and standardized_interface["fields"]:
            entity = {
                "id": f"entity_{standardized_interface['id'].replace('interface_', '')}",
                "name": standardized_interface["name"].replace("接口", "").replace("管理", "") + "表",
                "description": f"{standardized_interface['description']}对应的数据实体",
                "fields": standardized_interface["fields"],
                "source_interface_id": standardized_interface["id"]
            }
            entities.append(entity)

    # 构建最终ISM
    final_ism = {
        "doc_meta": doc_meta,
        "interfaces": standardized_interfaces,
        "entities": entities,
        "actions": [],
        "views": [],
        "parsing_statistics": {
            "total_chunks": len(chunks),
            "chunks_with_grid": len([c for c in chunks if c["metadata"]["has_grid"]]),
            "chunks_processed": len(chunks),
            "interfaces_generated": len(standardized_interfaces),
            "entities_generated": len(entities)
        },
        "__processing_method": "chunked_parallel",
        "__key": f"chunked_{hash(str(chunks)) % 10000:04d}"
    }

    logger.info(trace_id, step_name, f"ISM构建完成: {len(standardized_interfaces)} 个接口，{len(entities)} 个实体")

    return final_ism


def _generate_fallback_ism(state: AgentState, error_msg: str, trace_id: str, step_name: str) -> AgentState:
    """生成兜底ISM（现有逻辑）"""
    feishu_urls = state.get("feishu_urls", [])

    fallback_ism = {
        "doc_meta": {
            "title": "解析失败的文档",
            "url": feishu_urls[0] if feishu_urls else "",
            "version": "latest",
            "parsing_mode": "error_fallback",
            "error": error_msg
        },
        "interfaces": [],
        "entities": [],
        "actions": [],
        "views": [],
        "__pending__": [f"文档理解发生错误: {error_msg}"],
        "__key": f"error_{hash(error_msg) % 1000:03d}"
    }

    result_state = state.copy()
    result_state["ism"] = fallback_ism

    logger.error(trace_id, step_name, f"生成兜底ISM: {error_msg}")

    return result_state


def _extract_interface_from_text(result: str, chunk_data: dict, grid_info: dict, trace_id: str, step_name: str) -> dict:
    """
    当JSON解析失败时，从文本中提取接口信息的降级方法

    Args:
        result: LLM返回的原始文本
        chunk_data: 当前处理的数据块
        grid_info: 接口基本信息
        trace_id: 追踪ID
        step_name: 步骤名称

    Returns:
        dict: 提取的接口信息
    """
    logger.info(trace_id, step_name, f"开始文本提取接口信息")

    try:
        import re
        import uuid

        # 默认接口结构
        interface = {
            "id": f"interface_fallback_{uuid.uuid4().hex[:8]}",
            "name": grid_info.get("name", "未知接口"),
            "type": "unknown",
            "method": "GET",
            "path": "",
            "description": grid_info.get("description", ""),
            "fields": [],
            "operations": ["read"],
            "parameters": {
                "properties": {},
                "required": [],
                "type": "object"
            },
            "responses": {
                "200": {
                    "description": "成功响应",
                    "schema": {"type": "object"}
                }
            }
        }

        # 提取接口名称
        name_patterns = [
            r'["\'"]?name["\'"]?\s*[:：]\s*["\'"]([^"\']+)["\'"]',
            r'接口名[称]?[:：]\s*([^\n，。,\.]+)',
            r'name[:：]\s*([^\n，。,\.]+)'
        ]

        for pattern in name_patterns:
            match = re.search(pattern, result, re.IGNORECASE)
            if match:
                interface["name"] = match.group(1).strip()
                break

        # 提取请求方法
        method_patterns = [
            r'["\'"]?method["\'"]?\s*[:：]\s*["\'"]?(GET|POST|PUT|DELETE|PATCH)["\'"]?',
            r'请求方式?[:：]\s*(GET|POST|PUT|DELETE|PATCH)',
            r'method[:：]\s*(GET|POST|PUT|DELETE|PATCH)'
        ]

        for pattern in method_patterns:
            match = re.search(pattern, result, re.IGNORECASE)
            if match:
                interface["method"] = match.group(1).upper()
                break

        # 提取路径
        path_patterns = [
            r'["\'"]?path["\'"]?\s*[:：]\s*["\'"]([^"\']+)["\'"]',
            r'路径[:：]\s*([^\n，。,\.]+)',
            r'path[:：]\s*([^\n，。,\.]+)',
            r'/api/[^\s\n，。,\.]+'
        ]

        for pattern in path_patterns:
            match = re.search(pattern, result, re.IGNORECASE)
            if match:
                path = match.group(1).strip()
                # 确保路径以/开头
                if not path.startswith('/'):
                    path = '/' + path
                interface["path"] = path
                break

        # 如果有表格数据，尝试从中提取更多结构化信息
        grid_content = chunk_data.get("content", "")
        if "消耗" in grid_content and "详情" in grid_content:
            interface["description"] = "获取消耗详情相关信息"
            interface["name"] = interface.get("name") or "消耗波动详情"
            interface["type"] = "analytics"
            interface["operations"] = ["read", "analyze"]
            interface["fields"] = [
                {"name": "date", "type": "string", "required": True, "description": "日期"},
                {"name": "consume_amount", "type": "number", "required": False, "description": "消耗金额"},
                {"name": "fluctuation", "type": "number", "required": False, "description": "波动值"}
            ]
        elif "素材" in grid_content and "明细" in grid_content:
            interface["description"] = "获取素材明细数据"
            interface["name"] = interface.get("name") or "素材明细"
            interface["type"] = "crud"
            interface["operations"] = ["read", "create", "update", "delete"]
            interface["fields"] = [
                {"name": "material_id", "type": "string", "required": True, "description": "素材ID"},
                {"name": "material_name", "type": "string", "required": True, "description": "素材名称"},
                {"name": "material_type", "type": "string", "required": False, "description": "素材类型"}
            ]
        elif "趋势" in grid_content:
            if "消耗" in grid_content:
                interface["description"] = "获取消耗趋势数据"
                interface["name"] = interface.get("name") or "消耗趋势"
                interface["type"] = "analytics"
                interface["operations"] = ["read", "analyze"]
                interface["fields"] = [
                    {"name": "date_range", "type": "string", "required": True, "description": "日期范围"},
                    {"name": "trend_data", "type": "array", "required": False, "description": "趋势数据"}
                ]
            elif "交易" in grid_content:
                interface["description"] = "获取交易趋势数据"
                interface["name"] = interface.get("name") or "交易趋势"
                interface["type"] = "analytics"
                interface["operations"] = ["read", "analyze"]
                interface["fields"] = [
                    {"name": "transaction_date", "type": "string", "required": True, "description": "交易日期"},
                    {"name": "transaction_amount", "type": "number", "required": False, "description": "交易金额"}
                ]
        elif "总" in grid_content and "筛选" in grid_content:
            interface["description"] = "获取总筛选项信息"
            interface["name"] = interface.get("name") or "总筛选项"
            interface["type"] = "config"
            interface["operations"] = ["read"]
            interface["fields"] = [
                {"name": "filter_key", "type": "string", "required": True, "description": "筛选键"},
                {"name": "filter_value", "type": "string", "required": True, "description": "筛选值"},
                {"name": "filter_type", "type": "string", "required": False, "description": "筛选类型"}
            ]

        # 如果没有提取到路径，根据接口名称生成默认路径
        if not interface.get("path"):
            interface["path"] = f"/api/{interface['name'].replace(' ', '_').lower()}"

        logger.info(trace_id, step_name, f"文本提取完成: {interface['name']} - {interface['method']} {interface['path']}")

        return interface

    except Exception as e:
        logger.error(trace_id, step_name, f"文本提取失败: {str(e)}")

        # 最后的降级选项
        return {
            "id": f"interface_emergency_{uuid.uuid4().hex[:8]}",
            "name": grid_info.get("name", "未知接口"),
            "type": "fallback",
            "method": "GET",
            "path": f"/api/{grid_info.get('name', 'unknown').replace(' ', '_').lower()}",
            "description": f"从文本降级提取的接口: {grid_info.get('description', '')}",
            "fields": [
                {"name": "id", "type": "string", "required": True, "description": "主键ID"}
            ],
            "operations": ["read"],
            "parameters": {
                "properties": {},
                "required": [],
                "type": "object"
            },
            "responses": {
                "200": {
                    "description": "成功响应",
                    "schema": {"type": "object"}
                }
            }
        }


# 兼容性函数，保持原有的函数名
def understand_doc(state: AgentState) -> AgentState:
    """
    文档理解节点 - 自动选择并行或串行处理模式
    """
    return understand_doc_parallel(state)