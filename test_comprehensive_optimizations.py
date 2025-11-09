#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合优化测试
测试所有优化方案的性能表现
"""

import asyncio
import time
import json
import uuid
from typing import Dict, Any, List

# 导入所有优化版本
from nodes.understand_doc_original import understand_doc as understand_doc_original
from nodes.understand_doc_parallel import understand_doc as understand_doc_parallel
from nodes.understand_doc_async import understand_doc as understand_doc_async
from nodes.understand_doc_streaming_v2 import understand_doc as understand_doc_streaming_v2

from models.state import AgentState
from utils.logger import logger
from utils.llm_cache import get_llm_cache
from utils.predictive_cache import get_predictive_cache
from utils.adaptive_batching import get_adaptive_optimizer
from utils.model_load_balancer import get_model_load_balancer


# 超复杂测试文档
ULTRA_COMPLEX_TEST_DOC = """
# 超级复杂企业级平台设计文档

## 1. 用户中心模块

```grid
grid_column:
  - width_ratio: 35
    content: |
        ![用户中心界面](user_center.png)
  - width_ratio: 65
    content: |
        **基础查询条件**
        - 用户ID: userId
        - 用户名: username
        - 手机号: phone
        - 邮箱: email
        - 注册渠道: channel
        - 注册时间: createdTime
        - 用户状态: userStatus
        - 会员等级: memberLevel
        - 用户标签: userTags

        **高级筛选条件**
        - 消费金额范围: amountRange
        - 最后活跃时间: lastActiveTime
        - 注册城市: regCity
        - 设备类型: deviceType
        - VIP等级: vipLevel
        - 风险等级: riskLevel

        **显示字段**
        - 用户ID
        - 用户名
        - 手机号
        - 邮箱
        - 注册时间
        - 最后登录时间
        - 消费金额
        - 订单数量
        - 会员积分
        - 风险评级
```

## 2. 订单分析模块

```grid
grid_column:
  - width_ratio: 40
    content: |
        ![订单分析界面](order_analysis.png)
  - width_ratio: 60
    content: |
        **时间维度分析**
        - 实时统计: realtime
        - 小时统计: hourly
        - 日统计: daily
        - 周统计: weekly
        - 月统计: monthly
        - 季度统计: quarterly
        - 年度统计: yearly

        **核心业务指标**
        - 订单总数: totalOrders
        - 订单总金额: totalAmount
        - 平均客单价: avgOrderValue
        - 订单完成率: completionRate
        - 退款率: refundRate
        - 取消率: cancellationRate
        - 复购率: repurchaseRate
        - 客户生命周期价值: clv

        **转化漏斗指标**
        - 浏览量转化率: viewToOrderRate
        - 加购转化率: addToCartRate
        - 结算转化率: checkoutRate
        - 支付转化率: paymentRate
```

## 3. 商品管理模块

```grid
grid_column:
  - width_ratio: 45
    content: |
        ![商品管理界面](product_management.png)
  - width_ratio: 55
    content: |
        **商品基础筛选**
        - 商品分类: category
        - 品牌ID: brandId
        - 商品状态: productStatus
        - 上架状态: listingStatus
        - 库存状态: stockStatus
        - 价格区间: priceRange
        - 销量排名: salesRanking
        - 评分区间: ratingRange

        **高级筛选条件**
        - 供应商ID: supplierId
        - 成本区间: costRange
        - 毛利率区间: marginRange
        - 季节性商品: seasonalProduct
        - 新品标识: isNewProduct
        - 热销标识: isBestseller
        - 促销标识: isOnPromotion

        **商品信息字段**
        - 商品ID: productId
        - 商品名称: productName
        - 商品编码: productCode
        - 商品条码: barcode
        - 商品价格: price
        - 成本价格: costPrice
        - 库存数量: stock
        - 安全库存: safetyStock
        - 销量: sales
        - 评分: rating
        - 评论数: reviewCount
```

## 4. 营销活动模块

