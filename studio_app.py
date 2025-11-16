"""
LangGraph Studio 配置文件

这个文件定义了可以在 LangGraph Studio 中调试的图
支持文档缓存功能以提升性能
"""

import os
import time
from langgraph.graph import StateGraph, END

from models.state import AgentState
from nodes.ingest_input import ingest_input
from nodes.fetch_feishu_doc import fetch_feishu_doc
from nodes.split_document import split_document
from nodes.understand_doc import understand_doc
from nodes.normalize_and_validate_ism import normalize_and_validate_ism
from nodes.plan_from_ism import plan_from_ism
from nodes.apply_flow_patch import apply_flow_patch
from nodes.finalize import finalize
from utils.document_cache import try_get_document_cache, store_document_cache
from utils.logger import logger


def check_document_cache(state: AgentState) -> AgentState:
    """
    文档缓存检查节点
    在获取文档后检查是否有缓存命中
    """
    trace_id = state.get("trace_id", "")
    step_name = "check_document_cache"
    raw_docs = state.get("raw_docs", [])
    user_intent = state.get("user_intent", "generate_crud")

    logger.start(trace_id, step_name, f"检查文档缓存，文档数: {len(raw_docs)}, 意图: {user_intent}")

    result_state = state.copy()

    # 默认值：进行正常处理
    result_state["__cache_hit"] = False
    result_state["__skip_processing"] = False
    result_state["__processing_start_time"] = time.time()

    if raw_docs:
        # 尝试获取缓存
        cached_entry = try_get_document_cache(raw_docs, user_intent)

        if cached_entry:
            # 缓存命中
            logger.info(trace_id, step_name, f"缓存命中！文档hash: {cached_entry.doc_hash[:16]}...")
            logger.info(trace_id, step_name, f"节省处理时间: {cached_entry.processing_time_ms:.2f}ms, 命中次数: {cached_entry.hit_count}")

            # 标记缓存命中，并设置缓存结果
            result_state["__cache_hit"] = True
            result_state["__cached_entry"] = cached_entry
            result_state["__skip_processing"] = True

            # 直接设置缓存的结果到状态中
            result_state["doc_chunks"] = cached_entry.doc_chunks
            result_state["chunk_metadata"] = cached_entry.chunk_metadata
            result_state["ism"] = cached_entry.ism_result
            result_state["plan"] = cached_entry.plan_result
            result_state["final_flow_json"] = cached_entry.final_flow_json
            result_state["mcp_payloads"] = cached_entry.mcp_payloads
            result_state["response"] = cached_entry.final_response

        else:
            # 缓存未命中
            logger.info(trace_id, step_name, "缓存未命中，需要正常处理")
            # 保持默认值（正常处理）
    else:
        # 没有文档内容，跳过缓存检查，进行正常处理
        logger.info(trace_id, step_name, "无文档内容，跳过缓存检查")

    logger.end(trace_id, step_name, f"缓存检查完成，缓存命中: {result_state['__cache_hit']}")
    return result_state


