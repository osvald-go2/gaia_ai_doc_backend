#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级流式处理版本
支持实时进度反馈、增量结果输出和动态负载均衡
"""

import asyncio
import aiohttp
import json
import time
from typing import List, Dict, Any, Tuple, AsyncGenerator, Optional
from dataclasses import dataclass
from models.state import AgentState
from utils.logger import logger
from utils.llm_cache import get_llm_cache
from utils.batch_optimizer import get_batch_optimizer


@dataclass
class ProcessingProgress:
    """处理进度信息"""
    total_interfaces: int
    completed_interfaces: int
    current_chunk: int
    current_interface: str
    processing_time: float
    estimated_remaining_time: float
    partial_results: List[Dict[str, Any]]
    cache_hit_rate: float
    error_count: int


class StreamingProcessorV2:
    """高级流式处理器"""

    def __init__(self):
        self.batch_optimizer = get_batch_optimizer()
        self.cache = get_llm_cache()
        self.start_time = None
        self.interface_times = []  # 记录每个接口的处理时间

    async def process_with_progress_and_feedback(
        self, content: str, trace_id: str
    ) -> AsyncGenerator[ProcessingProgress, None]:
        """
        带进度反馈和动态负载均衡的异步处理
        """
        self.start_time = time.time()

        # 提取grid块
        grid_blocks = self._extract_grid_blocks(content)
        total_interfaces = len(grid_blocks)

        logger.info(trace_id, "streaming_v2", f"开始流式处理 {total_interfaces} 个接口")

        # 获取动态优化配置
        config = self.batch_optimizer.optimize_config(content, grid_blocks, "aggressive")

        # 创建动态分块策略
        chunks = self._create_adaptive_chunks(grid_blocks, config)

        # 初始化进度
        progress = ProcessingProgress(
            total_interfaces=total_interfaces,
            completed_interfaces=0,
            current_chunk=0,
            current_interface="",
            processing_time=0,
            estimated_remaining_time=0,
            partial_results=[],
            cache_hit_rate=0.0,
            error_count=0
        )

        # 实时处理进度统计
        cache_hits = 0
        total_requests = 0

        # 处理每个块
        completed_interfaces = 0
        for chunk_idx, chunk in enumerate(chunks):
            progress.current_chunk = chunk_idx + 1
            progress.current_interface = f"处理块 {chunk_idx + 1}/{len(chunks)}"

            # 发送进度更新
            yield progress

            # 动态调整并发数
            current_workers = self._adjust_workers_dynamically(chunk_idx, len(chunks), config)

            # 处理当前块
            chunk_interfaces = await self._process_chunk_with_load_balancing(
                chunk, chunk_idx, trace_id, current_workers
            )

            # 更新统计
            for interface in chunk_interfaces:
                if "_processing_time" in interface:
                    self.interface_times.append(interface["_processing_time"])

                if "_cache_hit" in interface and interface["_cache_hit"]:
                    cache_hits += 1
                total_requests += 1

            progress.partial_results.extend(chunk_interfaces)
            completed_interfaces += len(chunk_interfaces)

            # 更新进度
            progress.completed_interfaces = completed_interfaces
            progress.processing_time = time.time() - self.start_time
            progress.cache_hit_rate = cache_hits / total_requests if total_requests > 0 else 0

            # 估算剩余时间（基于历史平均时间）
            if self.interface_times:
                avg_time_per_interface = sum(self.interface_times[-10:]) / min(len(self.interface_times), 10)
                remaining_interfaces = total_interfaces - completed_interfaces
                progress.estimated_remaining_time = avg_time_per_interface * remaining_interfaces

            logger.info(trace_id, "streaming_v2",
                       f"完成块 {chunk_idx + 1}/{len(chunks)}, "
                       f"解析出 {len(chunk_interfaces)} 个接口, "
                       f"累计 {completed_interfaces}/{total_interfaces}, "
                       f"缓存命中率: {progress.cache_hit_rate:.2f}")

        # 最终进度
        progress.current_interface = "处理完成"
        progress.estimated_remaining_time = 0
        yield progress

    def _adjust_workers_dynamically(self, chunk_idx: int, total_chunks: int, config) -> int:
        """动态调整并发数"""
        # 基于处理进度和系统负载动态调整
        if chunk_idx < total_chunks // 3:
            # 前期：使用最大并发
            return config.max_workers
        elif chunk_idx < 2 * total_chunks // 3:
            # 中期：稍微降低并发
            return max(config.max_workers - 1, config.max_workers // 2)
        else:
            # 后期：使用保守并发
            return max(config.max_workers // 2, 2)

    async def _process_chunk_with_load_balancing(
        self, chunk: List[Tuple[str, int, str]], chunk_idx: int, trace_id: str, max_workers: int
    ) -> List[Dict[str, Any]]:
        """带负载均衡的块处理"""
        if not chunk:
            return []

        # 创建HTTP会话池
        connector = aiohttp.TCPConnector(limit=max_workers, limit_per_host=max_workers)
        timeout = aiohttp.ClientTimeout(total=90, connect=30)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # 创建信号量控制并发数
            semaphore = asyncio.Semaphore(max_workers)

            # 创建任务
            tasks = [
                self._process_single_interface_with_semaphore(
                    task, session, semaphore, trace_id
                ) for task in chunk
            ]

            # 并发执行所有任务
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理异常结果
            valid_interfaces = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(trace_id, "streaming_v2", f"接口处理异常: {str(result)}")
                    valid_interfaces.append({
                        "error": str(result),
                        "_block_index": chunk[i][2],
                        "_grid_content": chunk[i][0]
                    })
                else:
                    valid_interfaces.append(result)

            return valid_interfaces

    async def _process_single_interface_with_semaphore(
        self, grid_block_with_context: Tuple[str, str, int],
        session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, trace_id: str
    ) -> Dict[str, Any]:
        """带信号量控制的单个接口处理"""
        async with semaphore:
            grid_content, context, block_index = grid_block_with_context
            start_time = time.time()

            try:
                # 构建用户提示词
                user_prompt = f"""请解析下面这个功能块，生成对应的接口定义。

