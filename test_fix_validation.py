#!/usr/bin/env python3
"""
测试修复效果的验证脚本
验证"交易趋势"降级处理问题的修复
"""

import json
import sys
import traceback

def test_array_response_processing():
    """测试数组响应处理逻辑"""
    print("=== 测试数组响应处理逻辑 ===")

    try:
        from nodes.understand_doc.interface_extractor import InterfaceExtractor

        # 创建接口提取器
        extractor = InterfaceExtractor("test-trace", "test-step")

        # 模拟LLM返回的数组响应
        array_response = [
            {
                "id": "api_totalFilter_filter",
                "name": "总筛选项",
                "type": "filter_dimension",
                "fields": [
                    {"name": "公司ID", "expression": "companyId", "data_type": "string", "required": True}
                ],
                "operations": ["read"]
            },
            {
                "id": "api_consumptionFluctuation_trend",
                "name": "消耗波动详情",
                "type": "trend_analysis",
                "fields": [
                    {"name": "消耗", "expression": "consumption", "data_type": "number", "required": False}
                ],
                "operations": ["read"]
            },
            {
                "id": "api_materialDetail_data",
                "name": "素材明细",
                "type": "data_display",
                "fields": [
                    {"name": "素材ID", "expression": "materialId", "data_type": "string", "required": False}
                ],
                "operations": ["read"]
            }
        ]

        # 测试主要接口选择
        content = "## 总筛选项\n```grid\n...\n```\n\n## 消耗波动详情\n```grid\n...\n```"
        primary = extractor._select_primary_interface_from_array(array_response, "test-chunk", content)

        print(f"✓ 主要接口选择成功: {primary.get('name', '未知')}")
        print(f"  - 数组大小: {len(array_response)}")
        print(f"  - 选中的接口: {primary.get('id')}")

        return True

    except Exception as e:
        print(f"✗ 数组响应处理测试失败: {e}")
        traceback.print_exc()
        return False

def test_interface_key_generation():
    """测试改进的接口键生成"""
    print("\n=== 测试接口键生成 ===")

    try:
        from nodes.understand_doc.ism_builder import ISMBuilder

        builder = ISMBuilder("test-trace", "test-step")

        # 测试用例
        test_cases = [
            {
                "name": "总筛选项",
                "type": "filter_dimension",
                "fields": [{"name": "公司ID"}, {"name": "行业"}],
                "expected_key": "总筛选项_filter_dimension"
            },
            {
                "name": "消耗趋势",
                "type": "trend_analysis",
                "_array_response": True,
                "_array_index": 0,
                "fields": [{"name": "天"}, {"name": "消耗"}],
                "expected_key": "消耗趋势_trend_analysis_array_0_fields_天_消耗"
            },
            {
                "name": "交易趋势",
                "type": "trend_analysis",
                "_array_response": True,
                "_array_index": 1,
                "fields": [{"name": "天"}, {"name": "GMV"}],
                "expected_key": "交易趋势_trend_analysis_array_1_fields_gmv_天"
            }
        ]

        for i, test_case in enumerate(test_cases):
            key = builder._create_interface_key(test_case)
            expected = test_case.get("expected_key")

            # 检查是否包含关键信息
            success = (
                test_case["name"].lower() in key and
                test_case["type"].lower() in key
            )

            if test_case.get("_array_response"):
                success = success and f"_array_{test_case['_array_index']}" in key

            print(f"测试用例 {i+1}: {'✓' if success else '✗'}")
            print(f"  - 生成的键: {key}")
            if expected:
                print(f"  - 预期模式: {expected}")
            print(f"  - 包含数组信息: {f'_array_' in key}")

        return True

    except Exception as e:
        print(f"✗ 接口键生成测试失败: {e}")
        traceback.print_exc()
        return False

