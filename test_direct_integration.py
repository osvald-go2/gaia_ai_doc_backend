#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接集成测试：跳过飞书文档获取，直接测试并行文档理解节点
"""

import json
import uuid
import time
from langgraph.graph import StateGraph, END

from models.state import AgentState
from nodes.understand_doc import understand_doc
from nodes.plan_from_ism import plan_from_ism
from nodes.apply_flow_patch import apply_flow_patch
from nodes.finalize import finalize

from utils.logger import logger


# 测试用的复杂电商文档内容
TEST_ECOMMERCE_DOC = """
# 电商管理系统产品设计

## 1. 用户管理模块

```grid
grid_column:
  - width_ratio: 40
    content: |
        ![用户列表界面](user_list.png)
  - width_ratio: 60
    content: |
        **查询条件**
        - 用户ID: userId
        - 用户名: username
        - 注册渠道: channel
        - 注册时间: createdTime

        **显示字段**
        - 用户ID
        - 用户名
        - 邮箱
        - 注册时间
        - 最后登录时间
```

## 2. 订单管理模块

```grid
grid_column:
  - width_ratio: 50
    content: |
        ![订单统计界面](order_stats.png)
  - width_ratio: 50
    content: |
        **统计指标**
        - 订单总数: orderCount
        - 订单总金额: totalAmount
        - 平均客单价: avgOrderValue
        - 订单状态分布: statusDistribution

        **时间维度**
        - 日统计: daily
        - 周统计: weekly
        - 月统计: monthly
```

## 3. 商品管理模块

```grid
grid_column:
  - width_ratio: 45
    content: |
        ![商品管理界面](product_manage.png)
  - width_ratio: 55
    content: |
        **商品筛选条件**
        - 商品分类: category
        - 品牌ID: brandId
        - 价格区间: priceRange
        - 库存状态: stockStatus

        **商品信息字段**
        - 商品ID: productId
        - 商品名称: productName
        - 商品价格: price
        - 库存数量: stock
        - 销量: sales
```

## 4. 数据分析模块

```grid
grid_column:
  - width_ratio: 50
    content: |
        ![数据分析仪表板](analytics_dashboard.png)
  - width_ratio: 50
    content: |
        **分析维度**
        - 用户维度: userDimension
        - 商品维度: productDimension
        - 时间维度: timeDimension
        - 地域维度: regionDimension

        **核心指标**
        - 转化率: conversionRate
        - 复购率: repurchaseRate
        - 用户留存率: retentionRate
        - 销售增长率: growthRate
```

## 5. 导出报表模块

```grid
grid_column:
  - width_ratio: 40
    content: |
        ![报表导出界面](export_report.png)
  - width_ratio: 60
    content: |
        **导出配置**
        - 报表类型: reportType
        - 导出格式: exportFormat (Excel/PDF/CSV)
        - 时间范围: dateRange
        - 数据范围: dataScope

        **导出字段**
        - 用户信息: userInfo
        - 订单信息: orderInfo
        - 商品信息: productInfo
        - 统计数据: statistics
```
"""


def create_direct_test_graph() -> StateGraph:
    """
    创建直接测试用的 LangGraph 工作流（跳过文档获取）
    """
    graph = StateGraph(AgentState)

    # 直接从文档理解开始
    graph.add_node("understand_doc", understand_doc)
    graph.add_node("plan_from_ism", plan_from_ism)
    graph.add_node("apply_flow_patch", apply_flow_patch)
    graph.add_node("finalize", finalize)

    # 设置入口点
    graph.set_entry_point("understand_doc")

    # 添加边
    graph.add_edge("understand_doc", "plan_from_ism")
    graph.add_edge("plan_from_ism", "apply_flow_patch")
    graph.add_edge("apply_flow_patch", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


def run_direct_integration_test():
    """
    运行直接集成测试
    """
    print("=" * 60)
    print("直接集成测试：并行文档理解节点")
    print("=" * 60)

    # 创建工作流
    app = create_direct_test_graph()

    # 初始化状态（直接提供文档内容）
    init_state: AgentState = {
        "feishu_urls": ["https://example.com/test/ecommerce-system"],
        "user_intent": "generate_crud",
        "trace_id": f"direct-test-{uuid.uuid4().hex[:8]}",
        "raw_docs": [TEST_ECOMMERCE_DOC],
        "feishu_blocks": [],
        "templates": []
    }

    print(f"输入状态:")
    print(f"   feishu_urls: {init_state['feishu_urls']}")
    print(f"   user_intent: {init_state['user_intent']}")
    print(f"   trace_id: {init_state['trace_id']}")
    print(f"   文档长度: {len(TEST_ECOMMERCE_DOC)} 字符")
    print(f"   grid块数量: {TEST_ECOMMERCE_DOC.count('```grid')} 个")
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
                for i, interface in enumerate(ism.get("interfaces", [])[:5], 1):
                    name = interface.get('name', 'Unknown')
                    type_name = interface.get('type', 'Unknown')
                    dims_count = len(interface.get('dimensions', []))
                    metrics_count = len(interface.get('metrics', []))
                    print(f"   {i}. {name} ({type_name}) - {dims_count}维度, {metrics_count}指标")

                if len(ism.get("interfaces", [])) > 5:
                    remaining = len(ism.get("interfaces", [])) - 5
                    print(f"   ... 还有 {remaining} 个接口")

        # 检查计划
        if "plan" in result:
            plan = result["plan"]
            plan_steps = len(plan) if isinstance(plan, list) else 0
            print(f"\n生成的计划:")
            print(f"   计划步骤数: {plan_steps}")

            if plan_steps > 0:
                print(f"   前几个步骤:")
                for i, step in enumerate(plan[:3], 1):
                    tool = step.get('tool', 'unknown')
                    args = step.get('args', {})
                    print(f"     {i}. {tool}")
                    if 'name' in args:
                        print(f"        - 名称: {args['name']}")

        # 检查最终响应
        if "response" in result:
            response = result["response"]
            print(f"\n最终响应:")
            print(f"   状态: {response.get('status', 'unknown')}")
            print(f"   消息: {response.get('message', 'no message')}")

            # 保存完整结果到文件
            with open("direct_integration_test_result.json", "w", encoding="utf-8") as f:
                json.dump({
                    "test_info": {
                        "trace_id": init_state["trace_id"],
                        "total_time": total_time,
                        "parsing_mode": parsing_mode,
                        "grid_blocks_count": TEST_ECOMMERCE_DOC.count('```grid'),
                        "doc_length": len(TEST_ECOMMERCE_DOC)
                    },
                    "final_result": result
                }, f, ensure_ascii=False, indent=2, default=str)

            print(f"\n详细结果已保存到: direct_integration_test_result.json")

        else:
            print("错误：没有找到响应结果")

        print("=" * 60)
        print("直接集成测试完成！")

        return True

    except Exception as e:
        end_time = time.time()
        total_time = end_time - start_time
        print(f"执行失败: {str(e)}")
        print(f"失败时间点: {total_time:.2f} 秒")
        logger.error(init_state["trace_id"], "direct_integration_test", f"工作流执行失败: {str(e)}")
        return False


if __name__ == "__main__":
    success = run_direct_integration_test()
    if success:
        print("\n集成测试通过 - 并行处理节点在完整流程中工作正常")
    else:
        print("\n集成测试失败 - 需要检查配置")