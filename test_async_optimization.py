#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步IO优化性能测试
对比并行处理和异步处理的性能差异
"""

import asyncio
import time
import json
import uuid
from typing import Dict, Any, List

from nodes.understand_doc_parallel import understand_doc as understand_doc_parallel
from nodes.understand_doc_async import understand_doc as understand_doc_async
from models.state import AgentState
from utils.logger import logger
from utils.llm_cache import get_llm_cache


# 复杂测试文档
COMPLEX_TEST_DOC = """
# 高复杂度电商系统设计文档

## 1. 用户管理模块

```grid
grid_column:
  - width_ratio: 40
    content: |
        ![用户管理界面](user_management.png)
  - width_ratio: 60
    content: |
        **查询条件**
        - 用户ID: userId
        - 用户名: username
        - 注册渠道: channel
        - 注册时间: createdTime
        - 用户状态: userStatus
        - 会员等级: memberLevel

        **显示字段**
        - 用户ID
        - 用户名
        - 邮箱
        - 手机号
        - 注册时间
        - 最后登录时间
        - 订单数量
        - 消费金额
```

## 2. 订单管理模块

```grid
grid_column:
  - width_ratio: 50
    content: |
        ![订单统计界面](order_statistics.png)
  - width_ratio: 50
    content: |
        **统计指标**
        - 订单总数: orderCount
        - 订单总金额: totalAmount
        - 平均客单价: avgOrderValue
        - 订单状态分布: statusDistribution
        - 退款率: refundRate
        - 完成率: completionRate

        **时间维度**
        - 日统计: daily
        - 周统计: weekly
        - 月统计: monthly
        - 季度统计: quarterly
```

## 3. 商品管理模块

```grid
grid_column:
  - width_ratio: 45
    content: |
        ![商品管理界面](product_management.png)
  - width_ratio: 55
    content: |
        **商品筛选条件**
        - 商品分类: category
        - 品牌ID: brandId
        - 价格区间: priceRange
        - 库存状态: stockStatus
        - 上架状态: listingStatus
        - 销量排名: salesRanking

        **商品信息字段**
        - 商品ID: productId
        - 商品名称: productName
        - 商品价格: price
        - 库存数量: stock
        - 销量: sales
        - 评分: rating
        - 评论数: reviewCount
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
        - 渠道维度: channelDimension

        **核心指标**
        - 转化率: conversionRate
        - 复购率: repurchaseRate
        - 用户留存率: retentionRate
        - 销售增长率: growthRate
        - 毛利率: grossMargin
        - 客单价增长率: avgOrderGrowth
```

## 5. 营销活动模块

```grid
grid_column:
  - width_ratio: 40
    content: |
        ![营销活动管理](marketing_campaign.png)
  - width_ratio: 60
    content: |
        **活动配置**
        - 活动类型: campaignType
        - 活动名称: campaignName
        - 开始时间: startTime
        - 结束时间: endTime
        - 预算金额: budgetAmount
        - 目标用户: targetUsers

        **效果指标**
        - 参与人数: participantCount
        - 转化率: conversionRate
        - ROI: returnOnInvestment
        - 分享次数: shareCount
```

## 6. 财务报表模块

```grid
grid_column:
  - width_ratio: 45
    content: |
        ![财务报表界面](financial_report.png)
  - width_ratio: 55
    content: |
        **报表类型**
        - 收入报表: revenueReport
        - 成本报表: costReport
        - 利润报表: profitReport
        - 现金流量表: cashFlowStatement

        **财务指标**
        - 总收入: totalRevenue
        - 净利润: netProfit
        - 毛利率: grossMargin
        - 净利率: netMargin
        - 资产回报率: roa
        - 净资产收益率: roe
```

## 7. 客服管理模块

```grid
grid_column:
  - width_ratio: 50
    content: |
        ![客服管理界面](customer_service.png)
  - width_ratio: 50
    content: |
        **服务指标**
        - 响应时间: responseTime
        - 解决率: resolutionRate
        - 满意度: satisfactionScore
        - 工单数量: ticketCount

        **客服字段**
        - 客服ID: agentId
        - 客服姓名: agentName
        - 技能组: skillGroup
        - 在线状态: onlineStatus
        - 工作时长: workingHours
```

## 8. 权限管理模块

