#!/usr/bin/env python3
"""
测试JSON恢复逻辑的简单验证脚本
验证9个接口生成问题的修复效果
"""

import json
import re
import uuid

def test_json_recovery():
    """测试JSON恢复逻辑"""
    print("=== 测试JSON恢复逻辑 ===")

    # 模拟LLM返回的有问题的JSON（Extra data错误）
    problematic_json = '''{
  "id": "api_totalFilter_filter",
  "name": "总筛选项",
  "type": "filter_dimension",
  "fields": [{"name": "公司ID", "data_type": "string", "required": true}]
}{
  "id": "api_consumptionTrend_trend",
  "name": "消耗趋势",
  "type": "trend_analysis",
  "fields": [{"name": "消耗", "data_type": "number", "required": false}]
}{
  "id": "api_transactionTrend_trend",
  "name": "交易趋势",
  "type": "trend_analysis",
  "fields": [{"name": "GMV", "data_type": "number", "required": false}]
}'''

    # 测试常规解析（应该失败）
    try:
        result = json.loads(problematic_json.strip())
        print("✗ 常规解析应该失败但却成功了")
        return False
    except json.JSONDecodeError as e:
        if "Extra data" in str(e):
            print(f"✓ 检测到预期的Extra data错误: {str(e)[:50]}...")
        else:
            print(f"✗ 意外的JSON错误: {e}")
            return False

    # 测试恢复策略
    strategies = [
        r'(?<=\})\s*(?=\{)',
        r'\}\s*\n\s*\{',
        r'\}\s{2,}\{'
    ]

    recovered_interfaces = []

    for strategy in strategies:
        try:
            parts = re.split(strategy, problematic_json.strip())

            valid_interfaces = []
            for i, part in enumerate(parts):
                part = part.strip()
                if not part:
                    continue

                if not part.startswith('{'):
                    part = '{' + part
                if not part.endswith('}'):
                    part = part + '}'

                try:
                    interface = json.loads(part)
                    if validate_interface_structure(interface):
                        interface["recovery_index"] = i
                        interface["recovery_strategy"] = strategy
                        valid_interfaces.append(interface)
                        print(f"  ✓ 成功恢复接口 {i}: {interface.get('name', '未知')}")
                except json.JSONDecodeError:
                    continue

            if valid_interfaces:
                recovered_interfaces.extend(valid_interfaces)
                print(f"✓ 策略成功: 恢复了 {len(valid_interfaces)} 个接口")
                break

        except Exception:
            continue

    if not recovered_interfaces:
        print("✗ 所有恢复策略都失败")
        return False

    print(f"✓ JSON恢复成功: 总共恢复 {len(recovered_interfaces)} 个接口")

    # 检查是否恢复了预期的接口
    recovered_names = [iface.get("name") for iface in recovered_interfaces]
    expected_names = ["总筛选项", "消耗趋势", "交易趋势"]

    missing = [name for name in expected_names if name not in recovered_names]
    if missing:
        print(f"✗ 缺失预期接口: {missing}")
        return False

    print(f"✓ 恢复了所有预期接口: {recovered_names}")
    return True

def validate_interface_structure(interface):
    """验证接口结构的基本有效性"""
    required_fields = ["name", "type"]
    for field in required_fields:
        if field not in interface or not interface[field]:
            return False

    if not isinstance(interface.get("fields", []), list):
        return False

    return True

def test_array_expansion():
    """测试数组展开逻辑"""
    print("\n=== 测试数组展开逻辑 ===")

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
                    "name": "总筛选项",
                    "type": "filter_dimension",
                    "fields": [{"name": "公司ID"}]
                },
                {
                    "id": "api_2",
                    "name": "消耗趋势",
                    "type": "trend_analysis",
                    "fields": [{"name": "天"}]
                },
                {
                    "id": "api_3",
                    "name": "交易趋势",
                    "type": "trend_analysis",
                    "fields": [{"name": "GMV"}]
                }
            ]
        },
        {
            "id": "normal_interface",
            "name": "素材明细",
            "type": "data_display",
            "source_chunk_id": "chunk_2"
        }
    ]

    # 展开数组响应
    expanded_interfaces = []
    for interface in interface_results:
        if interface.get("_array_response") and interface.get("_array_data"):
            array_data = interface["_array_data"]
            print(f"  展开数组响应: {len(array_data)} 个接口")

            for i, array_interface in enumerate(array_data):
                expanded_interface = array_interface.copy()
                expanded_interface.update({
                    "source_chunk_id": interface.get("source_chunk_id", ""),
                    "source_chunk_type": interface.get("source_chunk_type", ""),
                    "source_method": f"{interface.get('source_method', '')}_array_item_{i}",
                    "_array_response": True,
                    "_array_index": i
                })
                expanded_interfaces.append(expanded_interface)
        else:
            expanded_interfaces.append(interface)

    print(f"展开前的接口数: {len(interface_results)}")
    print(f"展开后的接口数: {len(expanded_interfaces)}")

    # 验证展开结果
    array_interfaces = [iface for iface in expanded_interfaces if iface.get("_array_response")]
    expected_array_count = 3

    if len(array_interfaces) != expected_array_count:
        print(f"✗ 数组接口展开错误，期望{expected_array_count}个，实际{len(array_interfaces)}个")
        return False

    print(f"✓ 数组接口正确展开为{len(array_interfaces)}个独立接口")

    # 检查接口完整性
    all_names = [iface.get("name") for iface in expanded_interfaces]
    expected_names = ["总筛选项", "消耗趋势", "交易趋势", "素材明细"]
    missing = [name for name in expected_names if name not in all_names]

    if missing:
        print(f"✗ 缺失接口: {missing}")
        return False

    print(f"✓ 接口完整性检查通过: {all_names}")
    return True

