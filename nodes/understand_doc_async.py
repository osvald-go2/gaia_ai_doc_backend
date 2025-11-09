#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步IO版本的文档理解节点
使用asyncio进一步提升LLM调用的并发性能，集成缓存系统
"""

import asyncio
import aiohttp
import json
import time
import os
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from models.state import AgentState
from utils.logger import logger
from utils.llm_cache import get_llm_cache
from dotenv import load_dotenv

load_dotenv()


class AsyncDeepSeekClient:
    """异步DeepSeek客户端，集成缓存系统"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.cache = get_llm_cache()

        if not self.api_key:
            self.use_mock = True
            print(f"{{\"timestamp\": \"{datetime.now().isoformat()}\", \"level\": \"WARNING\", \"message\": \"未配置DEEPSEEK_API_KEY，异步客户端将使用mock模式\"}}")
        else:
            self.use_mock = False
            logger.info(f"异步DeepSeek客户端初始化成功 - base_url: {self.base_url}")

    async def call_llm_async(self, system_prompt: str, user_prompt: str,
                           model: str = "deepseek-chat", temperature: float = 0.1,
                           max_tokens: int = 2000, session: Optional[aiohttp.ClientSession] = None) -> str:
        """异步调用LLM，带缓存支持"""
        # 生成缓存键
        content_for_cache = f"{system_prompt}\n\n{user_prompt}"

        # 尝试从缓存获取结果
        cached_result = self.cache.get(content_for_cache)
        if cached_result:
            logger.debug("异步LLM调用缓存命中")
            return json.dumps(cached_result, ensure_ascii=False)

        if self.use_mock:
            result = self._mock_response(system_prompt, user_prompt)
        else:
            result = await self._call_llm_api(system_prompt, user_prompt, model, temperature, max_tokens, session)

        # 解析结果并缓存
        try:
            parsed_result = json.loads(result)
            self.cache.put(content_for_cache, parsed_result)
            return result
        except json.JSONDecodeError as e:
            print(f"{{\"timestamp\": \"{datetime.now().isoformat()}\", \"level\": \"WARNING\", \"message\": \"LLM响应JSON解析失败，缓存原始响应: {str(e)}\"}}")
            # 缓存原始响应字符串
            self.cache.put(content_for_cache, {"raw_response": result})
            return result

    async def _call_llm_api(self, system_prompt: str, user_prompt: str,
                           model: str, temperature: float, max_tokens: int,
                           session: aiohttp.ClientSession) -> str:
        """实际调用LLM API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }

        try:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=90)  # 增加超时时间
            ) as response:
                response.raise_for_status()
                result = await response.json()

                if "choices" not in result or len(result["choices"]) == 0:
                    raise ValueError("API响应格式异常：缺少choices字段")

                content = result["choices"][0]["message"]["content"]

                # 清理markdown标记
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                logger.debug(f"异步LLM API调用成功，响应长度: {len(content)}")
                return content

        except asyncio.TimeoutError:
            print(f"{{\"timestamp\": \"{datetime.now().isoformat()}\", \"level\": \"ERROR\", \"message\": \"异步LLM API调用超时\"}}")
            raise Exception("异步LLM API调用超时")
        except aiohttp.ClientError as e:
            print(f"{{\"timestamp\": \"{datetime.now().isoformat()}\", \"level\": \"ERROR\", \"message\": \"异步LLM API网络错误: {str(e)}\"}}")
            raise Exception(f"异步LLM API网络错误: {str(e)}")
        except Exception as e:
            print(f"{{\"timestamp\": \"{datetime.now().isoformat()}\", \"level\": \"ERROR\", \"message\": \"异步LLM API调用失败: {str(e)}\"}}")
            # 降级到mock响应
            print(f"{{\"timestamp\": \"{datetime.now().isoformat()}\", \"level\": \"WARNING\", \"message\": \"降级使用mock响应\"}}")
            return self._mock_response(system_prompt, user_prompt)

    def _mock_response(self, system_prompt: str, user_prompt: str) -> str:
        """智能Mock响应，从上下文和grid内容中提取真实的接口名称"""
        logger.debug("使用异步Mock响应")

        # 尝试从用户提示词中提取上下文信息和grid内容
        interface_name = "通用接口"  # 默认名称
        interface_type = "data_display"  # 默认类型

        # 分割用户提示词，提取上下文和grid内容
        parts = user_prompt.split("功能块内容：")
        if len(parts) > 1:
            context_part = parts[0].replace("上下文信息：", "").strip()
            grid_content = parts[1].strip()

            # 从上下文中提取标题（支持多种标题格式）
            context_lines = context_part.split('\n')
            for line in context_lines:
                line = line.strip()
                if line.startswith('### '):
                    interface_name = line[4:].strip()
                    break
                elif line.startswith('## '):
                    interface_name = line[3:].strip()
                    break
                elif line.startswith('# '):
                    interface_name = line[2:].strip()
                    break
                elif line.endswith('：'):
                    interface_name = line[:-1].strip()
                    break
                elif line.endswith(':'):
                    interface_name = line[:-1].strip()
                    break
                elif len(line) < 50 and line and not line.startswith('```') and interface_name == "通用接口":
                    # 短行且非空，可能是标题
                    interface_name = line

            # 如果没有找到标题，尝试从grid内容中提取信息
            if interface_name == "通用接口":
                # 寻找grid内容中的关键信息来命名接口
                if "用户" in grid_content or "user" in grid_content.lower():
                    interface_name = "用户管理" if "管理" in grid_content else "用户信息"
                elif "订单" in grid_content or "order" in grid_content.lower():
                    interface_name = "订单统计" if "统计" in grid_content else "订单管理"
                elif "商品" in grid_content or "product" in grid_content.lower():
                    interface_name = "商品筛选" if "筛选" in grid_content else "商品管理"
                elif "报表" in grid_content or "导出" in grid_content:
                    interface_name = "报表导出"

            # 根据内容推断接口类型
            if "筛选" in grid_content or "过滤" in grid_content or "filter" in grid_content.lower():
                interface_type = "filter_dimension"
            elif "统计" in grid_content or "指标" in grid_content or "metric" in grid_content.lower():
                interface_type = "analytics_metric"
            elif "导出" in grid_content or "报表" in grid_content or "export" in grid_content.lower():
                interface_type = "export_report"
            elif "趋势" in grid_content or "trend" in grid_content.lower():
                interface_type = "trend_analysis"
            elif "概览" in grid_content or "仪表板" in grid_content or "dashboard" in grid_content.lower():
                interface_type = "summary_dashboard"
        else:
            # 回退到原来的简单关键词匹配
            if "用户" in user_prompt and "管理" in user_prompt:
                interface_name = "用户管理"
                interface_type = "data_display"
            elif "订单" in user_prompt and "统计" in user_prompt:
                interface_name = "订单统计"
                interface_type = "analytics_metric"
            elif "商品" in user_prompt and "筛选" in user_prompt:
                interface_name = "商品筛选"
                interface_type = "filter_dimension"
            elif "导出" in user_prompt or "报表" in user_prompt:
                interface_name = "报表导出"
                interface_type = "export_report"

        # 生成基于提取信息的响应
        interface_id = f"api_{interface_name.lower().replace(' ', '_').replace('/', '_')}"

        # 根据接口类型生成相应的字段
        if interface_type == "filter_dimension":
            return f"""{{
  "id": "{interface_id}",
  "name": "{interface_name}",
  "type": "{interface_type}",
  "dimensions": [
    {{"name": "筛选条件", "expression": "filterCondition", "data_type": "string", "required": false}},
    {{"name": "查询参数", "expression": "queryParams", "data_type": "string", "required": false}}
  ],
  "metrics": []
}}"""
        elif interface_type == "analytics_metric":
            return f"""{{
  "id": "{interface_id}",
  "name": "{interface_name}",
  "type": "{interface_type}",
  "dimensions": [
    {{"name": "时间维度", "expression": "timeDimension", "data_type": "date", "required": false}}
  ],
  "metrics": [
    {{"name": "统计数值", "expression": "metricValue", "data_type": "number", "required": false}},
    {{"name": "计数", "expression": "count", "data_type": "number", "required": false}}
  ]
}}"""
        elif interface_type == "export_report":
            return f"""{{
  "id": "{interface_id}",
  "name": "{interface_name}",
  "type": "{interface_type}",
  "dimensions": [
    {{"name": "导出格式", "expression": "exportFormat", "data_type": "string", "required": true}},
    {{"name": "时间范围", "expression": "timeRange", "data_type": "string", "required": false}}
  ],
  "metrics": []
}}"""
        else:
            # 默认data_display类型
            return f"""{{
  "id": "{interface_id}",
  "name": "{interface_name}",
  "type": "{interface_type}",
  "dimensions": [
    {{"name": "查询条件", "expression": "queryCondition", "data_type": "string", "required": false}},
    {{"name": "排序字段", "expression": "sortBy", "data_type": "string", "required": false}}
  ],
  "metrics": [
    {{"name": "显示字段", "expression": "displayField", "data_type": "string", "required": false}}
  ]
}}"""


# 全局异步客户端
_async_client = None


async def get_async_client() -> AsyncDeepSeekClient:
    global _async_client
    if _async_client is None:
        _async_client = AsyncDeepSeekClient()
    return _async_client


def extract_grid_blocks(content: str) -> List[Tuple[str, int]]:
    """提取grid块（复用原有逻辑）"""
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


def extract_context_around_grid(content: str, grid_start: int, context_size: int = 5) -> str:
    """提取grid块周围的上下文，支持多种标题格式"""
    lines = content.split('\n')
    start = max(0, grid_start - context_size)
    end = min(len(lines), grid_start + context_size)

    context_lines = []
    for i in range(start, end):
        if i < grid_start:
            line = lines[i].strip()
            # 支持多种标题格式
            if (line.startswith('#') or line.startswith('##') or
                line.startswith('###') or line.endswith('：') or
                line.endswith(':') or len(line) < 50):  # 短行可能是标题
                context_lines.append(lines[i])
        elif i >= grid_start:
            break

    # 如果没有找到标题行，尝试寻找最近的非空行作为上下文
    if not context_lines:
        for i in range(start, grid_start):
            line = lines[i].strip()
            if line and not line.startswith('```'):
                context_lines.append(lines[i])
                break

    return '\n'.join(context_lines)


# 异步接口解析提示词
ASYNC_INTERFACE_SYSTEM_PROMPT = """你是一个智能接口解析器，专门解析产品设计文档中的单个功能块，生成接口语义模型。

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
1. 解析这个功能块的内容
2. 识别接口类型
3. 提取字段信息
4. 生成单个接口的JSON