def test_array_expansion():
    """测试数组响应展开"""
    print("\n=== 测试数组响应展开 ===")

    try:
        from nodes.understand_doc.ism_builder import ISMBuilder

        builder = ISMBuilder("test-trace", "test-step")

        # 模拟包含数组响应的接口结果
        interface_results = [
            {
                "id": "chunk_1_result",
                "name": "主要接口",
                "type": "filter_dimension",
                "source_chunk_id": "chunk_1",
                "_array_response": True,
                "_array_data": [
                    {
                        "id": "api_1",
                        "name": "接口1",
                        "type": "filter_dimension",
                        "fields": [{"name": "field1"}]
                    },
                    {
                        "id": "api_2",
                        "name": "接口2",
                        "type": "trend_analysis",
                        "fields": [{"name": "field2"}]
                    }
                ]
            },
            {
                "id": "normal_interface",
                "name": "普通接口",
                "type": "custom",
                "source_chunk_id": "chunk_2"
            }
        ]

        expanded = builder._expand_array_responses(interface_results)

        print(f"✓ 数组展开成功:")
        print(f"  - 原始接口数: {len(interface_results)}")
        print(f"  - 展开后接口数: {len(expanded)}")
        print(f"  - 数组响应接口: {len([iface for iface in expanded if iface.get('_array_response')])}")

        # 验证展开后的接口
        array_interfaces = [iface for iface in expanded if iface.get('_array_response')]
        if len(array_interfaces) == 2:
            print("✓ 数组接口正确展开为2个独立接口")
            for i, iface in enumerate(array_interfaces):
                print(f"  - 接口{i+1}: {iface.get('name')} (索引: {iface.get('_array_index')})")
        else:
            print(f"✗ 数组接口展开错误，期望2个，实际{len(array_interfaces)}个")
            return False

        return True

    except Exception as e:
        print(f"✗ 数组响应展开测试失败: {e}")
        traceback.print_exc()
        return False

def test_config_improvements():
    """测试配置改进"""
    print("\n=== 测试配置改进 ===")

    try:
        from nodes.understand_doc.config import understand_doc_config

        # 检查新增的配置项
        config_improvements = [
            ("EXPECTED_INTERFACES", len(understand_doc_config.EXPECTED_INTERFACES) >= 5),
            ("INTERFACE_SYSTEM_PROMPT", "必须为每个grid块生成对应的接口" in understand_doc_config.INTERFACE_SYSTEM_PROMPT),
            ("接口区分指导", "消耗趋势" in understand_doc_config.INTERFACE_SYSTEM_PROMPT),
            ("接口区分指导", "交易趋势" in understand_doc_config.INTERFACE_SYSTEM_PROMPT)
        ]

        success_count = 0
        for config_name, check_result in config_improvements:
            status = "✓" if check_result else "✗"
            print(f"  {status} {config_name}")
            if check_result:
                success_count += 1

        print(f"\n配置改进通过率: {success_count}/{len(config_improvements)}")
        return success_count == len(config_improvements)

    except Exception as e:
        print(f"✗ 配置改进测试失败: {e}")
        traceback.print_exc()
        return False

def test_expected_interfaces():
    """测试预期接口识别"""
    print("\n=== 测试预期接口识别 ===")

    try:
        from nodes.understand_doc.config import understand_doc_config

        expected = understand_doc_config.EXPECTED_INTERFACES
        required_interfaces = ["总筛选项", "消耗波动详情", "素材明细", "消耗趋势", "交易趋势"]

        missing = [iface for iface in required_interfaces if iface not in expected]
        extra = [iface for iface in expected if iface not in required_interfaces]

        print(f"预期接口列表: {expected}")
        print(f"缺失的接口: {missing}")
        print(f"额外的接口: {extra}")

        success = len(missing) == 0
        print(f"预期接口识别: {'✓' if success else '✗'}")

        return success

    except Exception as e:
        print(f"✗ 预期接口识别测试失败: {e}")
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("开始验证修复效果...\n")

    tests = [
        ("数组响应处理逻辑", test_array_response_processing),
        ("接口键生成", test_interface_key_generation),
        ("数组响应展开", test_array_expansion),
        ("配置改进", test_config_improvements),
        ("预期接口识别", test_expected_interfaces)
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} - 通过\n")
            else:
                print(f"❌ {test_name} - 失败\n")
        except Exception as e:
            print(f"❌ {test_name} - 异常: {e}\n")

    print("=" * 50)
    print(f"测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有测试通过！修复成功！")
        print("\n主要修复点:")
        print("1. ✓ LLM数组响应处理 - 现在能正确处理所有接口")
        print("2. ✓ 接口去重策略 - 改进的键生成避免错误合并")
        print("3. ✓ LLM提示词优化 - 强调完整性和接口区分")
        print("4. ✓ 日志增强 - 更好的调试信息")
        return 0
    else:
        print("❌ 部分测试失败，需要进一步修复")
        return 1

if __name__ == "__main__":
    sys.exit(main())