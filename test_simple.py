#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import run_workflow

def test_feishu_parsing():
    test_input = {
        "feishu_urls": ["https://ecnjtt87q4e5.feishu.cn/wiki/O2NjwrNDCiRDqMkWJyfcNwd5nXe"],
        "user_intent": "generate_crud",
        "trace_id": "test-simple"
    }

    try:
        result = run_workflow(test_input)

        # Get ISM data
        ism = result.get("ism", {})
        interfaces = ism.get("interfaces", [])

        print("=== 解析结果 ===")
        print(f"总共解析出 {len(interfaces)} 个接口")

        # List all interfaces
        for i, interface in enumerate(interfaces):
            name = interface.get("name", "未知")
            type_name = interface.get("type", "unknown")
            print(f"{i+1}. {name} [{type_name}]")

        # Expected interfaces
        expected = ["总筛选项", "消耗波动详情", "素材明细", "消耗趋势", "交易趋势"]
        found = []

        interface_names = [iface.get("name", "") for iface in interfaces]

        for exp in expected:
            for name in interface_names:
                if exp in name or name in exp:
                    found.append(exp)
                    break

        print(f"\n期望: {expected}")
        print(f"找到: {found}")
        print(f"缺失: {[e for e in expected if e not in found]}")

        success_rate = len(found) / len(expected)
        print(f"成功率: {success_rate:.1%}")

        # Check chunking statistics
        stats = ism.get("parsing_statistics", {})
        print(f"\n块处理统计:")
        print(f"- 总块数: {stats.get('total_chunks', 0)}")
        print(f"- 包含grid的块数: {stats.get('chunks_with_grid', 0)}")
        print(f"- 处理的块数: {stats.get('chunks_processed', 0)}")
        print(f"- 生成的接口数: {stats.get('interfaces_generated', 0)}")

        return success_rate >= 0.8

    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_feishu_parsing()