接口类型识别规则：
- **filter_dimension**: 包含筛选条件、过滤字段、查询参数的功能块
- **data_display**: 展示数据列表、明细、表格内容的功能块
- **analytics_metric**: 包含指标、统计、计算值的功能块
- **trend_analysis**: 包含时间序列、趋势图、对比分析的功能块
- **summary_dashboard**: 综合概览、汇总信息、仪表板功能块
- **export_report**: 导出、报表、下载相关的功能块
- **configuration**: 配置设置、参数管理相关的功能块
- **custom_action**: 自定义操作、特殊业务逻辑的功能块

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


async def parse_single_interface_async(grid_block_with_context: Tuple[str, str, int],
                                      session: aiohttp.ClientSession, retry_count: int = 3) -> Dict[str, Any]:
    """异步解析单个grid块为接口定义，带重试机制"""
    grid_content, context, block_index = grid_block_with_context
    start_time = time.time()

    for attempt in range(retry_count):
        try:
            # 构建用户提示词
            user_prompt = f"""请解析下面这个功能块，生成对应的接口定义。

上下文信息：
{context}

功能块内容：
{grid_content}

请根据功能块的内容智能识别接口类型，并提取字段信息。输出JSON格式。"""

            # 异步调用LLM
            client = await get_async_client()
            response = await client.call_llm_async(
                system_prompt=ASYNC_INTERFACE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                session=session,
                max_tokens=3000  # 增加token限制
            )

            processing_time = time.time() - start_time

            # 解析响应
            try:
                interface_data = json.loads(response)
                interface_data['_block_index'] = block_index
                interface_data['_grid_content'] = grid_content
                interface_data['_processing_time'] = processing_time
                interface_data['_attempt'] = attempt + 1

                logger.debug(f"Block {block_index} 解析成功，耗时: {processing_time:.2f}s，尝试次数: {attempt + 1}")
                return interface_data

            except json.JSONDecodeError as e:
                print(f"{{\"timestamp\": \"{datetime.now().isoformat()}\", \"level\": \"WARNING\", \"message\": \"Block {block_index} 第{attempt + 1}次尝试JSON解析失败: {str(e)}\"}}")
                if attempt == retry_count - 1:  # 最后一次尝试
                    return {
                        "error": f"JSON解析失败 (尝试{retry_count}次): {str(e)}",
                        "_block_index": block_index,
                        "_grid_content": grid_content,
                        "_raw_response": response,
                        "_processing_time": processing_time,
                        "_attempt": attempt + 1
                    }
                continue  # 继续重试

        except asyncio.TimeoutError:
            print(f"{{\"timestamp\": \"{datetime.now().isoformat()}\", \"level\": \"WARNING\", \"message\": \"Block {block_index} 第{attempt + 1}次尝试超时\"}}")
            if attempt == retry_count - 1:
                return {
                    "error": f"处理超时 (尝试{retry_count}次)",
                    "_block_index": block_index,
                    "_grid_content": grid_content,
                    "_processing_time": time.time() - start_time,
                    "_attempt": attempt + 1
                }
            # 超时后等待一下再重试
            await asyncio.sleep(1 * (attempt + 1))

        except Exception as e:
            print(f"{{\"timestamp\": \"{datetime.now().isoformat()}\", \"level\": \"WARNING\", \"message\": \"Block {block_index} 第{attempt + 1}次尝试发生错误: {str(e)}\"}}")
            if attempt == retry_count - 1:
                return {
                    "error": f"处理失败 (尝试{retry_count}次): {str(e)}",
                    "_block_index": block_index,
                    "_grid_content": grid_content,
                    "_processing_time": time.time() - start_time,
                    "_attempt": attempt + 1
                }
            # 发生错误后等待一下再重试
            await asyncio.sleep(0.5 * (attempt + 1))

    # 不应该到达这里，但作为保险
    return {
        "error": "未知错误",
        "_block_index": block_index,
        "_grid_content": grid_content,
        "_processing_time": time.time() - start_time,
        "_attempt": retry_count
    }


