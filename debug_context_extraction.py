#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试上下文提取问题
"""

# 导入函数
import sys
sys.path.append('.')

from nodes.understand_doc_parallel import extract_context_around_grid, extract_grid_blocks

# 测试内容
TEST_CONTENT = """
# 用户管理测试文档

```grid
grid_column:
  - width_ratio: 50
    content: |
        ![用户界面](user.png)
  - width_ratio: 50
    content: |
        **查询条件**
        - 用户ID: userId
        - 用户名: username
        - 手机号: phone
        - 注册时间: createdTime
        - 用户状态: userStatus
```

```grid
grid_column:
  - width_ratio: 40
    content: |
        ![订单管理](order.png)
  - width_ratio: 60
    content: |
        **订单筛选**
        - 订单ID: orderId
        - 用户ID: userId
        - 订单金额: amount
        - 订单状态: status
        - 创建时间: createdTime
```
"""

def debug_context_extraction():
    print("调试上下文提取问题")
    print("=" * 50)

    # 提取grid块
    grid_blocks = extract_grid_blocks(TEST_CONTENT)
    print(f"找到 {len(grid_blocks)} 个grid块")

    for i, (grid_content, grid_start) in enumerate(grid_blocks):
        print(f"\n--- Grid块 {i+1} (第{grid_start}行) ---")
        print("Grid内容:")
        print(grid_content[:200] + "..." if len(grid_content) > 200 else grid_content)

        # 提取上下文
        context = extract_context_around_grid(TEST_CONTENT, grid_start)
        print(f"\n上下文 (第{grid_start}行之前):")
        print(f"'{context}'")

        if not context.strip():
            print("❌ 上下文为空!")
        else:
            print("✅ 上下文提取成功")

if __name__ == "__main__":
    debug_context_extraction()