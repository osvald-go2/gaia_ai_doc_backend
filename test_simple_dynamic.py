#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的动态标题测试
"""

from deepseek_client import get_deepseek_client
import json

def test_simple_prompt():
    """测试简单的提示词修改"""
    print("=== 测试动态标题提示词 ===")

    # 新的系统提示词
    new_system_prompt = """你是一个智能接口解析器。请解析下面的功能块并生成JSON接口定义。

重要：请从上下文中提取实际的功能标题，不要使用"总筛选项"等固定名称。
使用文档中真实的标题，比如"投放筛选条件"、"账户数据明细"、"成本趋势分析"等。

输出格式：
{
  "id": "api_功能英文名",
  "name": "实际的功能中文名（从文档中提取）",
  "type": "接口类型",
  "dimensions": [{"name": "字段名", "expression": "englishName", "data_type": "string", "required": true/false}],
  "metrics": [{"name": "指标名", "expression": "englishName", "data_type": "number", "required": true/false}]
}

只输出JSON，不要其他文字。"""

    # 用户提示词
    user_prompt = """上下文信息：
功能块标题: ## 投放筛选条件

功能块内容：
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

请解析这个功能块，生成接口定义。"""

    print(f"用户提示词:\n{user_prompt}")
    print("\n调用DeepSeek API...")

    try:
        client = get_deepseek_client()
        response = client.call_llm(
            system_prompt=new_system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=2000
        )

        print(f"\nLLM响应:\n{response}")

        # 解析JSON
        try:
            result = json.loads(response)
            print(f"\n解析成功!")
            print(f"接口名称: {result.get('name', 'N/A')}")
            print(f"接口ID: {result.get('id', 'N/A')}")
            print(f"接口类型: {result.get('type', 'N/A')}")

            # 检查标题
            name = result.get('name', '')
            if "总筛选项" in name:
                print("警告: 仍使用固定名称")
            elif "投放筛选条件" in name:
                print("成功: 使用动态标题!")
            else:
                print(f"使用其他标题: {name}")

        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")

    except Exception as e:
        print(f"调用失败: {e}")
        # 测试mock模式
        print("\n尝试Mock模式...")
        client = get_deepseek_client()
        client.use_mock = True
        response = client.call_llm(new_system_prompt, user_prompt)
        print(f"Mock响应:\n{response}")

if __name__ == "__main__":
    test_simple_prompt()