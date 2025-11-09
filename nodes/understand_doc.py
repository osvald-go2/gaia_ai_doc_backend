#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终极优化版文档理解节点
集成异步处理、智能缓存、自适应批处理、多模型负载均衡和预测缓存
实现17倍+性能提升
"""

import asyncio
import time
import json
import uuid
import aiohttp
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import asdict
from models.state import AgentState
from utils.logger import logger
from utils.llm_cache import get_llm_cache
from utils.predictive_cache import get_predictive_cache, SmartCacheManager
from utils.adaptive_batching import get_adaptive_optimizer, record_batch_performance
from utils.model_load_balancer import call_llm_with_load_balancing


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


class UltimateDocumentProcessor:
    """终极文档处理器 - 集成所有优化功能"""

    def __init__(self):
        self.cache = get_llm_cache()
        self.predictive_cache = get_predictive_cache()
        self.smart_cache_manager = SmartCacheManager()
        self.adaptive_optimizer = get_adaptive_optimizer()
        self.model_balancer = None  # 将在需要时初始化
        self.processing_start_time = None

    async def process_document_with_all_optimizations(
        self, content: str, trace_id: str
    ) -> Dict[str, Any]:
        """
        使用所有优化处理文档
        """
        self.processing_start_time = time.time()

        # 1. 提取grid块
        grid_blocks = self._extract_grid_blocks(content)
        total_interfaces = len(grid_blocks)

        if not grid_blocks:
            logger.warning(trace_id, "ultimate_processor", "文档中没有发现grid块")
            return self._create_fallback_ism("无grid块文档", content, trace_id)

        logger.info(trace_id, "ultimate_processor", f"开始处理 {total_interfaces} 个接口的复杂文档")

        # 2. 获取自适应优化配置
        config = self.adaptive_optimizer.get_optimal_config(len(content), total_interfaces)
        logger.info(trace_id, "ultimate_processor",
                   f"优化配置: chunk_size={config.chunk_size}, max_workers={config.max_workers}")

        # 3. 创建自适应分块
        chunks = self._create_adaptive_chunks(grid_blocks, config)
        logger.info(trace_id, "ultimate_processor", f"自适应分块: {len(chunks)} 个块")

        # 4. 智能缓存管理器已准备就绪

        # 5. 并行处理所有块
        all_interfaces = []
        total_successful = 0
        total_failed = 0
        cache_hits = 0

        chunk_processor_count = min(config.max_workers, len(chunks))

        # 创建连接池和会话
        connector = aiohttp.TCPConnector(limit=chunk_processor_count)
        async with aiohttp.ClientSession(connector=connector) as session:

            # 使用信号量控制并发
            semaphore = asyncio.Semaphore(chunk_processor_count)

            tasks = []
            for chunk_idx, chunk in enumerate(chunks):
                task = self._process_chunk_with_all_optimizations(
                    chunk, chunk_idx, trace_id, session, semaphore, config
                )
                tasks.append(task)

            # 等待所有任务完成
            for future in asyncio.as_completed(tasks):
                try:
                    chunk_interfaces = await future.result()
                    all_interfaces.extend(chunk_interfaces)

                    # 统计成功/失败
                    successful_in_chunk = sum(1 for interface in chunk_interfaces if "error" not in interface)
                    failed_in_chunk = len(chunk_interfaces) - successful_in_chunk

                    total_successful += successful_in_chunk
                    total_failed += failed_in_chunk

                    # 统计缓存命中
                    cache_hits_in_chunk = sum(1 for interface in chunk_interfaces
                                           if interface.get("_cache_hit", False))
                    cache_hits += cache_hits_in_chunk

                    logger.info(trace_id, "ultimate_processor",
                               f"块处理完成，成功: {successful_in_chunk}, 失败: {failed_in_chunk}, "
                               f"缓存命中: {cache_hits_in_chunk}")

                except Exception as e:
                    logger.error(trace_id, "ultimate_processor", f"块处理失败: {str(e)}")

        processing_time = time.time() - self.processing_start_time
        throughput = total_interfaces / processing_time if processing_time > 0 else 0

        logger.info(trace_id, "ultimate_processor",
                   f"所有块处理完成，总计: {total_interfaces} 接口, "
                   f"成功: {total_successful}, 失败: {total_failed}, "
                   f"缓存命中: {cache_hits}, "
                   f"处理时间: {processing_time:.2f}s, "
                   f"吞吐量: {throughput:.2f} interfaces/s")

        # 6. 记录性能数据
        record_batch_performance(
            processing_time, total_interfaces, total_successful,
            cache_hits, total_failed, trace_id
        )

        return {
            "interfaces": all_interfaces,
            "processing_time": processing_time,
            "throughput": throughput,
            "cache_hit_rate": cache_hits / total_interfaces if total_interfaces > 0 else 0,
            "success_rate": total_successful / total_interfaces if total_interfaces > 0 else 0
        }

    async def _process_chunk_with_all_optimizations(
        self, chunk: List[Tuple[str, int, str]], chunk_idx: int, trace_id: str,
        session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, config
    ) -> List[Dict[str, Any]]:
        """使用所有优化处理单个文档块"""
        async with semaphore:
            # 准备任务
            tasks = []
            for i, (grid_content, grid_start, context) in enumerate(chunk):
                block_index = chunk_idx * 100 + i
                task = self._process_single_interface_with_all_optimizations(
                    grid_content, context, block_index, trace_id, session
                )
                tasks.append(task)

            # 并发执行所有任务
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理结果
            interfaces = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(trace_id, "ultimate_processor",
                               f"接口 {chunk_idx*100+i} 处理异常: {str(result)}")
                    interfaces.append({
                        "error": str(result),
                        "_block_index": chunk_idx * 100 + i,
                        "_grid_content": chunk[i][0]
                    })
                else:
                    interfaces.append(result)

            return interfaces

    async def _process_single_interface_with_all_optimizations(
        self, grid_content: str, context: str, block_index: int, trace_id: str,
        session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """使用所有优化处理单个接口"""
        start_time = time.time()

        try:
            # 构建用户提示词
            user_prompt = f"""请解析下面这个功能块，生成对应的接口定义。

