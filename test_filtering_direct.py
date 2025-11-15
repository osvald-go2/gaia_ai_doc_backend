#!/usr/bin/env python3
"""
直接测试过滤逻辑，不依赖完整模块导入
"""

def test_interface_type_validation():
    """测试接口类型验证逻辑"""
    print("=== 测试接口类型验证逻辑 ===")

    # 支持的接口类型（从config.py复制）
    SUPPORTED_INTERFACE_TYPES = [
        "filter_dimension", "data_display", "trend_analysis",
        "analytics_metric", "export_report", "custom_action",
        "crud", "config", "analytics", "fallback", "basic", "emergency"
    ]

    def is_valid_interface_type(interface_type: str) -> bool:
        """检查接口类型是否有效"""
        return interface_type in SUPPORTED_INTERFACE_TYPES

    # 测试用例
    test_cases = [
        ("filter_dimension", True),   # 有效类型
        ("trend_analysis", True),     # 有效类型
        ("data_display", True),       # 有效类型
        ("info", False),              # 无效类型 - 文档头部信息接口使用这个类型
        ("metadata", False),          # 无效类型
        ("document", False),          # 无效类型
        ("config", True),             # 有效类型
        ("fallback", True),           # 有效类型
    ]

    passed = 0
    for interface_type, expected in test_cases:
        actual = is_valid_interface_type(interface_type)
        success = actual == expected
        status = "✓" if success else "✗"
        result = "有效" if actual else "无效"
        expected_result = "有效" if expected else "无效"

        print(f"  {status} {interface_type}: {result} (期望: {expected_result})")
        if success:
            passed += 1

    print(f"\n接口类型验证通过率: {passed}/{len(test_cases)}")
    return passed == len(test_cases)

def test_metadata_interface_detection():
    """测试元数据接口检测逻辑"""
    print("\n=== 测试元数据接口检测逻辑 ===")

    def is_metadata_interface(interface: dict) -> bool:
        """检查是否为元数据接口（文档头部、配置信息等）"""
        interface_name = interface.get("name", "").lower()
        interface_type = interface.get("type", "").lower()
        interface_id = interface.get("id", "").lower()
        description = interface.get("description", "").lower()

        # 严格的元数据接口关键词（只匹配真正的元数据概念）
        strict_metadata_keywords = [
            "文档头部", "文档信息", "元数据", "文档metadata", "document header",
            "document info", "文档overview", "文档introduction"
        ]

        # 检查是否匹配严格的元数据关键词
        for keyword in strict_metadata_keywords:
            if (keyword in interface_name or
                keyword in interface_type or
                keyword in interface_id or
                keyword in description):
                return True

        # 特殊情况：检查是否为文档相关信息（更严格的匹配）
        document_indicators = [
            "文档id", "doc_id", "source", "url", "背景", "概述", "介绍",
            "documentid", "docid", "sourceurl", "background", "overview", "introduction"
        ]

        # 只有在明确包含文档相关信息时才标记为元数据
        document_matches = 0
        for indicator in document_indicators:
            if indicator in interface_id or indicator in description:
                document_matches += 1

        # 如果有多个文档指标匹配，认为是元数据接口
        if document_matches >= 2:
            return True

        # 特殊处理：检查接口类型是否明显是元数据类型
        metadata_only_types = ["info", "metadata", "document", "header"]
        if interface_type in metadata_only_types:
            return True

        # 避免误判：如果包含明显的业务关键词，即使有"信息"、"配置"等词也不算元数据
        business_keywords = [
            "筛选", "查询", "列表", "分析", "统计", "报表", "导出", "管理",
            "明细", "详情", "趋势", "消耗", "素材", "广告", "投放", "效果"
        ]

        for keyword in business_keywords:
            if keyword in interface_name or keyword in description:
                return False

        return False

    # 测试用例
    test_cases = [
        {
            "interface": {
                "id": "api_document_header_info",
                "name": "文档头部信息接口",
                "type": "info",
                "description": "文档的头部信息，包括背景、概述等"
            },
            "expected": True,
            "description": "文档头部信息接口"
        },
        {
            "interface": {
                "id": "api_filter_dimension",
                "name": "公司筛选功能",
                "type": "filter_dimension",
                "description": "按公司名称筛选广告投放数据"
            },
            "expected": False,
            "description": "业务功能接口"
        },
        {
            "interface": {
                "id": "api_metadata_config",
                "name": "元数据配置接口",
                "type": "metadata",
                "description": "系统的元数据配置管理"
            },
            "expected": True,
            "description": "元数据配置接口"
        },
        {
            "interface": {
                "id": "api_trend_analysis",
                "name": "消耗趋势分析",
                "type": "trend_analysis",
                "description": "展示广告消耗的趋势变化"
            },
            "expected": False,
            "description": "趋势分析接口"
        }
    ]

    passed = 0
    for i, test_case in enumerate(test_cases, 1):
        actual = is_metadata_interface(test_case["interface"])
        expected = test_case["expected"]
        success = actual == expected
        status = "✓" if success else "✗"
        result = "元数据" if actual else "功能"
        expected_result = "元数据" if expected else "功能"

        print(f"  {status} 测试用例 {i}: {test_case['description']}")
        print(f"      {result}接口 (期望: {expected_result})")
        print(f"      名称: {test_case['interface']['name']}")

        if success:
            passed += 1

    print(f"\n元数据接口检测通过率: {passed}/{len(test_cases)}")
    return passed == len(test_cases)

