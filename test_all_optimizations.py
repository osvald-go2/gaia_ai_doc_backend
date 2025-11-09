#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全方案优化对比测试
测试所有优化方案的性能表现
"""

import time
import json
import asyncio
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

# 导入所有版本的处理器
from nodes.understand_doc_original import understand_doc as understand_doc_original
from nodes.understand_doc_parallel import understand_doc as understand_doc_parallel
from nodes.understand_doc_async import understand_doc as understand_doc_async
from nodes.understand_doc_streaming import understand_doc as understand_doc_streaming

# 导入优化工具
from utils.llm_cache import get_llm_cache
from utils.batch_optimizer import get_batch_optimizer


# 测试用的复杂文档
COMPLEX_TEST_DOC = """
# 复杂电商系统设计文档

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


def create_test_state(content: str, test_name: str) -> Dict[str, Any]:
    """创建测试状态"""
    return {
        "feishu_urls": [f"https://example.com/test/{test_name}"],
        "user_intent": "generate_crud",
        "trace_id": f"test-{test_name}-{int(time.time())}",
        "raw_docs": [content],
        "feishu_blocks": [],
        "templates": []
    }


def measure_performance(processor_func, test_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """测量处理器性能"""
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

        print(f"✅ {test_name} 测试成功!")
        print(f"⏱️  处理时间: {processing_time:.2f} 秒")
        print(f"📊 解析接口数: {interfaces_count}")
        print(f"⚠️  待处理项: {pending_count}")
        print(f"🔧 解析模式: {parsing_mode}")

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

        print(f"❌ {test_name} 测试失败!")
        print(f"⏱️  处理时间: {processing_time:.2f} 秒")
        print(f"🚨 错误信息: {str(e)}")

        return {
            "success": False,
            "test_name": test_name,
            "processing_time": processing_time,
            "error": str(e)
        }


async def test_async_processor(test_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """测试异步处理器"""
    print(f"\n{'='*60}")
    print(f"测试 {test_name}")
    print(f"{'='*60}")

    start_time = time.time()

    try:
        result = await understand_doc_async(state)
        end_time = time.time()

        processing_time = end_time - start_time
        ism = result.get("ism", {})

        interfaces_count = len(ism.get("interfaces", []))
        pending_count = len(ism.get("__pending__", []))
        parsing_mode = ism.get("doc_meta", {}).get("parsing_mode", "unknown")

        print(f"✅ {test_name} 测试成功!")
        print(f"⏱️  处理时间: {processing_time:.2f} 秒")
        print(f"📊 解析接口数: {interfaces_count}")
        print(f"⚠️  待处理项: {pending_count}")
        print(f"🔧 解析模式: {parsing_mode}")

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

        print(f"❌ {test_name} 测试失败!")
        print(f"⏱️  处理时间: {processing_time:.2f} 秒")
        print(f"🚨 错误信息: {str(e)}")

        return {
            "success": False,
            "test_name": test_name,
            "processing_time": processing_time,
            "error": str(e)
        }


async def run_comprehensive_test():
    """运行全面的优化对比测试"""
    print("🚀 开始全方案优化对比测试")
    print(f"📄 测试文档包含 {COMPLEX_TEST_DOC.count('```grid')} 个grid块，"
          f"{len(COMPLEX_TEST_DOC)} 字符")

    # 测试配置
    test_configs = [
        ("原始单次处理", understand_doc_original),
        ("并行处理", understand_doc_parallel),
        ("流式处理", understand_doc_streaming),
    ]

    results = []

    # 同步测试
    for test_name, processor in test_configs:
        state = create_test_state(COMPLEX_TEST_DOC, test_name.replace(" ", "_").lower())
        result = measure_performance(processor, test_name, state)
        results.append(result)

        # 等待一下避免API限制
        await asyncio.sleep(2)

    # 异步测试
    async_test_configs = [
        ("异步处理", understand_doc_async),
    ]

    for test_name, processor in async_test_configs:
        state = create_test_state(COMPLEX_TEST_DOC, test_name.replace(" ", "_").lower())
        result = await test_async_processor(test_name, state)
        results.append(result)

        await asyncio.sleep(2)

    # 分析结果
    print(f"\n{'='*80}")
    print("📊 优化方案性能对比分析")
    print(f"{'='*80}")

    successful_results = [r for r in results if r["success"]]
    failed_results = [r for r in results if not r["success"]]

    if successful_results:
        # 按处理时间排序
        successful_results.sort(key=lambda x: x["processing_time"])

        print(f"{'方案':<15} {'时间(秒)':<10} {'接口数':<8} {'解析模式':<15} {'相对性能':<10}")
        print("-" * 80)

        baseline_time = successful_results[0]["processing_time"]

        for result in successful_results:
            test_name = result["test_name"]
            processing_time = result["processing_time"]
            interfaces_count = result["interfaces_count"]
            parsing_mode = result["parsing_mode"]
            performance_ratio = processing_time / baseline_time

            print(f"{test_name:<15} {processing_time:<10.2f} {interfaces_count:<8} "
                  f"{parsing_mode:<15} {performance_ratio:.2f}x")

        # 性能提升分析
        best_result = successful_results[0]
        worst_result = successful_results[-1]
        improvement = worst_result["processing_time"] / best_result["processing_time"]

        print(f"\n🏆 性能最佳方案: {best_result['test_name']} ({best_result['processing_time']:.2f}秒)")
        print(f"📈 最大性能提升: {improvement:.2f}倍")
        print(f"⚡ 时间节省: {worst_result['processing_time'] - best_result['processing_time']:.2f}秒")

    if failed_results:
        print(f"\n❌ 失败的测试:")
        for result in failed_results:
            print(f"   - {result['test_name']}: {result['error']}")

    # 缓存统计
    print(f"\n📦 缓存系统统计:")
    cache = get_llm_cache()
    cache_stats = cache.get_stats()
    print(f"   总缓存条目: {cache_stats['total_entries']}")
    print(f"   有效缓存条目: {cache_stats['valid_entries']}")
    print(f"   总命中次数: {cache_stats['total_hits']}")
    print(f"   平均命中率: {cache_stats['avg_hits_per_entry']:.2f}")

    # 批处理优化器统计
    print(f"\n🎯 批处理优化器统计:")
    optimizer = get_batch_optimizer()
    optimizer_stats = optimizer.get_performance_summary()
    if "total_records" in optimizer_stats:
        print(f"   性能记录数: {optimizer_stats['total_records']}")
        print(f"   平均成功率: {optimizer_stats['avg_success_rate']:.2f}")
        print(f"   平均处理时间: {optimizer_stats['avg_processing_time']:.2f}秒")
        print(f"   性能趋势: {optimizer_stats['performance_trend']}")

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
            "failed_tests": len(failed_results),
            "best_performance": successful_results[0]["test_name"] if successful_results else None,
            "max_improvement": improvement if successful_results else 0,
            "cache_stats": cache_stats,
            "optimizer_stats": optimizer_stats
        }
    }

    with open("comprehensive_optimization_test_results.json", "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n💾 详细测试结果已保存到: comprehensive_optimization_test_results.json")
    print("\n🎉 全方案优化对比测试完成!")


if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())