#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试grid解析和动态标题提取
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from nodes.understand_doc import UltimateDocumentProcessor, get_ultimate_processor
import asyncio

async def test_grid_parsing():
    """测试grid解析功能"""
    print("=== 测试Grid解析和动态标题提取 ===")

    # 读取测试文档
    with open('test_dynamic_content.md', 'r', encoding='utf-8') as f:
        content = f.read()

    print(f"文档内容长度: {len(content)} 字符")
    print("\n文档内容:")
    print(content[:500] + "..." if len(content) > 500 else content)

    processor = get_ultimate_processor()

    # 提取grid块
    grid_blocks = processor._extract_grid_blocks(content)
    print(f"\n发现 {len(grid_blocks)} 个grid块")

    for i, (grid_content, grid_start) in enumerate(grid_blocks):
        print(f"\n--- Grid块 {i+1} (位置: {grid_start}) ---")

        # 提取上下文
        context = processor._extract_context_around_grid(content, grid_start)
        print("上下文:")
        print(context)

        print("\nGrid内容:")
        print(grid_content)

        # 分析这个grid块应该是什么标题
        lines = content.split('\n')
        print(f"\n前后5行内容:")
        for j in range(max(0, grid_start-5), min(len(lines), grid_start+10)):
            prefix = ">>> " if j == grid_start else "    "
            print(f"{prefix}{j:3d}: {lines[j]}")

async def test_direct_llm_call():
    """直接测试LLM调用"""
    print("\n=== 直接测试LLM调用 ===")

    # 读取测试文档
    with open('test_dynamic_content.md', 'r', encoding='utf-8') as f:
        content = f.read()

    processor = get_ultimate_processor()
    grid_blocks = processor._extract_grid_blocks(content)

    if grid_blocks:
        grid_content, grid_start = grid_blocks[0]
        context = processor._extract_context_around_grid(content, grid_start)

        # 构建提示词
        from nodes.understand_doc import INTERFACE_SYSTEM_PROMPT

        user_prompt = f"""请解析下面这个功能块，生成对应的接口定义。

上下文信息：
{context}

功能块内容：
{grid_content}

**重要提醒**：
1. 请从上下文中提取功能块的实际标题作为接口名称
2. 不要使用"总筛选项"等固定预设名称
3. 使用文档中真实的标题，比如"投放筛选条件"、"账户数据明细"、"成本趋势分析"等
4. 如果上下文中有明确的标题，请优先使用该标题

请根据功能块的内容智能识别接口类型，并提取字段信息。输出JSON格式。"""

        print("系统提示词:")
        print(INTERFACE_SYSTEM_PROMPT[:300] + "...")

        print(f"\n用户提示词:")
        print(user_prompt[:500] + "..." if len(user_prompt) > 500 else user_prompt)

        # 尝试调用LLM
        try:
            from deepseek_client import get_deepseek_client
            client = get_deepseek_client()

            # 强制使用mock模式
            client.use_mock = True

            response = client.call_llm(
                system_prompt=INTERFACE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=2000
            )

            print(f"\nLLM响应:")
            print(response)

            # 解析JSON
            import json
            try:
                result = json.loads(response)
                print(f"\n解析成功!")
                print(f"接口名称: {result.get('name', 'N/A')}")
                print(f"接口ID: {result.get('id', 'N/A')}")
                print(f"接口类型: {result.get('type', 'N/A')}")

                # 检查标题
                name = result.get('name', '')
                if "总筛选项" in name:
                    print("❌ 警告: 仍使用固定名称'总筛选项'")
                elif "投放筛选条件" in name:
                    print("✅ 成功: 使用了动态标题'投放筛选条件'")
                else:
                    print(f"ℹ️ 使用了其他标题: {name}")

            except json.JSONDecodeError as e:
                print(f"❌ JSON解析失败: {e}")

        except Exception as e:
            print(f"❌ LLM调用失败: {e}")

async def main():
    """主测试函数"""
    print("开始测试Grid解析功能...")

    await test_grid_parsing()
    await test_direct_llm_call()

    print("\n测试完成!")

if __name__ == "__main__":
    asyncio.run(main())