async def parse_interfaces_chunk_async(chunk_content: str, chunk_index: int) -> List[Dict[str, Any]]:
    """异步解析一个文档块中的所有接口"""
    grid_blocks = extract_grid_blocks(chunk_content)

    if not grid_blocks:
        return []

    # 准备异步处理的参数
    parse_tasks = []
    for i, (grid_content, grid_start) in enumerate(grid_blocks):
        context = extract_context_around_grid(chunk_content, grid_start)
        block_index = chunk_index * 10 + i
        parse_tasks.append((grid_content, context, block_index))

    # 创建异步HTTP会话
    async with aiohttp.ClientSession() as session:
        # 并发处理所有接口
        tasks = [
            parse_single_interface_async(task, session)
            for task in parse_tasks
        ]

        # 等待所有任务完成
        interfaces = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常结果
        valid_interfaces = []
        for i, result in enumerate(interfaces):
            if isinstance(result, Exception):
                print(f"{{\"timestamp\": \"{datetime.now().isoformat()}\", \"level\": \"ERROR\", \"message\": \"异步处理接口时发生异常: {str(result)}\"}}")
                valid_interfaces.append({
                    "error": str(result),
                    "_block_index": parse_tasks[i][2],
                    "_grid_content": parse_tasks[i][0]
                })
            else:
                valid_interfaces.append(result)

        return valid_interfaces


