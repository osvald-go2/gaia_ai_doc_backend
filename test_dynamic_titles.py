#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试动态标题提取功能
"""

import asyncio
import json
from nodes.understand_doc import UltimateDocumentProcessor, get_ultimate_processor
from deepseek_client import get_deepseek_client
from utils.logger import logger


def create_test_content():
    """创建测试内容，包含不同的grid标题"""
    test_content = """
# 投放数据分析系统

## 投放筛选条件

```grid
grid_column:
  - width_ratio: 50
    content: |
        投放筛选条件界面截图
  - width_ratio: 50
    content: |
        - 推广计划ID
        - 广告组ID
        - 时间范围
        - 投放状态
```

## 账户数据明细

```grid
grid_column:
  - width_ratio: 50
    content: |
        数据明细表格展示
  - width_ratio: 50
    content: |
        - 账户名称
        - 消耗金额
        - 展示次数
        - 点击次数
        - CTR
```

## 成本趋势分析

```grid
grid_column:
  - width_ratio: 50
    content: |
        趋势图表界面
  - width_ratio: 50
    content: |
        - 日期维度
        - 成本指标
        - 趋势对比
```
"""
    return test_content


async def test_context_extraction():
    """测试上下文提取功能"""
    print("=== 测试上下文提取功能 ===")

    content = create_test_content()
    processor = get_ultimate_processor()

    # 提取grid块
    grid_blocks = processor._extract_grid_blocks(content)
    print(f"发现 {len(grid_blocks)} 个grid块")

    for i, (grid_content, grid_start) in enumerate(grid_blocks):
        context = processor._extract_context_around_grid(content, grid_start)
        print(f"\n--- Grid块 {i+1} (位置: {grid_start}) ---")
        print("上下文:")
        print(context)
        print("\nGrid内容:")
        print(grid_content[:200] + "..." if len(grid_content) > 200 else grid_content)


async def test_llm_response():
    """测试LLM响应是否使用动态标题"""
    print("\n=== 测试LLM响应 ===")

    content = create_test_content()
    processor = get_ultimate_processor()

    # 处理第一个grid块
    grid_blocks = processor._extract_grid_blocks(content)
    if not grid_blocks:
        print("没有找到grid块")
        return

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

    print(f"系统提示词长度: {len(INTERFACE_SYSTEM_PROMPT)}")
    print(f"用户提示词长度: {len(user_prompt)}")
    print(f"上下文内容:\n{context}")

    # 调用LLM
    try:
        deepseek_client = get_deepseek_client()
        response = deepseek_client.call_llm(
            system_prompt=INTERFACE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=3000
        )

        print(f"\nLLM响应:")
        print(response)

        # 尝试解析JSON
        try:
            result = json.loads(response)
            print(f"\n解析成功!")
            print(f"接口名称: {result.get('name', 'N/A')}")
            print(f"接口ID: {result.get('id', 'N/A')}")
            print(f"接口类型: {result.get('type', 'N/A')}")

            # 检查是否使用了动态标题
            if "总筛选项" in result.get('name', ''):
                print("警告: 仍然使用了固定预设名称'总筛选项'")
            elif "投放筛选条件" in result.get('name', ''):
                print("成功: 使用了动态标题'投放筛选条件'")
            else:
                print(f"使用了其他标题: {result.get('name', 'N/A')}")

        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            print(f"原始响应: {response}")

    except Exception as e:
        print(f"LLM调用失败: {e}")


async def test_full_processing():
    """测试完整的文档处理流程"""
    print("\n=== 测试完整处理流程 ===")

    content = create_test_content()
    processor = get_ultimate_processor()

    try:
        result = await processor.process_document_with_all_optimizations(
            content, "test-trace-id"
        )

        print(f"处理完成!")
        print(f"接口数量: {len(result.get('interfaces', []))}")
        print(f"处理时间: {result.get('processing_time', 0):.2f}s")
        print(f"成功率: {result.get('success_rate', 0):.2%}")

        # 检查每个接口的名称
        for i, interface in enumerate(result.get('interfaces', [])):
            if 'error' not in interface:
                name = interface.get('name', 'N/A')
                print(f"接口 {i+1}: {name}")

                if "总筛选项" in name:
                    print(f"  警告: 仍使用固定名称: {name}")
                else:
                    print(f"  成功: 使用动态名称: {name}")
            else:
                print(f"接口 {i+1}: 处理失败 - {interface['error']}")

    except Exception as e:
        print(f"处理失败: {e}")


async def main():
    """主测试函数"""
    print("开始测试动态标题提取功能...")

    await test_context_extraction()
    await test_llm_response()
    await test_full_processing()

    print("\n测试完成!")


if __name__ == "__main__":
    asyncio.run(main())