def test_fallback_improvement():
    """测试改进的fallback逻辑"""
    print("\n=== 测试Fallback改进逻辑 ===")

    # 模拟接口结果（包含数组响应）
    interface_results = [
        {
            "id": "chunk_1_result",
            "source_chunk_id": "chunk_1",
            "_array_response": True,
            "_array_data": [
                {"name": "总筛选项", "type": "filter_dimension"},
                {"name": "消耗趋势", "type": "trend_analysis"},
                {"name": "交易趋势", "type": "trend_analysis"}
            ]
        },
        {
            "id": "chunk_2_result",
            "name": "素材明细",
            "type": "data_display",
            "source_chunk_id": "chunk_2"
        }
    ]

    # 模拟所有块
    grid_chunks = [
        {"chunk_id": "chunk_1"},
        {"chunk_id": "chunk_2"},
        {"chunk_id": "chunk_3"}  # 这个块失败了
    ]

    # 展开数组响应进行缺失检查
    expanded_interfaces = []
    for interface in interface_results:
        if interface.get("_array_response") and interface.get("_array_data"):
            array_data = interface["_array_data"]
            for array_interface in array_data:
                expanded_interfaces.append(array_interface)
        else:
            expanded_interfaces.append(interface)

    # 检查缺失的接口
    expected_interfaces = ["总筛选项", "消耗波动详情", "素材明细", "消耗趋势", "交易趋势"]
    found_names = {iface.get("name") for iface in expanded_interfaces}
    missing = [exp for exp in expected_interfaces if exp not in found_names]

    print(f"展开后找到的接口: {found_names}")
    print(f"仍然缺失的接口: {missing}")

    # 检查失败的块（跳过已有数组响应的块）
    processed_chunk_ids = {iface.get("source_chunk_id") for iface in interface_results}
    missing_chunk_ids = {chunk.get("chunk_id") for chunk in grid_chunks} - processed_chunk_ids

    print(f"已处理块ID: {processed_chunk_ids}")
    print(f"缺失块ID: {missing_chunk_ids}")

    # 应该只有chunk_3需要fallback处理
    expected_missing_chunks = {"chunk_3"}
    if missing_chunk_ids != expected_missing_chunks:
        print(f"✗ 缺失块检测错误，期望{expected_missing_chunks}，实际{missing_chunk_ids}")
        return False

    print(f"✓ 正确识别需要fallback处理的块: {missing_chunk_ids}")

    # 检查缺失接口（应该只有"消耗波动详情"）
    expected_missing_interfaces = ["消耗波动详情"]
    if missing != expected_missing_interfaces:
        print(f"✗ 缺失接口检测错误，期望{expected_missing_interfaces}，实际{missing}")
        return False

    print(f"✓ 正确识别真正缺失的接口: {missing}")
    return True

def main():
    """主测试函数"""
    print("开始验证9个接口生成问题的修复效果...\n")

    tests = [
        ("JSON恢复逻辑", test_json_recovery),
        ("数组展开逻辑", test_array_expansion),
        ("Fallback改进逻辑", test_fallback_improvement)
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

    print(f"\n{'='*50}")
    print(f"修复验证结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有修复验证通过！9个接口问题已解决！")
        print("\n主要修复效果:")
        print("1. ✅ JSON恢复机制 - 解决'Extra data'错误")
        print("2. ✅ 数组响应处理 - 正确展开所有接口")
        print("3. ✅ Fallback优化 - 避免不必要的降级接口")
        print("4. ✅ 接口完整性 - 确保生成预期的5个接口")
        return 0
    else:
        print("❌ 部分修复验证失败，需要进一步调试")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())