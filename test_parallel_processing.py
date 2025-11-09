#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
并行处理性能测试脚本
对比单次LLM调用与并行LLM调用的性能差异
"""

import time
import json
from typing import Dict, Any, List
from nodes.understand_doc import understand_doc as understand_doc_single
from nodes.understand_doc_parallel import understand_doc_parallel
from models.state import AgentState
from utils.logger import logger


# 模拟包含多个接口的测试文档
TEST_DOCUMENT_WITH_MULTIPLE_INTERFACES = """
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


def create_test_state(document_content: str, test_name: str) -> AgentState:
    """创建测试用的AgentState"""
    return {
        "trace_id": f"test_{test_name}_{int(time.time())}",
        "raw_docs": [document_content],
        "feishu_urls": [f"https://example.com/test/{test_name}"],
        "feishu_blocks": [],
        "templates": []
    }


def measure_processing_time(processor_func, state: AgentState, processor_name: str) -> Dict[str, Any]:
    """测量处理时间并返回结果"""
    print(f"\n{'='*50}")
    print(f"测试 {processor_name} 处理...")
    print(f"{'='*50}")

    start_time = time.time()

    try:
        result_state = processor_func(state)
        end_time = time.time()

        processing_time = end_time - start_time
        ism = result_state.get("ism", {})

        # 统计结果
        interfaces_count = len(ism.get("interfaces", []))
        pending_count = len(ism.get("__pending__", []))

        print(f"{processor_name} 处理成功!")
        print(f"处理时间: {processing_time:.2f} 秒")
        print(f"解析接口数: {interfaces_count}")
        print(f"待处理项: {pending_count}")

        return {
            "success": True,
            "processing_time": processing_time,
            "interfaces_count": interfaces_count,
            "pending_count": pending_count,
            "ism": ism,
            "result_state": result_state
        }

    except Exception as e:
        end_time = time.time()
        processing_time = end_time - start_time

        print(f"{processor_name} 处理失败!")
        print(f"处理时间: {processing_time:.2f} 秒")
        print(f"错误信息: {str(e)}")

        return {
            "success": False,
            "processing_time": processing_time,
            "error": str(e)
        }


def compare_results(single_result: Dict, parallel_result: Dict) -> None:
    """对比两种处理方法的结果"""
    print(f"\n{'='*50}")
    print("性能对比结果")
    print(f"{'='*50}")

    if single_result["success"] and parallel_result["success"]:
        # 性能对比
        time_improvement = single_result["processing_time"] - parallel_result["processing_time"]
        speedup_ratio = single_result["processing_time"] / parallel_result["processing_time"]

        print(f"单次处理时间: {single_result['processing_time']:.2f} 秒")
        print(f"并行处理时间: {parallel_result['processing_time']:.2f} 秒")
        print(f"时间节省: {time_improvement:.2f} 秒")
        print(f"加速比: {speedup_ratio:.2f}x")

        # 结果质量对比
        print(f"\n结果质量对比:")
        print(f"   单次处理接口数: {single_result['interfaces_count']}")
        print(f"   并行处理接口数: {parallel_result['interfaces_count']}")
        print(f"   单次处理待处理项: {single_result['pending_count']}")
        print(f"   并行处理待处理项: {parallel_result['pending_count']}")

        # 显示解析的接口
        print(f"\n解析的接口详情:")
        single_ism = single_result["ism"]
        parallel_ism = parallel_result["ism"]

        print(f"\n单次处理解析的接口:")
        for i, interface in enumerate(single_ism.get("interfaces", [])[:3], 1):
            print(f"   {i}. {interface.get('name', 'Unknown')} ({interface.get('type', 'Unknown')})")

        print(f"\n并行处理解析的接口:")
        for i, interface in enumerate(parallel_ism.get("interfaces", [])[:3], 1):
            print(f"   {i}. {interface.get('name', 'Unknown')} ({interface.get('type', 'Unknown')})")

        if len(parallel_ism.get("interfaces", [])) > 3:
            remaining = len(parallel_ism.get("interfaces", [])) - 3
            print(f"   ... 还有 {remaining} 个接口")

    else:
        print("处理结果对比失败，至少有一个方法处理失败")
        if not single_result["success"]:
            print(f"   单次处理失败: {single_result.get('error', 'Unknown error')}")
        if not parallel_result["success"]:
            print(f"   并行处理失败: {parallel_result.get('error', 'Unknown error')}")


def run_performance_test():
    """运行性能测试"""
    print("开始并行处理性能测试")
    print(f"测试文档包含 {TEST_DOCUMENT_WITH_MULTIPLE_INTERFACES.count('```grid')} 个grid块")

    # 创建测试状态
    single_state = create_test_state(TEST_DOCUMENT_WITH_MULTIPLE_INTERFACES, "single")
    parallel_state = create_test_state(TEST_DOCUMENT_WITH_MULTIPLE_INTERFACES, "parallel")

    # 测试单次处理
    single_result = measure_processing_time(
        understand_doc_single,
        single_state,
        "单次LLM调用"
    )

    # 等待一下避免API限制
    time.sleep(2)

    # 测试并行处理
    parallel_result = measure_processing_time(
        understand_doc_parallel,
        parallel_state,
        "并行LLM调用"
    )

    # 对比结果
    compare_results(single_result, parallel_result)

    # 保存详细结果到文件
    results = {
        "test_timestamp": time.time(),
        "document_info": {
            "grid_blocks_count": TEST_DOCUMENT_WITH_MULTIPLE_INTERFACES.count('```grid'),
            "content_length": len(TEST_DOCUMENT_WITH_MULTIPLE_INTERFACES)
        },
        "single_processing": single_result,
        "parallel_processing": parallel_result
    }

    with open("parallel_processing_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n详细测试结果已保存到: parallel_processing_test_results.json")
    print("\n性能测试完成!")


if __name__ == "__main__":
    run_performance_test()