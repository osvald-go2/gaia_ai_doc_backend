"""
LangGraph Studio 配置文件

这个文件定义了可以在 LangGraph Studio 中调试的图
"""

from langgraph.graph import StateGraph, END

from models.state import AgentState
from nodes.ingest_input import ingest_input
from nodes.fetch_feishu_doc import fetch_feishu_doc
from nodes.understand_doc import understand_doc
from nodes.normalize_and_validate_ism import normalize_and_validate_ism
from nodes.plan_from_ism import plan_from_ism
from nodes.apply_flow_patch import apply_flow_patch
from nodes.finalize import finalize


def create_graph() -> StateGraph:
    """
    创建并配置 LangGraph 工作流，用于 Studio 调试
    """
    # 创建状态图
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("ingest_input", ingest_input)
    graph.add_node("fetch_feishu_doc", fetch_feishu_doc)
    graph.add_node("understand_doc", understand_doc)
    graph.add_node("normalize_and_validate_ism", normalize_and_validate_ism)
    graph.add_node("plan_from_ism", plan_from_ism)
    graph.add_node("apply_flow_patch", apply_flow_patch)
    graph.add_node("finalize", finalize)

    # 设置入口点
    graph.set_entry_point("ingest_input")

    # 添加边（定义执行顺序）
    graph.add_edge("ingest_input", "fetch_feishu_doc")
    graph.add_edge("fetch_feishu_doc", "understand_doc")
    graph.add_edge("understand_doc", "normalize_and_validate_ism")
    graph.add_edge("normalize_and_validate_ism", "plan_from_ism")
    graph.add_edge("plan_from_ism", "apply_flow_patch")
    graph.add_edge("apply_flow_patch", "finalize")
    graph.add_edge("finalize", END)

    # 编译图
    return graph.compile()


# 为 Studio 提供默认的测试输入
SAMPLE_INPUT = {
    "feishu_url": "https://feishu.cn/doc/123",
    "user_intent": "generate_crud",
    "trace_id": "studio-test-001"
}