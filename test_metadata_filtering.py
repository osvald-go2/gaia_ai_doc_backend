#!/usr/bin/env python3
"""
测试元数据接口过滤逻辑
验证系统能够正确过滤掉文档头部信息接口
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'nodes'))

def test_metadata_interface_filtering():
    """测试元数据接口过滤逻辑"""
    print("=== 测试元数据接口过滤逻辑 ===")

    # 导入必要的模块
    from understand_doc.ism_builder import ISMBuilder
    from understand_doc.config import understand_doc_config

    builder = ISMBuilder("test-trace", "test-step")

    # 测试用例：各种类型的接口，包括文档头部信息接口
    test_interfaces = [
        {
            "id": "api_filter_dimension_company",
            "name": "公司筛选功能",
            "type": "filter_dimension",  # 有效类型
            "description": "按公司名称筛选广告投放数据",
            "fields": [{"name": "company_name", "type": "string", "required": True}],
            "should_pass": True
        },
        {
            "id": "api_trend_analysis_consumption",
            "name": "消耗趋势分析",
            "type": "trend_analysis",  # 有效类型
            "description": "展示广告消耗的趋势变化",
            "fields": [{"name": "date", "type": "date", "required": True}],
            "should_pass": True
        },
        {
            "id": "api_document_header_info",
            "name": "文档头部信息接口",
            "type": "info",  # 无效类型 - 应该被过滤
            "description": "文档的头部信息，包括背景、概述等",
            "fields": [{"name": "doc_id", "type": "string", "required": True}],
            "should_pass": False
        },
        {
            "id": "api_data_list_materials",
            "name": "素材明细列表",
            "type": "data_display",  # 有效类型
            "description": "展示所有创意素材的详细信息",
            "fields": [{"name": "material_id", "type": "string", "required": True}],
            "should_pass": True
        },
        {
            "id": "api_document_metadata",
            "name": "文档元数据接口",
            "type": "metadata",  # 无效类型 - 应该被过滤
            "description": "文档的元数据信息配置",
            "fields": [{"name": "meta_key", "type": "string", "required": True}],
            "should_pass": False
        },
        {
            "id": "api_export_report",
            "name": "数据导出报表",
            "type": "export_report",  # 有效类型
            "description": "导出数据报表功能",
            "fields": [{"name": "format", "type": "string", "required": True}],
            "should_pass": True
        }
    ]

    passed_tests = 0
    total_tests = len(test_interfaces)

    for i, test_interface in enumerate(test_interfaces, 1):
        # 测试接口类型验证
        is_valid_type = builder._is_valid_interface_type(test_interface["type"])
        is_metadata = builder._is_metadata_interface(test_interface)

        # 综合判断：接口应该被保留的条件是：类型有效且不是元数据接口
        should_keep = is_valid_type and not is_metadata
        expected_keep = test_interface["should_pass"]

        success = should_keep == expected_keep
        status = "✓" if success else "✗"

        action = "保留" if should_keep else "过滤"
        expected_action = "保留" if expected_keep else "过滤"

        print(f"  {status} 测试用例 {i}: {test_interface['name']}")
        print(f"      类型: {test_interface['type']}, 有效: {is_valid_type}, 元数据: {is_metadata}")
        print(f"      {action} (期望: {expected_action})")

        if success:
            passed_tests += 1

    print(f"\n元数据接口过滤通过率: {passed_tests}/{total_tests}")
    return passed_tests == total_tests

def test_combined_filtering():
    """测试组合过滤效果"""
    print("\n=== 测试组合过滤效果 ===")

    # 模拟系统处理流程
    from understand_doc.ism_builder import ISMBuilder
    from understand_doc.config import understand_doc_config

    builder = ISMBuilder("test-trace", "test-step")

    # 模拟一个完整的接口列表（包含功能和元数据接口）
    mock_interfaces = [
        # 功能接口
        {
            "id": "api_filter_dimension",
            "name": "总筛选项",
            "type": "filter_dimension",
            "description": "包含公司、时间等筛选条件",
            "fields": [{"name": "company", "type": "string"}],
            "_block_index": 100
        },
        {
            "id": "api_trend_analysis",
            "name": "消耗趋势",
            "type": "trend_analysis",
            "description": "展示每日消耗金额和变化趋势",
            "fields": [{"name": "date", "type": "date"}],
            "_block_index": 200
        },
        {
            "id": "api_data_list",
            "name": "素材明细",
            "type": "data_display",
            "description": "显示所有创意素材的详细信息",
            "fields": [{"name": "material_id", "type": "string"}],
            "_block_index": 300
        },
        # 元数据接口（应该被过滤）
        {
            "id": "api_document_header",
            "name": "文档头部信息接口",
            "type": "info",
            "description": "文档的头部信息，包括项目背景、概述等",
            "fields": [{"name": "doc_id", "type": "string"}],
            "_block_index": 10
        },
        {
            "id": "api_project_background",
            "name": "项目背景信息",
            "type": "metadata",
            "description": "项目的背景信息和配置参数",
            "fields": [{"name": "background", "type": "string"}],
            "_block_index": 20
        }
    ]

    # 应用过滤逻辑（模拟ism_builder中的处理）
    filtered_interfaces = []

    for interface in mock_interfaces:
        # 标准化接口
        standardized_interface = builder._standardize_interface(interface)

        # 应用类型验证
        if not builder._is_valid_interface_type(standardized_interface.get("type", "")):
            print(f"  过滤无效类型接口: {standardized_interface.get('name', '未知')} [类型: {standardized_interface.get('type')}]")
            continue

        # 应用元数据过滤
        if builder._is_metadata_interface(standardized_interface):
            print(f"  过滤元数据接口: {standardized_interface.get('name', '未知')}")
            continue

        # 保留有效接口
        filtered_interfaces.append(standardized_interface)
        print(f"  保留功能接口: {standardized_interface.get('name', '未知')}")

    print(f"\n过滤结果:")
    print(f"  原始接口数: {len(mock_interfaces)}")
    print(f"  过滤后接口数: {len(filtered_interfaces)}")
    print(f"  过滤掉接口数: {len(mock_interfaces) - len(filtered_interfaces)}")

    # 验证结果
    expected_remaining = 3  # 应该只保留3个功能接口
    expected_filtered = 2   # 应该过滤掉2个元数据接口

    success = (len(filtered_interfaces) == expected_remaining and
              len(mock_interfaces) - len(filtered_interfaces) == expected_filtered)

    status = "✓" if success else "✗"
    print(f"\n  {status} 组合过滤效果: {'成功' if success else '需要改进'}")

    if not success:
        print(f"      期望保留接口: {expected_remaining}, 实际: {len(filtered_interfaces)}")
        print(f"      期望过滤接口: {expected_filtered}, 实际: {len(mock_interfaces) - len(filtered_interfaces)}")

    return success

def main():
    """主测试函数"""
    print("开始验证元数据接口过滤逻辑...\n")

    tests = [
        ("元数据接口过滤逻辑", test_metadata_interface_filtering),
        ("组合过滤效果", test_combined_filtering)
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} - 通过")
            else:
                print(f"❌ {test_name} - 失败")
        except Exception as e:
            print(f"❌ {test_name} - 异常: {e}")

    print(f"\n{'='*60}")
    print(f"元数据过滤验证结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 元数据接口过滤逻辑验证通过！")
        print("\n关键改进:")
        print("1. ✅ 接口类型验证 - 自动过滤无效的接口类型")
        print("2. ✅ 元数据接口识别 - 智能识别并过滤文档头部、配置信息等接口")
        print("3. ✅ 双重过滤机制 - 类型验证 + 内容验证的组合过滤")
        print("4. ✅ 精准识别 - 基于关键词的元数据接口识别")
        print("\n预期效果:")
        print("- 消除文档头部信息接口（如'文档头部信息接口'）")
        print("- 保留功能相关接口（筛选、分析、列表等）")
        print("- 提高接口生成的准确性和实用性")
        return 0
    else:
        print("❌ 部分过滤逻辑需要进一步优化")
        return 1

if __name__ == "__main__":
    sys.exit(main())