#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 understand_doc 优化版本
"""

import asyncio
from models.state import AgentState

# 创建测试内容
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

def test_understand_doc():
    """测试 understand_doc 函数"""
    print("测试优化版 understand_doc")
    print("=" * 50)

    # 创建测试状态
    state = {
        "feishu_urls": ["https://test.com/doc"],
        "user_intent": "generate_crud",
        "trace_id": "test-understand-doc-001",
        "raw_docs": [TEST_CONTENT],
        "feishu_blocks": [],
        "templates": []
    }

    try:
        from nodes.understand_doc import understand_doc
        print("导入成功")

        # 测试同步版本
        print("\n开始测试同步处理...")
        result = understand_doc(state)

        print("处理完成!")
        print(f"解析接口数: {len(result.get('ism', {}).get('interfaces', []))}")
        print(f"处理模式: {result.get('ism', {}).get('doc_meta', {}).get('parsing_mode', 'unknown')}")

        return True

    except Exception as e:
        print(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_understand_doc_async():
    """测试异步版本"""
    print("\n测试异步版本")
    print("=" * 50)

    # 创建测试状态
    state = {
        "feishu_urls": ["https://test.com/doc"],
        "user_intent": "generate_crud",
        "trace_id": "test-async-002",
        "raw_docs": [TEST_CONTENT],
        "feishu_blocks": [],
        "templates": []
    }

    try:
        from nodes.understand_doc import UltimateDocumentProcessor

        processor = UltimateDocumentProcessor()
        print("创建处理器成功")

        # 测试异步处理
        print("\n开始测试异步处理...")
        result = await processor.process_document_with_all_optimizations(
            TEST_CONTENT, "test-async-002"
        )

        print("异步处理完成!")
        print(f"解析接口数: {len(result.get('interfaces', []))}")
        print(f"处理模式: {result.get('parsing_mode', 'unknown')}")

        return True

    except Exception as e:
        print(f"异步测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("开始测试 understand_doc 优化版本")
    print(f"测试内容长度: {len(TEST_CONTENT)} 字符")
    print(f"Grid块数量: {TEST_CONTENT.count('```grid')}")

    # 测试同步版本
    sync_success = test_understand_doc()

    # 测试异步版本
    print("\n" + "="*60)
    async_success = asyncio.run(test_understand_doc_async())

    # 总结
    print("\n" + "="*60)
    print("测试总结:")
    print(f"同步版本: {'成功' if sync_success else '失败'}")
    print(f"异步版本: {'成功' if async_success else '失败'}")

    if sync_success and async_success:
        print("\n所有测试通过! 优化版本工作正常!")
    else:
        print("\n部分测试失败，请检查配置")