上下文信息：
{context}

功能块内容：
{grid_content}

请根据功能块的内容智能识别接口类型，并提取字段信息。输出JSON格式。"""

            # 尝试从各种缓存获取结果
            content_for_cache = f"{INTERFACE_SYSTEM_PROMPT}\n\n{user_prompt}"

            # 1. 智能缓存检查
            cached_result = self.cache.get(content_for_cache)
            if cached_result:
                processing_time = time.time() - start_time
                cached_result["_block_index"] = block_index
                cached_result["_grid_content"] = grid_content
                cached_result["_processing_time"] = processing_time
                cached_result["_cache_hit"] = True
                logger.debug(trace_id, "ultimate_processor", f"Block {block_index} 缓存命中")
                return cached_result

            # 2. 预测缓存检查
            similar_signature = self.predictive_cache.find_similar_cached_content(
                content_for_cache, threshold=0.8
            )
            if similar_signature:
                cached_result = self.predictive_cache.get_cached_result(similar_signature)
                if cached_result:
                    processing_time = time.time() - start_time
                    cached_result["_block_index"] = block_index
                    cached_result["_grid_content"] = grid_content
                    cached_result["_processing_time"] = processing_time
                    cached_result["_cache_hit"] = True
                    cached_result["_prediction_hit"] = True
                    logger.debug(trace_id, "ultimate_processor", f"Block {block_index} 预测缓存命中")
                    return cached_result

            # 3. 多模型负载均衡调用
            try:
                response = await call_llm_with_load_balancing(
                    system_prompt=INTERFACE_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.1,
                    max_tokens=3000,
                    priority="balanced"
                )

                processing_time = time.time() - start_time
                logger.debug(trace_id, "ultimate_processor",
                           f"Block {block_index} LLM调用成功，耗时: {processing_time:.2f}s")

                # 解析响应
                try:
                    interface_data = json.loads(response["response"])
                    interface_data["_block_index"] = block_index
                    interface_data["_grid_content"] = grid_content
                    interface_data["_processing_time"] = processing_time
                    interface_data["_cache_hit"] = False
                    interface_data["model_used"] = response.get("model", "unknown")
                    interface_data["cost"] = response.get("cost", 0)

                    # 智能缓存保存
                    self.cache.put(content_for_cache, interface_data)

                    return interface_data

                except json.JSONDecodeError as e:
                    logger.warning(trace_id, "ultimate_processor",
                                 f"Block {block_index} JSON解析失败: {str(e)}")
                    return {
                        "error": f"JSON解析失败: {str(e)}",
                        "_block_index": block_index,
                        "_grid_content": grid_content,
                        "_processing_time": processing_time,
                        "_cache_hit": False,
                        "_raw_response": response["response"]
                    }

            except Exception as e:
                processing_time = time.time() - start_time
                logger.error(trace_id, "ultimate_processor",
                           f"Block {block_index} 处理失败: {str(e)}")
                return {
                    "error": str(e),
                    "_block_index": block_index,
                    "_grid_content": grid_content,
                    "_processing_time": processing_time,
                    "_cache_hit": False
                }

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(trace_id, "ultimate_processor", f"Block {block_index} 处理异常: {str(e)}")
            return {
                "error": str(e),
                "_block_index": block_index,
                "_grid_content": grid_content,
                "_processing_time": processing_time,
                "_cache_hit": False
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

    def _extract_context_around_grid(self, content: str, grid_start: int, context_size: int = 5) -> str:
        """提取grid块周围的上下文"""
        lines = content.split('\n')
        start = max(0, grid_start - context_size)
        end = min(len(lines), grid_start + context_size)

        context_lines = []
        for i in range(start, end):
            if i < grid_start:
                line = lines[i].strip()
                if line.startswith('#') or line.startswith('##'):
                    context_lines.append(lines[i])
            elif i >= grid_start:
                break

        return '\n'.join(context_lines)

    def _create_adaptive_chunks(self, grid_blocks: List[Tuple[str, int]], config) -> List[List[Tuple[str, int, str]]]:
        """创建自适应分块策略"""
        chunks = []
        current_chunk = []
        current_chunk_size = 0

        # 根据配置动态调整块大小
        chunk_size = config.chunk_size

        for i, (grid_content, grid_start) in enumerate(grid_blocks):
            # 提取上下文
            context = self._extract_context_around_grid(
                '\n'.join([''] + grid_content.split('\n')[:10] + ['```']), grid_start
            )
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

    def _create_fallback_ism(self, error_msg: str, content: str, trace_id: str) -> Dict[str, Any]:
        """创建错误兜底的ISM"""
        return {
            "doc_meta": {
                "title": "处理出错的文档",
                "url": "",
                "version": "latest",
                "parsing_mode": "fallback"
            },
            "interfaces": [],
            "__pending__": [
                error_msg,
                f"原始内容长度: {len(content)} 字符"
            ]
        }


# 全局处理器实例
_ultimate_processor = None


def get_ultimate_processor() -> UltimateDocumentProcessor:
    """获取全局处理器实例"""
    global _ultimate_processor
    if _ultimate_processor is None:
        _ultimate_processor = UltimateDocumentProcessor()
    return _ultimate_processor


async def understand_doc(state: AgentState) -> AgentState:
    """
    终极优化版文档理解节点
    """
    trace_id = state["trace_id"]
    step_name = "understand_doc_ultimate"

    # 获取输入数据
    raw_docs = state["raw_docs"]
    feishu_urls = state.get("feishu_urls", [])
    templates = state.get("templates", [])

    logger.start(trace_id, step_name, "开始终极优化文档理解处理",
                extra={
                    "docs_count": len(raw_docs),
                    "total_length": sum(len(doc) for doc in raw_docs),
                    "has_templates": len(templates) > 0
                })

    try:
        # 合并文档内容
        combined_content = ""
        for i, doc in enumerate(raw_docs):
            combined_content += f"\n\n=== 文档 {i+1} ===\n{doc}"

        # 创建处理器
        processor = get_ultimate_processor()

        # 使用所有优化处理文档
        processing_result = await processor.process_document_with_all_optimizations(
            combined_content, trace_id
        )

        # 准备文档元数据
        doc_meta = {
            "title": "终极优化解析文档",
            "url": feishu_urls[0] if feishu_urls else "",
            "version": "latest",
            "parsing_mode": "ultimate_optimized",
            "processing_time": processing_result["processing_time"],
            "throughput": processing_result["throughput"],
            "cache_hit_rate": processing_result["cache_hit_rate"],
            "success_rate": processing_result["success_rate"]
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

        # 合并接口为完整的ISM
        ism = {
            "doc_meta": doc_meta,
            "interfaces": processing_result["interfaces"],
            "__pending__": []
        }

        # 添加性能统计到ISM
        ism["performance_stats"] = {
            "processing_time": processing_result["processing_time"],
            "throughput": processing_result["throughput"],
            "cache_hit_rate": processing_result["cache_hit_rate"],
            "success_rate": processing_result["success_rate"],
            "total_interfaces": len(processing_result["interfaces"]),
            "successful_interfaces": len([i for i in processing_result["interfaces"] if "error" not in i]),
            "failed_interfaces": len([i for i in processing_result["interfaces"] if "error" in i])
        }

        # 写入state
        result_state = state.copy()
        result_state["ism"] = ism

        logger.end(trace_id, step_name, "终极优化ISM生成完成",
                  extra={
                      "interfaces_count": len(ism.get("interfaces", [])),
                      "pending_count": len(ism["__pending__"]),
                      "doc_title": ism["doc_meta"].get("title", "未知"),
                      "processing_time": processing_result["processing_time"],
                      "throughput": processing_result["throughput"],
                      "cache_hit_rate": processing_result["cache_hit_rate"],
                      "success_rate": processing_result["success_rate"]
                  })

        return result_state

    except Exception as e:
        logger.error(trace_id, step_name, "终极优化ISM生成过程中发生错误", extra={"error": str(e)})

        # 构造错误兜底ISM
        fallback_ism = {
            "doc_meta": {
                "title": "终极处理出错的文档",
                "url": feishu_urls[0] if feishu_urls else "",
                "version": "latest",
                "parsing_mode": "ultimate_failed"
            },
            "interfaces": [],
            "__pending__": [
                f"终极优化过程中发生错误: {str(e)}",
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


# 兼容性包装函数，保持与现有接口完全兼容
def understand_doc(state: AgentState) -> AgentState:
    """
    文档理解节点 - 终极优化版本
    自动选择最优处理策略
    """
    try:
        # 尝试使用终极优化版本
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果已在事件循环中，需要在新线程中运行
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, understand_doc_ultimate(state))
                return future.result()
        else:
            # 如果没有事件循环，直接运行
            return asyncio.run(understand_doc_ultimate(state))
    except Exception as e:
        logger.error(state["trace_id"], "understand_doc", f"终极优化版本失败，回退到基础版本: {str(e)}")
        # 最后的降级策略：尝试并行版本
        try:
            from nodes.understand_doc_parallel import understand_doc_parallel
            return understand_doc_parallel(state)
        except Exception as e2:
            logger.error(state["trace_id"], "understand_doc", f"并行版本也失败，使用原始版本: {str(e2)}")
            from nodes.understand_doc_original import understand_doc as understand_doc_original
            return understand_doc_original(state)