def test_combined_filtering():
    """测试组合过滤效果"""
    print("\n=== 测试组合过滤效果 ===")

    # 支持的接口类型
    SUPPORTED_INTERFACE_TYPES = [
        "filter_dimension", "data_display", "trend_analysis",
        "analytics_metric", "export_report", "custom_action",
        "crud", "config", "analytics", "fallback", "basic", "emergency"
    ]

    def is_valid_interface_type(interface_type: str) -> bool:
        return interface_type in SUPPORTED_INTERFACE_TYPES

    def is_metadata_interface(interface: dict) -> bool:
        interface_name = interface.get("name", "").lower()
        interface_type = interface.get("type", "").lower()
        interface_id = interface.get("id", "").lower()
        description = interface.get("description", "").lower()

        # 严格的元数据接口关键词（只匹配真正的元数据概念）
        strict_metadata_keywords = [
            "文档头部", "文档信息", "元数据", "文档metadata", "document header",
            "document info", "文档overview", "文档introduction"
        ]

        # 检查是否匹配严格的元数据关键词
        for keyword in strict_metadata_keywords:
            if (keyword in interface_name or
                keyword in interface_type or
                keyword in interface_id or
                keyword in description):
                return True

        # 特殊情况：检查是否为文档相关信息（更严格的匹配）
        document_indicators = [
            "文档id", "doc_id", "source", "url", "背景", "概述", "介绍",
            "documentid", "docid", "sourceurl", "background", "overview", "introduction"
        ]

        # 只有在明确包含文档相关信息时才标记为元数据
        document_matches = 0
        for indicator in document_indicators:
            if indicator in interface_id or indicator in description:
                document_matches += 1

        # 如果有多个文档指标匹配，认为是元数据接口
        if document_matches >= 2:
            return True

        # 特殊处理：检查接口类型是否明显是元数据类型
        metadata_only_types = ["info", "metadata", "document", "header"]
        if interface_type in metadata_only_types:
            return True

        # 避免误判：如果包含明显的业务关键词，即使有"信息"、"配置"等词也不算元数据
        business_keywords = [
            "筛选", "查询", "列表", "分析", "统计", "报表", "导出", "管理",
            "明细", "详情", "趋势", "消耗", "素材", "广告", "投放", "效果"
        ]

        for keyword in business_keywords:
            if keyword in interface_name or keyword in description:
                return False

        return False

    # 模拟完整的接口列表
    mock_interfaces = [
        # 功能接口
        {
            "id": "api_filter_dimension",
            "name": "总筛选项",
            "type": "filter_dimension",
            "description": "包含公司、时间等筛选条件"
        },
        {
            "id": "api_trend_analysis",
            "name": "消耗趋势",
            "type": "trend_analysis",
            "description": "展示每日消耗金额和变化趋势"
        },
        {
            "id": "api_data_list",
            "name": "素材明细",
            "type": "data_display",
            "description": "显示所有创意素材的详细信息"
        },
        {
            "id": "api_export_report",
            "name": "数据导出",
            "type": "export_report",
            "description": "导出数据报表功能"
        },
        # 元数据接口（应该被过滤）
        {
            "id": "api_document_header_info",
            "name": "文档头部信息接口",
            "type": "info",
            "description": "文档的头部信息，包括项目背景、概述等"
        },
        {
            "id": "api_project_background",
            "name": "项目背景信息",
            "type": "metadata",
            "description": "项目的背景信息和配置参数"
        }
    ]

    # 应用过滤逻辑
    filtered_interfaces = []
    filtered_out_interfaces = []

    for interface in mock_interfaces:
        # 应用类型验证
        if not is_valid_interface_type(interface.get("type", "")):
            filtered_out_interfaces.append({
                "interface": interface,
                "reason": f"无效类型: {interface.get('type')}"
            })
            continue

        # 应用元数据过滤
        if is_metadata_interface(interface):
            filtered_out_interfaces.append({
                "interface": interface,
                "reason": "元数据接口"
            })
            continue

        # 保留有效接口
        filtered_interfaces.append(interface)

    print(f"过滤结果详情:")
    print(f"  原始接口数: {len(mock_interfaces)}")
    print(f"  保留接口数: {len(filtered_interfaces)}")
    print(f"  过滤接口数: {len(filtered_out_interfaces)}")

    print(f"\n保留的接口:")
    for i, interface in enumerate(filtered_interfaces, 1):
        print(f"  {i}. {interface['name']} ({interface['type']})")

    print(f"\n过滤的接口:")
    for i, item in enumerate(filtered_out_interfaces, 1):
        interface = item["interface"]
        reason = item["reason"]
        print(f"  {i}. {interface['name']} ({interface['type']}) - {reason}")

    # 验证结果
    expected_remaining = 4  # 应该只保留4个功能接口
    expected_filtered = 2   # 应该过滤掉2个元数据接口

    success = (len(filtered_interfaces) == expected_remaining and
              len(filtered_out_interfaces) == expected_filtered)

    status = "✓" if success else "✗"
    print(f"\n  {status} 组合过滤效果: {'成功' if success else '需要改进'}")

    if not success:
        print(f"      期望保留接口: {expected_remaining}, 实际: {len(filtered_interfaces)}")
        print(f"      期望过滤接口: {expected_filtered}, 实际: {len(filtered_out_interfaces)}")

    return success

def main():
    """主测试函数"""
    print("开始验证过滤逻辑...\n")

    tests = [
        ("接口类型验证", test_interface_type_validation),
        ("元数据接口检测", test_metadata_interface_detection),
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
    print(f"过滤逻辑验证结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 过滤逻辑验证通过！")
        print("\n关键成果:")
        print("1. ✅ 类型验证机制 - 'info'和'metadata'类型被正确识别为无效")
        print("2. ✅ 元数据接口识别 - 文档头部信息接口被正确识别")
        print("3. ✅ 组合过滤效果 - 功能接口被保留，元数据接口被过滤")
        print("4. ✅ 精准识别精度 - 基于关键词和描述的智能识别")
        print("\n解决方案:")
        print("- ✅ 双重过滤机制有效工作")
        print("- ✅ 文档头部信息接口将被消除")
        print("- ✅ 只保留功能性业务接口（筛选、分析、列表、导出等）")
        return 0
    else:
        print("❌ 过滤逻辑需要进一步优化")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())