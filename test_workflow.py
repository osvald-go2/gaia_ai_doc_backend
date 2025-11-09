#!/usr/bin/env python3
"""
工作流测试脚本
用于开发和调试，可以注入Mock数据测试特定节点
"""

import json
import uuid
from langgraph.graph import StateGraph, END

from models.state import AgentState
from nodes.ingest_input import ingest_input
from nodes.fetch_feishu_doc import fetch_feishu_doc
from nodes.understand_doc import understand_doc
from nodes.normalize_and_validate_ism import normalize_and_validate_ism
from nodes.plan_from_ism import plan_from_ism
from nodes.apply_flow_patch import apply_flow_patch
from nodes.finalize import finalize

from utils.logger import logger


def create_full_graph() -> StateGraph:
    """创建完整的工作流图"""
    graph = StateGraph(AgentState)

    # 添加所有节点
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

    return graph.compile()


def create_test_graph(start_node: str = "normalize_and_validate_ism") -> StateGraph:
    """创建测试图，从指定节点开始"""
    graph = StateGraph(AgentState)

    # 添加所有节点
    graph.add_node("ingest_input", ingest_input)
    graph.add_node("fetch_feishu_doc", fetch_feishu_doc)
    graph.add_node("understand_doc", understand_doc)
    graph.add_node("normalize_and_validate_ism", normalize_and_validate_ism)
    graph.add_node("plan_from_ism", plan_from_ism)
    graph.add_node("apply_flow_patch", apply_flow_patch)
    graph.add_node("finalize", finalize)

    # 设置入口点
    graph.set_entry_point(start_node)

    # 添加边（定义执行顺序）
    graph.add_edge("ingest_input", "fetch_feishu_doc")
    graph.add_edge("fetch_feishu_doc", "understand_doc")
    graph.add_edge("understand_doc", "normalize_and_validate_ism")
    graph.add_edge("normalize_and_validate_ism", "plan_from_ism")
    graph.add_edge("plan_from_ism", "apply_flow_patch")
    graph.add_edge("apply_flow_patch", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


def get_mock_ism_raw():
    """获取Mock ISM数据"""
    return {
        "doc_meta": {
            "title": "ROI分析报表",
            "url": "https://feishu.cn/test"
        },
        "interfaces": [
            {
                "name": "公司ROI分析",
                "type": "data_display",
                "dimensions": [
                    {"name": "公司ID"},
                    {"name": "公司名称"}
                ],
                "metrics": [
                    {"name": "ROI"},
                    {"name": "消耗"},
                    {"name": "GMV"}
                ]
            },
            {
                "name": "趋势分析",
                "type": "trend_analysis",
                "dimensions": [
                    {"name": "时间"}
                ],
                "metrics": [
                    {"name": "ROI"},
                    {"name": "转化率"}
                ]
            }
        ]
    }


def test_full_workflow():
    """测试完整工作流"""
    print("测试完整工作流")
    print("=" * 60)

    # 创建工作流
    app = create_full_graph()

    # 初始化状态
    init_state: AgentState = {
        "feishu_urls": ["https://feishu.cn/doc/123"],
        "user_intent": "generate_crud",
        "trace_id": f"full-test-{uuid.uuid4().hex[:8]}"
    }

    print(f"输入状态:")
    print(f"   feishu_urls: {init_state['feishu_urls']}")
    print(f"   user_intent: {init_state['user_intent']}")
    print(f"   trace_id: {init_state['trace_id']}")
    print("-" * 60)

    # 执行工作流
    try:
        result = app.invoke(init_state)

        print("完整工作流执行成功!")
        print("=" * 60)
        print("最终结果:")
        print(f"   状态: {result.get('response', {}).get('status', 'unknown')}")
        print(f"   ISM接口数: {len(result.get('ism', {}).get('interfaces', []))}")
        print(f"   计划数: {len(result.get('plan', []))}")

        return result

    except Exception as e:
        print(f"完整工作流执行失败: {str(e)}")
        logger.error(init_state["trace_id"], "test_full_workflow", f"完整工作流执行失败: {str(e)}")
        return None


def test_from_normalize_and_validate():
    """测试从 normalize_and_validate_ism 开始的流程"""
    print("测试从 normalize_and_validate_ism 开始的流程")
    print("=" * 60)

    # 创建测试工作流
    app = create_test_graph("normalize_and_validate_ism")

    # 准备Mock数据
    mock_ism_raw = get_mock_ism_raw()

    # 初始化状态
    init_state: AgentState = {
        "feishu_urls": ["https://feishu.cn/doc/123"],
        "user_intent": "generate_crud",
        "trace_id": f"partial-test-{uuid.uuid4().hex[:8]}",
        "ism_raw": mock_ism_raw
    }

    print(f"输入状态:")
    print(f"   trace_id: {init_state['trace_id']}")
    print(f"   ism_raw 接口数: {len(mock_ism_raw.get('interfaces', []))}")
    print("-" * 60)

    # 执行工作流
    try:
        result = app.invoke(init_state)

        print("部分工作流执行成功!")
        print("=" * 60)
        print("最终结果:")
        print(f"   状态: {result.get('response', {}).get('status', 'unknown')}")
        print(f"   ISM接口数: {len(result.get('ism', {}).get('interfaces', []))}")
        print(f"   修复数: {len(result.get('diag', {}).get('fixups', []))}")
        print(f"   计划数: {len(result.get('plan', []))}")

        # 显示修复详情
        if 'diag' in result:
            print("\n修复详情:")
            for fixup in result['diag'].get('fixups', [])[:5]:  # 只显示前5个
                print(f"   - {fixup}")
            if len(result['diag']['fixups']) > 5:
                print(f"   ... 还有 {len(result['diag']['fixups']) - 5} 个修复")

        return result

    except Exception as e:
        print(f"部分工作流执行失败: {str(e)}")
        logger.error(init_state["trace_id"], "test_from_normalize_and_validate", f"部分工作流执行失败: {str(e)}")
        return None


def main():
    """主函数"""
    print("AI Agent MVP 工作流测试")
    print("=" * 60)

    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "full":
        # 测试完整工作流
        test_full_workflow()
    elif len(sys.argv) > 1 and sys.argv[1] == "partial":
        # 测试部分工作流（从 normalize_and_validate_ism 开始）
        test_from_normalize_and_validate()
    else:
        # 默认测试部分工作流
        print("默认测试从 normalize_and_validate_ism 开始的流程")
        print("使用 'python test_workflow.py full' 测试完整工作流")
        print("使用 'python test_workflow.py partial' 测试部分工作流")
        print()
        test_from_normalize_and_validate()


if __name__ == "__main__":
    main()