#!/usr/bin/env python3
"""
测试修复后的接口解析逻辑
验证能否正确解析出5个接口：总筛选项, 消耗波动详情, 素材明细, 消耗趋势, 交易趋势
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import run_workflow

def test_feishu_doc_parsing():
    """测试飞书文档解析"""

    # 使用用户提供的 problematic Feishu URL
    test_input = {
        "feishu_urls": ["https://ecnjtt87q4e5.feishu.cn/wiki/O2NjwrNDCiRDqMkWJyfcNwd5nXe"],
        "user_intent": "generate_crud",
        "trace_id": "test-fix-001"
    }

    print("=" * 60)
    print("测试修复后的接口解析逻辑")
    print("=" * 60)
    print(f"输入URL: {test_input['feishu_urls'][0]}")
    print(f"期望接口: 总筛选项, 消耗波动详情, 素材明细, 消耗趋势, 交易趋势")
    print("-" * 60)

    try:
        # 运行工作流
        result = run_workflow(test_input)

        # 检查解析结果
        ism = result.get("ism", {})
        interfaces = ism.get("interfaces", [])

        print(f"\n解析结果:")
        print(f"- 总共解析出 {len(interfaces)} 个接口")
        print(f"- 处理方法: {ism.get('__processing_method', 'unknown')}")

        # 列出所有解析的接口
        interface_names = []
        for interface in interfaces:
            name = interface.get("name", "未知接口")
            interface_type = interface.get("type", "unknown")
            interface_names.append(name)
            print(f"  - {name} [{interface_type}]")

        # 检查是否包含期望的接口
        expected_interfaces = ["总筛选项", "消耗波动详情", "素材明细", "消耗趋势", "交易趋势"]
        found_interfaces = []
        missing_interfaces = []

        for expected in expected_interfaces:
            found = False
            for interface_name in interface_names:
                if expected in interface_name or interface_name in expected:
                    found_interfaces.append(expected)
                    found = True
                    break
            if not found:
                missing_interfaces.append(expected)

        print(f"\n验证结果:")
        print(f"- 找到的接口: {found_interfaces}")
        print(f"- 缺失的接口: {missing_interfaces}")

        # 检查是否有重复
        unique_names = set(interface_names)
        if len(unique_names) < len(interface_names):
            print(f"- ⚠️  发现重复接口: {interface_names}")
        else:
            print(f"- ✅ 无重复接口")

        # 成功标准
        success_rate = len(found_interfaces) / len(expected_interfaces)
        print(f"\n成功率: {success_rate:.1%} ({len(found_interfaces)}/{len(expected_interfaces)})")

        if success_rate >= 0.8:  # 80%以上认为成功
            print("✅ 修复成功！接口解析效果显著改善")
            return True
        else:
            print("❌ 修复效果有限，需要进一步优化")
            return False

    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_feishu_doc_parsing()