async def understand_doc_async(state: AgentState) -> AgentState:
    """异步版本的文档理解节点"""
    trace_id = state["trace_id"]
    step_name = "understand_doc_async"

    
    # 获取输入数据
    raw_docs = state["raw_docs"]
    feishu_urls = state.get("feishu_urls", [])

    logger.start(trace_id, step_name, "开始异步并行解析多个文档内容",
                extra={
                    "docs_count": len(raw_docs),
                    "total_length": sum(len(doc) for doc in raw_docs)
                })

    try:
        # 1. 合并多个文档内容
        combined_content = ""
        for i, doc in enumerate(raw_docs):
            combined_content += f"\n\n=== 文档 {i+1} ===\n{doc}"

        # 2. 准备文档元数据
        doc_meta = {
            "title": "异步解析文档",
            "url": feishu_urls[0] if feishu_urls else "",
            "version": "latest",
            "parsing_mode": "async_parallel"
        }

        # 尝试从文档中提取标题
        lines = combined_content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                doc_meta["title"] = line[2:].strip()
                break

        # 3. 检查文档中是否有grid块
        # progress:30, "正在检查文档中的表格块...")
        grid_blocks = extract_grid_blocks(combined_content)

        if not grid_blocks:
            logger.warning(trace_id, step_name, "文档中没有发现grid块，使用原有逻辑")
                        # 回退到同步逻辑
            from nodes.understand_doc import understand_doc
            return understand_doc(state)

        # progress:40, f"发现 {len(grid_blocks)} 个表格块，开始异步并行处理")
        logger.info(trace_id, step_name, f"发现 {len(grid_blocks)} 个grid块，开始异步并行处理",
                   extra={"grid_blocks_count": len(grid_blocks)})

        # 4. 分割文档为处理块（更小的块，更好的并发）
        # progress:50, "正在分割文档为处理块...")
        chunk_size = 1  # 每个块只包含1个grid块，最大化并发
        chunks = []
        for grid_content, grid_start in grid_blocks:
            context = extract_context_around_grid(combined_content, grid_start)
            chunk = f"{context}\n\n{grid_content}"
            chunks.append(chunk)

        logger.info(trace_id, step_name, f"文档分割为 {len(chunks)} 个块进行异步并行处理",
                   extra={"chunks_count": len(chunks)})

        # 5. 异步并行处理所有块
        # progress:60, "开始异步并行处理所有文档块...")
        all_interfaces = []

        # 并发处理所有块
        chunk_tasks = [
            parse_interfaces_chunk_async(chunk, i)
            for i, chunk in enumerate(chunks)
        ]

        # 等待所有块处理完成
        # progress:70, "正在等待所有文档块处理完成...")
        chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)

        # 合并结果
        for i, result in enumerate(chunk_results):
            if isinstance(result, Exception):
                logger.error(trace_id, step_name, f"块 {i} 处理失败: {str(result)}")
                all_interfaces.append({
                    "error": f"块处理失败: {str(result)}",
                    "_block_index": i * 100,
                    "_grid_content": chunks[i][:500] + "..." if len(chunks[i]) > 500 else chunks[i]
                })
            else:
                all_interfaces.extend(result)
                logger.info(trace_id, step_name, f"块 {i} 处理完成，解析出 {len(result)} 个接口")

        # progress:80, f"异步块处理完成，共解析出 {len(all_interfaces)} 个接口")
        logger.info(trace_id, step_name, f"所有异步块处理完成，共解析出 {len(all_interfaces)} 个接口",
                   extra={"total_interfaces": len(all_interfaces)})

        # 6. 合并接口为完整的ISM
        # progress:90, "正在合并接口为完整的语义模型...")
        ism = merge_interfaces_to_ism(all_interfaces, doc_meta)

        # 7. 写入state
        result_state = state.copy()
        result_state["ism_raw"] = ism

        # 完成进度追踪
        # progress completed: 异步ISM生成完成，解析出 {len(ism.get('interfaces', []))} 个接口

        logger.end(trace_id, step_name, "异步并行ISM生成完成",
                  extra={
                      "interfaces_count": len(ism.get("interfaces", [])),
                      "pending_count": len(ism.get("__pending__", [])),
                      "doc_title": ism["doc_meta"].get("title", "未知"),
                      "processed_docs": len(raw_docs),
                      "grid_blocks_found": len(grid_blocks),
                      "async_chunks": len(chunks)
                  })

        return result_state

    except Exception as e:
        # 错误进度追踪
        logger.error(trace_id, step_name, "异步ISM生成过程中发生错误", extra={"error": str(e)})

        # 构造错误兜底ISM
        fallback_ism = {
            "doc_meta": {
                "title": "异步处理出错的文档",
                "url": feishu_urls[0] if feishu_urls else "",
                "version": "latest",
                "parsing_mode": "async_parallel_failed"
            },
            "interfaces": [],
            "__pending__": [
                f"异步处理过程中发生错误: {str(e)}",
                "需要人工检查和补全或回退到同步处理模式"
            ]
        }

        result_state = state.copy()
        result_state["ism_raw"] = fallback_ism

        logger.end(trace_id, step_name, "ISM生成完成（错误兜底）",
                  extra={
                      "interfaces_count": 0,
                      "pending_count": len(fallback_ism["__pending__"])
                  })

        return result_state