def store_document_cache_result(state: AgentState) -> AgentState:
    """
    文档缓存存储节点
    在处理完成后存储结果到缓存
    """
    trace_id = state.get("trace_id", "")
    step_name = "store_document_cache_result"

    # 如果已经从缓存获取结果，跳过存储
    if state.get("__cache_hit", False):
        logger.info(trace_id, step_name, "使用缓存结果，跳过存储")
        return state

    logger.start(trace_id, step_name, "存储处理结果到缓存")

    try:
        # 计算处理时间
        start_time = state.get("__processing_start_time")
        processing_time_ms = 0.0
        if start_time:
            processing_time_ms = (time.time() - start_time) * 1000

        # 获取需要缓存的结果
        raw_docs = state.get("raw_docs", [])
        feishu_urls = state.get("feishu_urls", [])
        user_intent = state.get("user_intent", "generate_crud")
        doc_chunks = state.get("doc_chunks", [])
        chunk_metadata = state.get("chunk_metadata", {})
        ism_result = state.get("ism", {})
        plan_result = state.get("plan", [])
        final_flow_json = state.get("final_flow_json", "{}")
        mcp_payloads = state.get("mcp_payloads", [])
        final_response = state.get("response", {})

        # 存储到缓存
        store_document_cache(
            raw_docs=raw_docs,
            feishu_urls=feishu_urls,
            user_intent=user_intent,
            doc_chunks=doc_chunks,
            chunk_metadata=chunk_metadata,
            ism_result=ism_result,
            plan_result=plan_result,
            final_flow_json=final_flow_json,
            mcp_payloads=mcp_payloads,
            final_response=final_response,
            processing_time_ms=processing_time_ms
        )

        logger.info(trace_id, step_name,
                   f"结果已缓存，处理时间: {processing_time_ms:.2f}ms, "
                   f"文档数: {len(raw_docs)}")

    except Exception as e:
        logger.error(trace_id, step_name, f"缓存存储失败: {str(e)}")
        # 缓存失败不影响正常流程

    return state


def create_graph() -> StateGraph:
    """
    创建并配置 LangGraph 工作流，用于 Studio 调试
    集成文档缓存功能以提升性能
    """
    # 检查是否启用缓存
    enable_cache = os.environ.get('ENABLE_DOC_CACHE', 'true').lower() == 'true'

    # 创建状态图
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("ingest_input", ingest_input)
    graph.add_node("fetch_feishu_doc", fetch_feishu_doc)

    if enable_cache:
        # 启用缓存时添加缓存相关节点
        graph.add_node("check_document_cache", check_document_cache)
        graph.add_node("store_document_cache_result", store_document_cache_result)

    graph.add_node("split_document", split_document)
    graph.add_node("understand_doc", understand_doc)
    graph.add_node("normalize_and_validate_ism", normalize_and_validate_ism)
    graph.add_node("plan_from_ism", plan_from_ism)
    graph.add_node("apply_flow_patch", apply_flow_patch)
    graph.add_node("finalize", finalize)

    # 设置入口点
    graph.set_entry_point("ingest_input")

    if enable_cache:
        # 启用缓存的工作流
        graph.add_edge("ingest_input", "fetch_feishu_doc")
        graph.add_edge("fetch_feishu_doc", "check_document_cache")

        # 条件边：如果缓存命中则跳过处理步骤
        graph.add_conditional_edges(
            "check_document_cache",
            lambda state: "skip_processing" if state.get("__skip_processing", False) else "normal_processing",
            {
                "skip_processing": "store_document_cache_result",
                "normal_processing": "split_document"
            }
        )

        # 正常处理流程
        graph.add_edge("split_document", "understand_doc")
        graph.add_edge("understand_doc", "normalize_and_validate_ism")
        graph.add_edge("normalize_and_validate_ism", "plan_from_ism")
        graph.add_edge("plan_from_ism", "apply_flow_patch")
        graph.add_edge("apply_flow_patch", "finalize")

        # 缓存存储和结束
        graph.add_edge("finalize", "store_document_cache_result")
        graph.add_edge("store_document_cache_result", END)

    else:
        # 禁用缓存的标准工作流
        graph.add_edge("ingest_input", "fetch_feishu_doc")
        graph.add_edge("fetch_feishu_doc", "split_document")
        graph.add_edge("split_document", "understand_doc")
        graph.add_edge("understand_doc", "normalize_and_validate_ism")
        graph.add_edge("normalize_and_validate_ism", "plan_from_ism")
        graph.add_edge("plan_from_ism", "apply_flow_patch")
        graph.add_edge("apply_flow_patch", "finalize")
        graph.add_edge("finalize", END)

    # 编译图
    return graph.compile()


# 为 Studio 提供默认的测试输入
SAMPLE_INPUT = {
    "feishu_urls": ["https://feishu.cn/doc/123"],
    "user_intent": "generate_crud",
    "trace_id": "studio-test-001"
}