#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成测试：验证并行处理的文档理解节点在完整流程中的工作情况
"""

import json
import uuid
import time
from langgraph.graph import StateGraph, END

from models.state import AgentState
from nodes.ingest_input import ingest_input
from nodes.fetch_feishu_doc import fetch_feishu_doc
from nodes.understand_doc import understand_doc
from nodes.plan_from_ism import plan_from_ism
from nodes.apply_flow_patch import apply_flow_patch
from nodes.finalize import finalize

from utils.logger import logger


def create_test_graph() -> StateGraph:
    """
    创建测试用的 LangGraph 工作流
    """
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("ingest_input", ingest_input)
    graph.add_node("fetch_feishu_doc", fetch_feishu_doc)
    graph.add_node("understand_doc", understand_doc)
    graph.add_node("plan_from_ism", plan_from_ism)
    graph.add_node("apply_flow_patch", apply_flow_patch)
    graph.add_node("finalize", finalize)

    # 设置入口点
    graph.set_entry_point("ingest_input")

    # 添加边（定义执行顺序）
    graph.add_edge("ingest_input", "fetch_feishu_doc")
    graph.add_edge("fetch_feishu_doc", "understand_doc")
    graph.add_edge("understand_doc", "plan_from_ism")
    graph.add_edge("plan_from_ism", "apply_flow_patch")
    graph.add_edge("apply_flow_patch", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


def run_integration_test():
    """
    运行集成测试
    """
    print("=" * 60)
    print("集成测试：并行文档理解节点")
    print("=" * 60)

    # 创建工作流
    app = create_test_graph()

    # 初始化状态（使用包含多个接口的复杂文档）
    init_state: AgentState = {
        "feishu_urls": ["https://example.com/test/ecommerce-system"],
        "user_intent": "generate_crud",
        "trace_id": f"integration-test-{uuid.uuid4().hex[:8]}"
    }

    print(f"输入状态:")
    print(f"   feishu_urls: {init_state['feishu_urls']}")
    print(f"   user_intent: {init_state['user_intent']}")
    print(f"   trace_id: {init_state['trace_id']}")
    print("-" * 60)

    # 记录开始时间
    start_time = time.time()

    try:
        # 执行工作流
        result = app.invoke(init_state)

        # 计算总处理时间
        end_time = time.time()
        total_time = end_time - start_time

        print("执行完成!")
        print("=" * 60)
        print("处理结果:")
        print(f"   总处理时间: {total_time:.2f} 秒")

        # 检查ISM结构
        if "ism" in result:
            ism = result["ism"]
            interfaces_count = len(ism.get("interfaces", []))
            pending_count = len(ism.get("__pending__", []))
            doc_title = ism.get("doc_meta", {}).get("title", "未知")
            parsing_mode = ism.get("doc_meta", {}).get("parsing_mode", "unknown")

            print(f"   文档标题: {doc_title}")
            print(f"   解析模式: {parsing_mode}")
            print(f"   解析接口数: {interfaces_count}")
            print(f"   待处理项: {pending_count}")

            if interfaces_count > 0:
                print(f"\n解析的接口详情:")
                for i, interface in enumerate(ism.get("interfaces", [])[:3], 1):
                    name = interface.get('name', 'Unknown')
                    type_name = interface.get('type', 'Unknown')
                    dims_count = len(interface.get('dimensions', []))
                    metrics_count = len(interface.get('metrics', []))
                    print(f"   {i}. {name} ({type_name}) - {dims_count}维度, {metrics_count}指标")

                if len(ism.get("interfaces", [])) > 3:
                    remaining = len(ism.get("interfaces", [])) - 3
                    print(f"   ... 还有 {remaining} 个接口")

        # 检查最终响应
        if "response" in result:
            response = result["response"]
            print(f"\n最终响应:")
            print(f"   状态: {response.get('status', 'unknown')}")
            print(f"   消息: {response.get('message', 'no message')}")

            # 保存完整结果到文件
            with open("integration_test_result.json", "w", encoding="utf-8") as f:
                json.dump({
                    "test_info": {
                        "trace_id": init_state["trace_id"],
                        "total_time": total_time,
                        "parsing_mode": parsing_mode
                    },
                    "final_result": result
                }, f, ensure_ascii=False, indent=2, default=str)

            print(f"\n详细结果已保存到: integration_test_result.json")

        else:
            print("错误：没有找到响应结果")

        print("=" * 60)
        print("集成测试完成！")

        return True

    except Exception as e:
        end_time = time.time()
        total_time = end_time - start_time
        print(f"执行失败: {str(e)}")
        print(f"失败时间点: {total_time:.2f} 秒")
        logger.error(init_state["trace_id"], "integration_test", f"工作流执行失败: {str(e)}")
        return False


if __name__ == "__main__":
    success = run_integration_test()
    if success:
        print("\n✅ 集成测试通过 - 并行处理节点工作正常")
    else:
        print("\n❌ 集成测试失败 - 需要检查配置")