def merge_interfaces_to_ism(interfaces: List[Dict[str, Any]], doc_meta: Dict[str, Any]) -> Dict[str, Any]:
    """合并接口为ISM（复用原有逻辑）"""
    ism = {
        "doc_meta": doc_meta,
        "interfaces": [],
        "__pending__": []
    }

    successful_interfaces = []
    pending_items = []

    for interface in interfaces:
        if "error" in interface:
            pending_items.append(f"接口解析失败 (Block {interface.get('_block_index', 'unknown')}): {interface['error']}")
            if '_grid_content' in interface:
                pending_items.append(f"原始内容: {interface['_grid_content'][:200]}...")
        elif not interface.get("id"):
            pending_items.append(f"接口缺少ID (Block {interface.get('_block_index', 'unknown')})")
            if '_grid_content' in interface:
                pending_items.append(f"原始内容: {interface['_grid_content'][:200]}...")
        else:
            clean_interface = {k: v for k, v in interface.items()
                             if not k.startswith('_') and k != "error"}
            successful_interfaces.append(clean_interface)

    successful_interfaces.sort(key=lambda x: x.get('_block_index', 0))
    for interface in successful_interfaces:
        interface.pop('_block_index', None)

    ism["interfaces"] = successful_interfaces
    ism["__pending__"] = pending_items

    return ism


# 兼容性函数
def understand_doc(state: AgentState) -> AgentState:
    """同步包装器，用于兼容现有接口"""
    try:
        # 尝试获取当前事件循环
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果已经在事件循环中，需要在新线程中运行
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, understand_doc_async(state))
                return future.result()
        else:
            # 如果没有事件循环，直接运行
            return asyncio.run(understand_doc_async(state))
    except Exception as e:
        logger.error(state["trace_id"], "understand_doc", f"异步处理失败，回退到同步模式: {str(e)}")
        # 回退到同步模式
        from nodes.understand_doc_parallel import understand_doc_parallel
        return understand_doc_parallel(state)