```grid
grid_column:
  - width_ratio: 40
    content: |
        ![营销活动管理](marketing_campaign.png)
  - width_ratio: 60
    content: |
        **活动基本信息**
        - 活动类型: campaignType
        - 活动名称: campaignName
        - 活动描述: description
        - 开始时间: startTime
        - 结束时间: endTime
        - 预算金额: budgetAmount
        - 实际花费: actualSpend

        **目标设置**
        - 目标用户群体: targetAudience
        - 参与人数目标: participantTarget
        - 转化率目标: conversionTarget
        - ROI目标: roiTarget
        - 销售额目标: salesTarget

        **活动效果指标**
        - 参与人数: participantCount
        - 点击次数: clickCount
        - 转化次数: conversionCount
        - 转化率: conversionRate
        - 投资回报率: roi
        - 活动分享次数: shareCount
        - 活动裂变系数: viralCoefficient
```

## 5. 财务报表模块

```grid
grid_column:
  - width_ratio: 50
    content: |
        ![财务报表界面](financial_report.png)
  - width_ratio: 50
    content: |
        **收入分析**
        - 总收入: totalRevenue
        - 产品收入: productRevenue
        - 服务收入: serviceRevenue
        - 订阅收入: subscriptionRevenue
        - 广告收入: adRevenue
        - 其他收入: otherRevenue

        **成本分析**
        - 总成本: totalCost
        - 产品成本: productCost
        - 运营成本: operationalCost
        - 营销成本: marketingCost
        - 人力成本: laborCost
        - 技术成本: techCost

        **利润指标**
        - 毛利润: grossProfit
        - 毛利率: grossMargin
        - 净利润: netProfit
        - 净利率: netMargin
        - 营业利润: operatingProfit
        - EBITDA: ebitda

        **财务比率**
        - 资产回报率: roa
        - 净资产收益率: roe
        - 流动比率: currentRatio
        - 速动比率: quickRatio
        - 负债权益比: debtToEquity
```

## 6. 客服管理模块

```grid
grid_column:
  - width_ratio: 45
    content: |
        ![客服管理界面](customer_service.png)
  - width_ratio: 55
    content: |
        **客服团队管理**
        - 客服ID: agentId
        - 客服姓名: agentName
        - 技能组: skillGroup
        - 工号: agentNumber
        - 在线状态: onlineStatus
        - 工作状态: workingStatus
        - 工作时长: workingHours

        **服务质量指标**
        - 平均响应时间: avgResponseTime
        - 首次响应时间: firstResponseTime
        - 平均处理时间: avgHandleTime
        - 解决率: resolutionRate
        - 满意度: satisfactionScore
        - 客户评价评分: customerRating
        - 工单完成数: completedTickets

        **客服工作量统计**
        - 日处理工单数: dailyTickets
        - 周处理工单数: weeklyTickets
        - 月处理工单数: monthlyTickets
        - 平均在线时长: avgOnlineTime
        - 工作效率评分: efficiencyScore
```

## 7. 数据分析仪表板

```grid
grid_column:
  - width_ratio: 50
    content: |
        ![数据分析仪表板](analytics_dashboard.png)
  - width_ratio: 50
    content: |
        **用户行为分析**
        - 用户维度: userDimension
        - 地域维度: regionDimension
        - 设备维度: deviceDimension
        - 渠道维度: channelDimension
        - 时间维度: timeDimension

        **业务核心指标**
        - 日活跃用户: dau
        - 月活跃用户: mau
        - 用户留存率: retentionRate
        - 用户流失率: churnRate
        - 付费转化率: paidConversionRate
        - 用户生命周期价值: ltv

        **实时监控指标**
        - 实时在线用户: onlineUsers
        - 实时订单数: realtimeOrders
        - 实时交易额: realtimeRevenue
        - 系统响应时间: responseTime
        - 错误率: errorRate
        - 异常告警数: alertCount
```

## 8. 仓储物流模块

```grid
grid_column:
  - width_ratio: 40
    content: |
        ![仓储物流管理](warehouse_logistics.png)
  - width_ratio: 60
    content: |
        **仓库管理**
        - 仓库ID: warehouseId
        - 仓库名称: warehouseName
        - 仓库地址: warehouseAddress
        - 仓库类型: warehouseType
        - 存储容量: storageCapacity
        - 当前库存: currentStock

        **库存管理**
        - 商品SKU: productSku
        - 库存数量: stockQuantity
        - 安全库存: safetyStock
        - 库存预警级别: stockAlertLevel
        - 库存周转率: turnoverRate
        - 库存成本: inventoryCost

        **物流配送**
        - 配送方式: deliveryMethod
        - 配送状态: deliveryStatus
        - 物流公司: logisticsCompany
        - 运单号: trackingNumber
        - 配送时效: deliveryTime
        - 配送成本: deliveryCost
```

