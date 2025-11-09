#!/usr/bin/env python3
"""
AI Agent MVP - 主入口文件

实现：飞书URL → 解析 → ISM → 计划 → 合成JSON → 返回 的核心链路
"""

import json
import uuid
from langgraph.graph import StateGraph, END

from models.state import AgentState
from nodes.ingest_input import ingest_input
from nodes.fetch_feishu_doc import fetch_feishu_doc
from nodes.understand_doc_async import understand_doc_async as understand_doc
from nodes.normalize_and_validate_ism import normalize_and_validate_ism
from nodes.plan_from_ism import plan_from_ism
from nodes.apply_flow_patch import apply_flow_patch
from nodes.finalize import finalize

from utils.logger import logger


def create_graph() -> StateGraph:
    """
    创建并配置 LangGraph 工作流
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

    # 设置入口点 - 对于测试数据，直接从normalize_and_validate_ism开始
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


def main():
    """
    主函数：演示完整的 AI Agent MVP 流程
    """
    print("AI Agent MVP 启动")
    print("=" * 50)

    # 创建工作流
    app = create_graph()

    # 初始化状态 - 使用Mock数据直接注入测试完整工作流
    mock_ism_raw = {
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
            }
        ]
    }

    init_state: AgentState = {
        "feishu_urls": ["https://feishu.cn/doc/123"],
        "user_intent": "generate_crud",
        "trace_id": f"req-demo-{uuid.uuid4().hex[:8]}",
        "ism_raw": mock_ism_raw  # 直接注入Mock数据，跳过文档获取
    }

    print(f"输入状态:")
    print(f"   feishu_urls: {init_state['feishu_urls']}")
    print(f"   user_intent: {init_state['user_intent']}")
    print(f"   trace_id: {init_state['trace_id']}")
    print("-" * 50)

    # 执行工作流
    try:
        print("开始执行工作流...")
        result = app.invoke(init_state)

        print("执行完成!")
        print("=" * 50)

        # 检查哪些步骤被执行了
        if "ism" in result:
            print("[SUCCESS] ISM已生成 - normalize_and_validate_ism节点执行成功")
            print(f"   接口数量: {len(result.get('ism', {}).get('interfaces', []))}")
        else:
            print("[ERROR] ISM未生成 - 可能normalize_and_validate_ism节点未执行")

        if "plan" in result:
            print("[SUCCESS] 计划已生成")
            print(f"   计划数量: {len(result.get('plan', []))}")
        else:
            print("[ERROR] 计划未生成")

        if "response" in result:
            print("最终结果:")
            print(json.dumps(result["response"], ensure_ascii=False, indent=2))
        else:
            print("[ERROR] 响应未生成")

    except Exception as e:
        print(f"执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
        logger.error(init_state["trace_id"], "main", f"工作流执行失败: {str(e)}")


if __name__ == "__main__":
    main()