上下文信息：
{context}

功能块内容：
{grid_content}

请根据功能块的内容智能识别接口类型，并提取字段信息。输出JSON格式。"""

                # 尝试从缓存获取
                content_for_cache = f"{self.get_system_prompt()}\n\n{user_prompt}"
                cached_result = self.cache.get(content_for_cache)
                processing_time = time.time() - start_time

                if cached_result:
                    logger.debug(trace_id, "streaming_v2", f"Block {block_index} 缓存命中")
                    cached_result["_block_index"] = block_index
                    cached_result["_grid_content"] = grid_content
                    cached_result["_processing_time"] = processing_time
                    cached_result["_cache_hit"] = True
                    return cached_result

                # 缓存未命中，调用LLM
                from nodes.understand_doc_async import get_async_client
                client = await get_async_client()
                response = await client.call_llm_async(
                    system_prompt=self.get_system_prompt(),
                    user_prompt=user_prompt,
                    session=session,
                    max_tokens=3000
                )

                processing_time = time.time() - start_time

                # 解析响应
                try:
                    interface_data = json.loads(response)
                    interface_data['_block_index'] = block_index
                    interface_data['_grid_content'] = grid_content
                    interface_data['_processing_time'] = processing_time
                    interface_data['_cache_hit'] = False

                    # 缓存结果
                    self.cache.put(content_for_cache, interface_data)

                    logger.debug(trace_id, "streaming_v2",
                               f"Block {block_index} 解析成功，耗时: {processing_time:.2f}s")
                    return interface_data

                except json.JSONDecodeError as e:
                    logger.warning(trace_id, "streaming_v2",
                                 f"Block {block_index} JSON解析失败: {str(e)}")
                    return {
                        "error": f"JSON解析失败: {str(e)}",
                        "_block_index": block_index,
                        "_grid_content": grid_content,
                        "_raw_response": response,
                        "_processing_time": processing_time,
                        "_cache_hit": False
                    }

            except Exception as e:
                processing_time = time.time() - start_time
                logger.error(trace_id, "streaming_v2", f"Block {block_index} 处理失败: {str(e)}")
                return {
                    "error": str(e),
                    "_block_index": block_index,
                    "_grid_content": grid_content,
                    "_processing_time": processing_time,
                    "_cache_hit": False
                }

    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个智能接口解析器，专门解析产品设计文档中的单个功能块，生成接口语义模型。

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

    def _extract_grid_blocks(self, content: str) -> List[Tuple[str, int]]:
        """提取grid块"""
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

    def _create_adaptive_chunks(self, grid_blocks: List[Tuple[str, int]], config) -> List[List[Tuple[str, int, str]]]:
        """创建自适应分块策略"""
        chunks = []
        current_chunk = []
        current_chunk_size = 0

        # 根据系统负载和文档复杂度调整块大小
        if len(grid_blocks) <= 3:
            chunk_size = 1  # 小文档，每块1个接口
        elif len(grid_blocks) <= 10:
            chunk_size = 2  # 中等文档，每块2个接口
        else:
            chunk_size = 3  # 大文档，每块3个接口

        for i, (grid_content, grid_start) in enumerate(grid_blocks):
            # 提取上下文
            context = self._extract_context(grid_content, grid_start)
            current_chunk.append((grid_content, grid_start, context))
            current_chunk_size += 1

            if current_chunk_size >= chunk_size:
                chunks.append(current_chunk)
                current_chunk = []
                current_chunk_size = 0

        # 添加最后一个不完整的块
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _extract_context(self, content: str, grid_start: int) -> str:
        """提取上下文"""
        lines = content.split('\n')
        start = max(0, grid_start - 5)

        context_lines = []
        for i in range(start, grid_start):
            line = lines[i].strip()
            if line.startswith('#') or line.startswith('##'):
                context_lines.append(lines[i])

        return '\n'.join(context_lines)


async def understand_doc_streaming_v2(state: AgentState) -> AgentState:
    """
    高级流式处理版本的文档理解节点
    """
    trace_id = state["trace_id"]
    step_name = "understand_doc_streaming_v2"

    # 获取输入数据
    raw_docs = state["raw_docs"]
    feishu_urls = state.get("feishu_urls", [])

    logger.start(trace_id, step_name, "开始高级流式文档理解处理",
                extra={
                    "docs_count": len(raw_docs),
                    "total_length": sum(len(doc) for doc in raw_docs)
                })

    try:
        # 合并文档内容
        combined_content = ""
        for i, doc in enumerate(raw_docs):
            combined_content += f"\n\n=== 文档 {i+1} ===\n{doc}"

        # 创建流式处理器
        processor = StreamingProcessorV2()

        # 准备文档元数据
        doc_meta = {
            "title": "高级流式解析文档",
            "url": feishu_urls[0] if feishu_urls else "",
            "version": "latest",
            "parsing_mode": "streaming_v2"
        }

        # 提取标题
        lines = combined_content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                doc_meta["title"] = line[2:].strip()
                break

        # 流式处理
        all_interfaces = []
        processing_start_time = time.time()

        async for progress in processor.process_with_progress_and_feedback(combined_content, trace_id):
            # 可以在这里发送进度信息到客户端或监控系统
            logger.info(trace_id, step_name,
                       f"处理进度: {progress.completed_interfaces}/{progress.total_interfaces} "
                       f"({progress.completed_interfaces/progress.total_interfaces*100:.1f}%), "
                       f"缓存命中率: {progress.cache_hit_rate:.2f}, "
                       f"错误数: {progress.error_count}")

            all_interfaces = progress.partial_results.copy()

        # 处理完成
        total_time = time.time() - processing_start_time
        logger.info(trace_id, step_name, f"高级流式处理完成，总时间: {total_time:.2f}s")

        # 记录性能数据
        from utils.batch_optimizer import ProcessingConfig
        config = ProcessingConfig(chunk_size=2, max_workers=5, timeout_seconds=60, batch_mode="balanced")
        processor.batch_optimizer.record_performance(
            config, total_time, len(all_interfaces), len(all_interfaces)
        )

        # 合并结果为ISM
        ism = merge_interfaces_to_ism(all_interfaces, doc_meta)

        # 写入state
        result_state = state.copy()
        result_state["ism"] = ism

        logger.end(trace_id, step_name, "高级流式ISM生成完成",
                  extra={
                      "interfaces_count": len(ism.get("interfaces", [])),
                      "pending_count": len(ism["__pending__"]),
                      "doc_title": ism["doc_meta"].get("title", "未知"),
                      "processing_time": total_time,
                      "cache_hit_rate": processor.cache.get_stats().get("avg_hits_per_entry", 0)
                  })

        return result_state

    except Exception as e:
        logger.error(trace_id, step_name, "高级流式ISM生成过程中发生错误", extra={"error": str(e)})

        # 构造错误兜底ISM
        fallback_ism = {
            "doc_meta": {
                "title": "高级流式处理出错的文档",
                "url": feishu_urls[0] if feishu_urls else "",
                "version": "latest",
                "parsing_mode": "streaming_v2_failed"
            },
            "interfaces": [],
            "__pending__": [
                f"高级流式处理过程中发生错误: {str(e)}",
                "需要人工检查和补全或回退到异步处理模式"
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


def merge_interfaces_to_ism(interfaces: List[Dict[str, Any]], doc_meta: Dict[str, Any]) -> Dict[str, Any]:
    """合并接口为ISM"""
    ism = {
        "doc_meta": doc_meta,
        "interfaces": [],
        "__pending__": []
    }

    successful_interfaces = []
    pending_items = []

    for interface in interfaces:
        if "error" in interface:
            pending_items.append(f"接口解析失败: {interface['error']}")
        elif not interface.get("id"):
            pending_items.append("接口缺少ID")
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
    """同步包装器"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, understand_doc_streaming_v2(state))
                return future.result()
        else:
            return asyncio.run(understand_doc_streaming_v2(state))
    except Exception as e:
        logger.error(state["trace_id"], "understand_doc", f"高级流式处理失败，回退到异步模式: {str(e)}")
        from nodes.understand_doc_async import understand_doc_async
        return understand_doc_async(state)