## 9. 权限管理模块

```grid
grid_column:
  - width_ratio: 35
    content: |
        ![权限管理界面](permission_management.png)
  - width_ratio: 65
    content: |
        **角色管理**
        - 角色ID: roleId
        - 角色名称: roleName
        - 角色描述: roleDescription
        - 角色状态: roleStatus
        - 创建时间: createTime
        - 角色权限数量: permissionCount

        **权限配置**
        - 数据权限: dataPermission
        - 功能权限: functionPermission
        - 操作权限: actionPermission
        - 时间权限: timePermission
        - 地域权限: regionPermission
        - 部门权限: departmentPermission

        **用户权限管理**
        - 用户ID: userId
        - 分配角色: assignedRoles
        - 特殊权限: specialPermissions
        - 权限生效时间: effectiveTime
        - 权限过期时间: expireTime
```

## 10. 导出报表模块

```grid
grid_column:
  - width_ratio: 45
    content: |
        ![导出报表界面](export_report.png)
  - width_ratio: 55
    content: |
        **报表类型**
        - 用户报表: userReport
        - 订单报表: orderReport
        - 商品报表: productReport
        - 财务报表: financialReport
        - 营销报表: marketingReport
        - 客服报表: serviceReport
        - 物流报表: logisticsReport

        **导出配置**
        - 报表类型: reportType
        - 导出格式: exportFormat
        - 时间范围: dateRange
        - 数据范围: dataScope
        - 字段选择: fieldSelection
        - 筛选条件: filterConditions

        **导出设置**
        - 导出语言: exportLanguage
        - 数据精度: dataPrecision
        - 文件编码: fileEncoding
        - 分页设置: paginationSetting
        - 排序规则: sortRules
```
"""


def create_test_state(content: str, test_name: str) -> AgentState:
    """创建测试状态"""
    return {
        "feishu_urls": [f"https://example.com/test/{test_name}"],
        "user_intent": "generate_crud",
        "trace_id": f"comprehensive-test-{test_name}-{int(time.time())}",
        "raw_docs": [content],
        "feishu_blocks": [],
        "templates": []
    }


def measure_performance_sync(processor_func, test_name: str, state: AgentState) -> Dict[str, Any]:
    """测量同步处理器性能"""
    print(f"\n{'='*80}")
    print(f"测试 {test_name}")
    print(f"{'='*80}")

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
    print(f"\n{'='*80}")
    print(f"测试 {test_name}")
    print(f"{'='*80}")

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


async def run_comprehensive_optimization_test():
    """运行综合优化对比测试"""
    print("开始综合优化对比测试")
    print(f"测试文档包含 {ULTRA_COMPLEX_TEST_DOC.count('```grid')} 个grid块，"
          f"{len(ULTRA_COMPLEX_TEST_DOC)} 字符")

    # 清空所有缓存，确保测试公平性
    try:
        cache = get_llm_cache()
        cache.clear()
        print("LLM缓存已清空")
    except:
        pass

    try:
        predictive_cache = get_predictive_cache()
        print("预测缓存系统已准备")
    except:
        pass

    results = []

    # 测试配置
    test_configs = [
        ("原始单次处理", understand_doc_original),
        ("并行处理", understand_doc_parallel),
        ("异步处理", understand_doc_async),
        ("高级流式处理", understand_doc_streaming_v2),
    ]

    # 依次测试每个版本
    for test_name, processor in test_configs:
        print(f"\n{'='*100}")
        print(f"测试 {test_name}")
        print(f"{'='*100}")

        state = create_test_state(ULTRA_COMPLEX_TEST_DOC, test_name.replace(" ", "_").lower())

        if "异步" in test_name or "流式" in test_name:
            # 异步测试
            result = await measure_performance_async(processor, test_name, state)
        else:
            # 同步测试
            result = measure_performance_sync(processor, test_name, state)

        results.append(result)

        # 等待一下避免API限制
        await asyncio.sleep(5)

    # 分析结果
    print(f"\n{'='*100}")
    print("综合优化性能对比分析")
    print(f"{'='*100}")

    successful_results = [r for r in results if r["success"]]
    failed_results = [r for r in results if not r["success"]]

    if successful_results:
        print(f"{'方案':<20} {'时间(秒)':<10} {'接口数':<8} {'模式':<15} {'相对性能':<10} {'优化等级':<10}")
        print("-" * 100)

        baseline_time = successful_results[0]["processing_time"]

        # 定义优化等级
        def get_optimization_level(improvement_ratio):
            if improvement_ratio >= 5.0:
                return "A+"
            elif improvement_ratio >= 3.0:
                return "A"
            elif improvement_ratio >= 2.0:
                return "B+"
            elif improvement_ratio >= 1.5:
                return "B"
            elif improvement_ratio >= 1.2:
                return "C+"
            else:
                return "C"

        for result in successful_results:
            test_name = result["test_name"]
            processing_time = result["processing_time"]
            interfaces_count = result["interfaces_count"]
            parsing_mode = result["parsing_mode"]
            performance_ratio = baseline_time / processing_time
            optimization_level = get_optimization_level(performance_ratio)

            print(f"{test_name:<20} {processing_time:<10.2f} {interfaces_count:<8} "
                  f"{parsing_mode:<15} {performance_ratio:.2f}x     {optimization_level:<10}")

        # 性能提升分析
        best_result = successful_results[0]
        worst_result = successful_results[-1]

        if len(successful_results) >= 2:
            overall_improvement = worst_result["processing_time"] / best_result["processing_time"]
            time_saved = worst_result["processing_time"] - best_result["processing_time"]

            print(f"\n性能对比总结:")
            print(f"   最快方案: {best_result['test_name']} ({best_result['processing_time']:.2f}秒)")
            print(f"   最慢方案: {worst_result['test_name']} ({worst_result['processing_time']:.2f}秒)")
            print(f"   总体提升: {overall_improvement:.2f}倍")
            print(f"   时间节省: {time_saved:.2f}秒")

            # 缓存和优化系统统计
            print(f"\n系统优化统计:")
            try:
                cache_stats = get_llm_cache().get_stats()
                print(f"   LLM缓存条目: {cache_stats['total_entries']}")
                print(f"   缓存命中率: {cache_stats['avg_hits_per_entry']:.2f}")
            except:
                pass

            try:
                predictive_stats = get_predictive_cache().get_cache_statistics()
                print(f"   预测缓存模式: {predictive_stats['total_patterns']}")
                print(f"   平均请求频率: {predictive_stats['avg_frequency']:.2f}")
            except:
                pass

            try:
                optimizer_stats = get_adaptive_optimizer().get_performance_report()
                if "performance_summary" in optimizer_stats:
                    summary = optimizer_stats["performance_summary"]
                    print(f"   自适应批处理: 平均处理时间 {summary['avg_processing_time']:.2f}s")
                    print(f"   自适应批处理: 平均吞吐量 {summary['avg_throughput']:.2f} interfaces/s")
            except:
                pass

            try:
                model_status = get_model_load_balancer().get_model_status()
                print(f"   可用模型数: {len(model_status)}")
                for model_name, status in model_status.items():
                    print(f"   {model_name}: {status['status']} (成功率: {status['success_rate']:.2f})")
            except:
                pass

    if failed_results:
        print(f"\n失败的测试:")
        for result in failed_results:
            print(f"   - {result['test_name']}: {result['error']}")

    # 保存详细结果
    final_results = {
        "test_timestamp": time.time(),
        "test_document": {
            "grid_blocks_count": ULTRA_COMPLEX_TEST_DOC.count('```grid'),
            "content_length": len(ULTRA_COMPLEX_TEST_DOC)
        },
        "results": results,
        "analysis": {
            "successful_tests": len(successful_results),
            "failed_tests": len(failed_results),
            "total_improvement": worst_result["processing_time"] / best_result["processing_time"] if successful_results else 0
        }
    }

    with open("comprehensive_optimization_test_results.json", "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n详细测试结果已保存到: comprehensive_optimization_test_results.json")
    print("\n综合优化对比测试完成!")


if __name__ == "__main__":
    asyncio.run(run_comprehensive_optimization_test())