```grid
grid_column:
  - width_ratio: 40
    content: |
        ![权限管理界面](permission_management.png)
  - width_ratio: 60
    content: |
        **权限配置**
        - 角色名称: roleName
        - 权限范围: permissionScope
        - 数据权限: dataPermission
        - 功能权限: functionPermission

        **管理字段**
        - 用户ID: userId
        - 角色ID: roleId
        - 权限代码: permissionCode
        - 有效期: validityPeriod
        - 创建时间: createTime
```
"""


def create_test_state(content: str, test_name: str) -> AgentState:
    """创建测试状态"""
    return {
        "feishu_urls": [f"https://example.com/test/{test_name}"],
        "user_intent": "generate_crud",
        "trace_id": f"async-test-{test_name}-{int(time.time())}",
        "raw_docs": [content],
        "feishu_blocks": [],
        "templates": []
    }


def measure_performance_sync(processor_func, test_name: str, state: AgentState) -> Dict[str, Any]:
    """测量同步处理器性能"""
    print(f"\n{'='*60}")
    print(f"测试 {test_name}")
    print(f"{'='*60}")

    start_time = time.time()

    try:
        result = processor_func(state)
        end_time = time.time()

        processing_time = end_time - start_time
        ism = result.get("ism", {})

        interfaces_count = len(ism.get("interfaces", []))
        pending_count = len(ism.get("__pending__", []))
        parsing_mode = ism.get("doc_meta", {}).get("parsing_mode", "unknown")

        print(f"{test_name} 测试成功!")
        print(f"处理时间: {processing_time:.2f} 秒")
        print(f"解析接口数: {interfaces_count}")
        print(f"待处理项: {pending_count}")
        print(f"解析模式: {parsing_mode}")

        return {
            "success": True,
            "test_name": test_name,
            "processing_time": processing_time,
            "interfaces_count": interfaces_count,
            "pending_count": pending_count,
            "parsing_mode": parsing_mode,
            "ism": ism,
            "result": result
        }

    except Exception as e:
        end_time = time.time()
        processing_time = end_time - start_time

        print(f"{test_name} 测试失败!")
        print(f"处理时间: {processing_time:.2f} 秒")
        print(f"错误信息: {str(e)}")

        return {
            "success": False,
            "test_name": test_name,
            "processing_time": processing_time,
            "error": str(e)
        }


async def measure_performance_async(processor_func, test_name: str, state: AgentState) -> Dict[str, Any]:
    """测量异步处理器性能"""
    print(f"\n{'='*60}")
    print(f"测试 {test_name}")
    print(f"{'='*60}")

    start_time = time.time()

    try:
        result = await processor_func(state)
        end_time = time.time()

        processing_time = end_time - start_time
        ism = result.get("ism", {})

        interfaces_count = len(ism.get("interfaces", []))
        pending_count = len(ism.get("__pending__", []))
        parsing_mode = ism.get("doc_meta", {}).get("parsing_mode", "unknown")

        print(f"{test_name} 测试成功!")
        print(f"处理时间: {processing_time:.2f} 秒")
        print(f"解析接口数: {interfaces_count}")
        print(f"待处理项: {pending_count}")
        print(f"解析模式: {parsing_mode}")

        return {
            "success": True,
            "test_name": test_name,
            "processing_time": processing_time,
            "interfaces_count": interfaces_count,
            "pending_count": pending_count,
            "parsing_mode": parsing_mode,
            "ism": ism,
            "result": result
        }

    except Exception as e:
        end_time = time.time()
        processing_time = end_time - start_time

        print(f"{test_name} 测试失败!")
        print(f"处理时间: {processing_time:.2f} 秒")
        print(f"错误信息: {str(e)}")

        return {
            "success": False,
            "test_name": test_name,
            "processing_time": processing_time,
            "error": str(e)
        }


async def run_async_optimization_test():
    """运行异步优化对比测试"""
    print("开始异步IO优化性能对比测试")
    print(f"测试文档包含 {COMPLEX_TEST_DOC.count('```grid')} 个grid块，"
          f"{len(COMPLEX_TEST_DOC)} 字符")

    # 清空缓存，确保测试的公平性
    cache = get_llm_cache()
    cache.clear()
    print("缓存已清空，确保测试公平性")

    results = []

    # 测试1: 并行处理（基准）
    print(f"\n{'='*80}")
    print("基准测试：并行处理")
    print(f"{'='*80}")

    parallel_state = create_test_state(COMPLEX_TEST_DOC, "parallel_baseline")
    parallel_result = measure_performance_sync(
        understand_doc_parallel, "并行处理（基准）", parallel_state
    )
    results.append(parallel_result)

    # 等待一下避免API限制
    await asyncio.sleep(3)

    # 测试2: 异步处理（首次，无缓存）
    print(f"\n{'='*80}")
    print(" 优化测试：异步处理（首次）")
    print(f"{'='*80}")

    async_state_first = create_test_state(COMPLEX_TEST_DOC, "async_first")
    async_result_first = await measure_performance_async(
        understand_doc_async, "异步处理（首次）", async_state_first
    )
    results.append(async_result_first)

    # 等待一下
    await asyncio.sleep(3)

    # 测试3: 异步处理（第二次，有缓存）
    print(f"\n{'='*80}")
    print(" 缓存测试：异步处理（缓存）")
    print(f"{'='*80}")

    async_state_cached = create_test_state(COMPLEX_TEST_DOC, "async_cached")
    async_result_cached = await measure_performance_async(
        understand_doc_async, "异步处理（缓存）", async_state_cached
    )
    results.append(async_result_cached)

    # 分析结果
    print(f"\n{'='*80}")
    print(" 异步优化性能对比分析")
    print(f"{'='*80}")

    successful_results = [r for r in results if r["success"]]

    if successful_results:
        print(f"{'方案':<20} {'时间(秒)':<10} {'接口数':<8} {'模式':<15} {'相对性能':<10} {'缓存效果':<10}")
        print("-" * 80)

        baseline_time = successful_results[0]["processing_time"]

        for result in successful_results:
            test_name = result["test_name"]
            processing_time = result["processing_time"]
            interfaces_count = result["interfaces_count"]
            parsing_mode = result["parsing_mode"]
            performance_ratio = processing_time / baseline_time

            # 计算缓存效果
            cache_effect = "N/A"
            if "缓存" in test_name and len(successful_results) > 1:
                first_async_time = next(r["processing_time"] for r in successful_results if "首次" in r["test_name"])
                cache_improvement = first_async_time / processing_time
                cache_effect = f"{cache_improvement:.2f}x"

            print(f"{test_name:<20} {processing_time:<10.2f} {interfaces_count:<8} "
                  f"{parsing_mode:<15} {performance_ratio:.2f}x     {cache_effect:<10}")

        # 性能提升分析
        if len(successful_results) >= 2:
            parallel_result = successful_results[0]
            async_result = successful_results[1]

            if parallel_result["success"] and async_result["success"]:
                improvement = parallel_result["processing_time"] / async_result["processing_time"]
                time_saved = parallel_result["processing_time"] - async_result["processing_time"]

                print(f"\n 性能对比结果:")
                print(f"   并行处理时间: {parallel_result['processing_time']:.2f} 秒")
                print(f"   异步处理时间: {async_result['processing_time']:.2f} 秒")
                print(f"   性能提升: {improvement:.2f}倍")
                print(f"   时间节省: {time_saved:.2f} 秒")

                # 缓存效果分析
                if len(successful_results) >= 3:
                    cached_result = successful_results[2]
                    if cached_result["success"]:
                        cache_improvement = async_result["processing_time"] / cached_result["processing_time"]
                        cache_time_saved = async_result["processing_time"] - cached_result["processing_time"]

                        print(f"\n 缓存效果分析:")
                        print(f"   首次异步时间: {async_result['processing_time']:.2f} 秒")
                        print(f"   缓存命中时间: {cached_result['processing_time']:.2f} 秒")
                        print(f"   缓存提升: {cache_improvement:.2f}倍")
                        print(f"   缓存节省: {cache_time_saved:.2f} 秒")

    # 缓存统计
    print(f"\n 缓存系统统计:")
    cache_stats = cache.get_stats()
    print(f"   总缓存条目: {cache_stats['total_entries']}")
    print(f"   有效缓存条目: {cache_stats['valid_entries']}")
    print(f"   总命中次数: {cache_stats['total_hits']}")
    print(f"   平均命中率: {cache_stats['avg_hits_per_entry']:.2f}")
    print(f"   缓存大小: {cache_stats['cache_size_mb']:.2f} MB")

    # 保存详细结果
    final_results = {
        "test_timestamp": time.time(),
        "test_document": {
            "grid_blocks_count": COMPLEX_TEST_DOC.count('```grid'),
            "content_length": len(COMPLEX_TEST_DOC)
        },
        "results": results,
        "analysis": {
            "successful_tests": len(successful_results),
            "cache_stats": cache_stats
        }
    }

    with open("async_optimization_test_results.json", "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n 详细测试结果已保存到: async_optimization_test_results.json")
    print("\n 异步IO优化性能测试完成!")


if __name__ == "__main__":
    asyncio.run(run_async_optimization_test())