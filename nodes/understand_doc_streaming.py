#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流式处理版本的文档理解节点
支持实时进度反馈和增量结果输出
"""

import asyncio
import json
import time
from typing import List, Dict, Any, Tuple, AsyncGenerator, Optional
from dataclasses import dataclass
from models.state import AgentState
from utils.logger import logger
from utils.batch_optimizer import get_batch_optimizer, ProcessingConfig
from utils.llm_cache import get_llm_cache


@dataclass
class ProcessingProgress:
    """处理进度信息"""
    total_chunks: int
    completed_chunks: int
    current_chunk: int
    current_interface: str
    processing_time: float
    estimated_remaining_time: float
    partial_results: List[Dict[str, Any]]


class StreamingProcessor:
    """流式处理器"""

    def __init__(self):
        self.batch_optimizer = get_batch_optimizer()
        self.cache = get_llm_cache()
        self.start_time = None

    async def process_with_progress(self, content: str, trace_id: str) -> AsyncGenerator[ProcessingProgress, None]:
        """带进度反馈的异步处理"""
        self.start_time = time.time()

        # 提取grid块
        grid_blocks = self._extract_grid_blocks(content)
        total_interfaces = len(grid_blocks)

        logger.info(trace_id, "streaming_process", f"开始流式处理 {total_interfaces} 个接口")

        # 获取优化配置
        config = self.batch_optimizer.optimize_config(content, grid_blocks)

        # 分割处理块
        chunks = self._create_chunks(grid_blocks, config.chunk_size)

        # 初始化进度
        progress = ProcessingProgress(
            total_chunks=len(chunks),
            completed_chunks=0,
            current_chunk=0,
            current_interface="",
            processing_time=0,
            estimated_remaining_time=0,
            partial_results=[]
        )

        # 处理每个块
        completed_interfaces = 0
        for chunk_idx, chunk in enumerate(chunks):
            progress.current_chunk = chunk_idx + 1
            progress.current_interface = f"处理块 {chunk_idx + 1}/{len(chunks)}"

            # 发送进度更新
            yield progress

            # 处理当前块
            chunk_interfaces = await self._process_chunk(chunk, chunk_idx, trace_id)
            progress.partial_results.extend(chunk_interfaces)

            # 更新进度
            progress.completed_chunks = chunk_idx + 1
            completed_interfaces += len(chunk_interfaces)
            progress.processing_time = time.time() - self.start_time

            # 估算剩余时间
            if progress.completed_chunks > 0:
                avg_time_per_chunk = progress.processing_time / progress.completed_chunks
                remaining_chunks = progress.total_chunks - progress.completed_chunks
                progress.estimated_remaining_time = avg_time_per_chunk * remaining_chunks

            logger.info(trace_id, "streaming_process",
                       f"完成块 {chunk_idx + 1}/{len(chunks)}, "
                       f"解析出 {len(chunk_interfaces)} 个接口, "
                       f"累计 {completed_interfaces}/{total_interfaces}")

        # 最终进度
        progress.current_interface = "处理完成"
        progress.estimated_remaining_time = 0
        yield progress

    async def _process_chunk(self, chunk: List[Tuple[str, int, str]], chunk_idx: int, trace_id: str) -> List[Dict[str, Any]]:
        """处理单个块"""
        interfaces = []

        # 并发处理块中的所有接口
        tasks = []
        for grid_content, grid_start, context in chunk:
            task = self._process_single_interface(grid_content, context, trace_id)
            tasks.append(task)

        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(trace_id, "streaming_process", f"接口处理异常: {str(result)}")
                interfaces.append({
                    "error": str(result),
                    "_block_index": chunk_idx * 10 + i,
                    "_grid_content": chunk[i][0]
                })
            else:
                interfaces.append(result)

        return interfaces

    async def _process_single_interface(self, grid_content: str, context: str, trace_id: str) -> Dict[str, Any]:
        """处理单个接口（带缓存）"""
        content = f"{context}\n\n{grid_content}"

        # 尝试从缓存获取
        cached_result = self.cache.get(content)
        if cached_result:
            logger.debug(trace_id, "streaming_process", "缓存命中")
            return cached_result

        # 缓存未命中，调用LLM
        try:
            from utils.llm_cache import get_llm_cache
            cache = get_llm_cache()

            def call_llm():
                # 这里应该调用实际的LLM
                # 为了示例，返回模拟结果
                return {
                    "id": "api_streaming_interface",
                    "name": "流式接口",
                    "type": "data_display",
                    "dimensions": [
                        {"name": "字段1", "expression": "field1", "data_type": "string", "required": False}
                    ],
                    "metrics": []
                }

            result = cache.llm_cache_function(content, call_llm)
            return result

        except Exception as e:
            logger.error(trace_id, "streaming_process", f"LLM调用失败: {str(e)}")
            return {
                "error": str(e),
                "_grid_content": grid_content
            }

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

    def _create_chunks(self, grid_blocks: List[Tuple[str, int]], chunk_size: int) -> List[List[Tuple[str, int, str]]]:
        """创建处理块"""
        chunks = []
        current_chunk = []

        for i, (grid_content, grid_start) in enumerate(grid_blocks):
            # 提取上下文
            context = self._extract_context(grid_content, grid_start)
            current_chunk.append((grid_content, grid_start, context))

            if len(current_chunk) >= chunk_size:
                chunks.append(current_chunk)
                current_chunk = []

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


async def understand_doc_streaming(state: AgentState) -> AgentState:
    """流式处理版本的文档理解节点"""
    trace_id = state["trace_id"]
    step_name = "understand_doc_streaming"

    # 获取输入数据
    raw_docs = state["raw_docs"]
    feishu_urls = state.get("feishu_urls", [])

    logger.start(trace_id, step_name, "开始流式文档理解处理",
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
        processor = StreamingProcessor()

        # 准备文档元数据
        doc_meta = {
            "title": "流式解析文档",
            "url": feishu_urls[0] if feishu_urls else "",
            "version": "latest",
            "parsing_mode": "streaming"
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

        async for progress in processor.process_with_progress(combined_content, trace_id):
            # 可以在这里发送进度信息到客户端
            logger.info(trace_id, step_name,
                       f"处理进度: {progress.completed_chunks}/{progress.total_chunks} "
                       f"({progress.completed_chunks/progress.total_chunks*100:.1f}%), "
                       f"预计剩余时间: {progress.estimated_remaining_time:.1f}s")

            # 更新部分结果
            all_interfaces = progress.partial_results.copy()

        # 处理完成
        total_time = time.time() - processing_start_time
        logger.info(trace_id, step_name, f"流式处理完成，总时间: {total_time:.2f}s")

        # 记录性能数据
        config = ProcessingConfig(chunk_size=2, max_workers=5, timeout_seconds=60, batch_mode="balanced")
        processor.batch_optimizer.record_performance(
            config, total_time, len(all_interfaces), len(all_interfaces)
        )

        # 合并结果为ISM
        ism = merge_interfaces_to_ism(all_interfaces, doc_meta)

        # 写入state
        result_state = state.copy()
        result_state["ism"] = ism

        logger.end(trace_id, step_name, "流式ISM生成完成",
                  extra={
                      "interfaces_count": len(ism.get("interfaces", [])),
                      "pending_count": len(ism["__pending__"]),
                      "doc_title": ism["doc_meta"].get("title", "未知"),
                      "processing_time": total_time
                  })

        return result_state

    except Exception as e:
        logger.error(trace_id, step_name, "流式ISM生成过程中发生错误", extra={"error": str(e)})

        # 构造错误兜底ISM
        fallback_ism = {
            "doc_meta": {
                "title": "流式处理出错的文档",
                "url": feishu_urls[0] if feishu_urls else "",
                "version": "latest",
                "parsing_mode": "streaming_failed"
            },
            "interfaces": [],
            "__pending__": [
                f"流式处理过程中发生错误: {str(e)}",
                "需要人工检查和补全"
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
                future = executor.submit(asyncio.run, understand_doc_streaming(state))
                return future.result()
        else:
            return asyncio.run(understand_doc_streaming(state))
    except Exception as e:
        logger.error(state["trace_id"], "understand_doc", f"流式处理失败，回退到并行模式: {str(e)}")
        from nodes.understand_doc_parallel import understand_doc_parallel
        return understand_doc_parallel(state)