"""
AI Agent MVP - 主工作流入口
基于LangGraph的7节点工作流实现（新增文档切分和缓存功能）
"""

import os
from langgraph.graph import StateGraph, END

from models.state import AgentState
from nodes.ingest_input import ingest_input
from nodes.fetch_feishu_doc import fetch_feishu_doc
from nodes.split_document import split_document
from nodes.understand_doc import understand_doc_parallel
from nodes.normalize_and_validate_ism import normalize_and_validate_ism
from nodes.plan_from_ism import plan_from_ism
from nodes.apply_flow_patch import apply_flow_patch
from nodes.finalize import finalize
from utils.logger import logger


def create_graph() -> StateGraph:
    """
    创建并配置 LangGraph 工作流

    工作流程：ingest_input → fetch_feishu_doc → split_document → understand_doc_parallel
             → normalize_and_validate_ism → plan_from_ism → apply_flow_patch → finalize
    """
    # 创建状态图
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("ingest_input", ingest_input)
    graph.add_node("fetch_feishu_doc", fetch_feishu_doc)
    graph.add_node("split_document", split_document)
    graph.add_node("understand_doc", understand_doc_parallel)
    graph.add_node("normalize_and_validate_ism", normalize_and_validate_ism)
    graph.add_node("plan_from_ism", plan_from_ism)
    graph.add_node("apply_flow_patch", apply_flow_patch)
    graph.add_node("finalize", finalize)

    # 设置入口点
    graph.set_entry_point("ingest_input")

    # 添加边（定义执行顺序）
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


# 默认测试输入
SAMPLE_INPUT = {
    "feishu_urls": ["https://feishu.cn/doc/123"],
    "user_intent": "generate_crud",
    "trace_id": "test-001"
}


def run_workflow(input_data: dict = None, use_cache: bool = None) -> dict:
    """
    运行完整的工作流

    Args:
        input_data: 输入数据，如果为None则使用SAMPLE_INPUT
        use_cache: 是否使用缓存功能，None则根据环境变量决定

    Returns:
        工作流执行结果
    """
    if input_data is None:
        input_data = SAMPLE_INPUT

    # 决定是否使用缓存
    if use_cache is None:
        use_cache = os.environ.get('ENABLE_DOC_CACHE', 'true').lower() == 'true'

    trace_id = input_data.get('trace_id', 'unknown')

    if use_cache:
        logger.info(trace_id, "workflow_selection", "使用缓存感知工作流")
        try:
            from nodes.cache_aware_workflow import create_cached_graph
            workflow = create_cached_graph()
        except ImportError as e:
            logger.warning(trace_id, "workflow_selection", f"缓存工作流不可用，回退到标准工作流: {str(e)}")
            workflow = create_graph()
    else:
        logger.info(trace_id, "workflow_selection", "使用标准工作流")
        workflow = create_graph()

    # 运行工作流
    result = workflow.invoke(input_data)

    return result


if __name__ == "__main__":
    # 直接运行测试
    print("开始运行 AI Agent MVP 工作流测试...")
    print(f"输入: {SAMPLE_INPUT}")
    print("-" * 50)

    try:
        # 测试缓存功能
        use_cache = os.environ.get('ENABLE_DOC_CACHE', 'true').lower() == 'true'

        if use_cache:
            print("缓存功能已启用，进行缓存效果测试...")

            # 第一次运行（应该正常处理）
            print("\n第一次运行（正常处理）：")
            result1 = run_workflow()
            cache_hit = result1.get('__cache_hit', False)
            print(f"缓存命中: {cache_hit}")
            if not cache_hit:
                print("这是正常的，第一次运行需要处理文档并缓存结果")

            # 第二次运行（应该命中缓存）
            print("\n第二次运行（应该命中缓存）：")
            result2 = run_workflow()
            cache_hit = result2.get('__cache_hit', False)
            print(f"缓存命中: {cache_hit}")
            print(f"最终响应中的缓存状态: {result2.get('response', {}).get('cached', 'unknown')}")
            if cache_hit or result2.get('response', {}).get('cached', False):
                print("缓存功能正常！")
                cached_entry = result2.get('__cached_entry')
                if cached_entry:
                    print(f"缓存命中次数: {cached_entry.hit_count}")
                    print(f"节省处理时间: {cached_entry.processing_time_ms:.2f}ms")
            else:
                print("缓存未命中，可能文档内容或用户意图有变化")
        else:
            print("缓存功能未启用，运行标准工作流...")
            result = run_workflow(use_cache=False)
            print("工作流运行成功！")

    except Exception as e:
        print(f"工作流运行失败: {str(e)}")
        raise