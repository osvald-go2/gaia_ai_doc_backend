"""
AI Agent MVP - 主工作流入口
基于LangGraph的7节点工作流实现（新增文档切分）
"""

from langgraph.graph import StateGraph, END

from models.state import AgentState
from nodes.ingest_input import ingest_input
from nodes.fetch_feishu_doc import fetch_feishu_doc
from nodes.split_document import split_document
from nodes.understand_doc_parallel import understand_doc_parallel
from nodes.normalize_and_validate_ism import normalize_and_validate_ism
from nodes.plan_from_ism import plan_from_ism
from nodes.apply_flow_patch import apply_flow_patch
from nodes.finalize import finalize


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


def run_workflow(input_data: dict = None) -> dict:
    """
    运行完整的工作流

    Args:
        input_data: 输入数据，如果为None则使用SAMPLE_INPUT

    Returns:
        工作流执行结果
    """
    if input_data is None:
        input_data = SAMPLE_INPUT

    # 创建工作流图
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
        result = run_workflow()
        print("工作流运行成功！")
        print(f"结果: {result}")
    except Exception as e:
        print(f"工作流运行失败: {str(e)}")
        raise