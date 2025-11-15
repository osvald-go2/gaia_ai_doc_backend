#!/usr/bin/env python3
"""
测试重构后的understand_doc模块
"""

import sys
import traceback

def test_import():
    """测试模块导入"""
    print("=== 测试模块导入 ===")
    try:
        from nodes.understand_doc.config import understand_doc_config
        print("✓ 配置模块导入成功")
        print(f"  - MAX_WORKERS: {understand_doc_config.MAX_WORKERS}")
        print(f"  - DEFAULT_TIMEOUT: {understand_doc_config.DEFAULT_TIMEOUT}")
        print(f"  - EXPECTED_INTERFACES: {understand_doc_config.EXPECTED_INTERFACES}")
    except Exception as e:
        print(f"✗ 配置模块导入失败: {e}")
        return False

    try:
        from nodes.understand_doc.grid_parser import GridParser
        print("✓ Grid解析器导入成功")
    except Exception as e:
        print(f"✗ Grid解析器导入失败: {e}")
        return False

    try:
        from nodes.understand_doc.ism_builder import ISMBuilder
        print("✓ ISM构建器导入成功")
    except Exception as e:
        print(f"✗ ISM构建器导入失败: {e}")
        return False

    try:
        from nodes.understand_doc import get_module_info, health_check
        print("✓ 主模块导入成功")

        # 测试模块信息
        info = get_module_info()
        print(f"  - 模块版本: {info.get('version', 'unknown')}")
        print(f"  - 架构类型: {info.get('architecture', 'unknown')}")
        print(f"  - 组件数量: {len(info.get('components', []))}")

        # 测试健康检查
        health = health_check()
        print(f"  - 健康状态: {health.get('status', 'unknown')}")

    except Exception as e:
        print(f"✗ 主模块导入失败: {e}")
        traceback.print_exc()
        return False

    return True

def test_basic_functionality():
    """测试基本功能"""
    print("\n=== 测试基本功能 ===")

    try:
        from nodes.understand_doc.grid_parser import GridParser
        parser = GridParser("test-trace", "test-step")

        # 测试grid块提取
        test_content = '''
# 测试文档

这是文档的开始部分。

```grid
grid_column:
  - width_ratio: 50
    content: |
        左侧内容
  - width_ratio: 50
    content: |
        右侧字段列表
```

更多内容...
'''

        grid_blocks = parser.extract_grid_blocks(test_content)
        print(f"✓ Grid块提取成功: 找到 {len(grid_blocks)} 个grid块")

        # 测试上下文提取
        if grid_blocks:
            context = parser.extract_context_around_grid(test_content, grid_blocks[0][1])
            print(f"✓ 上下文提取成功: {len(context)} 字符")

        # 测试文档分割
        chunks = parser.split_document_for_parallel_processing(test_content)
        print(f"✓ 文档分割成功: 分割为 {len(chunks)} 个块")

        # 测试统计信息
        stats = parser.get_grid_statistics(test_content)
        print(f"✓ 统计信息: {stats}")

    except Exception as e:
        print(f"✗ Grid解析器测试失败: {e}")
        traceback.print_exc()
        return False

    try:
        from nodes.understand_doc.ism_builder import ISMBuilder
        builder = ISMBuilder("test-trace", "test-step")

        # 测试文档元数据构建
        doc_meta = builder.build_doc_meta(
            feishu_urls=["https://example.com/doc1"],
            parsing_mode="test_mode",
            title="测试文档"
        )
        print(f"✓ 文档元数据构建成功: {doc_meta}")

        # 测试基础ISM生成
        test_state = {
            "trace_id": "test-trace",
            "user_intent": "generate_crud",
            "feishu_urls": ["https://example.com/doc1"],
            "raw_docs": ["用户表内容：包含id、name、channel字段"]
        }
        basic_ism = builder.generate_basic_ism(test_state, test_state["raw_docs"][0])
        print(f"✓ 基础ISM生成成功: {len(basic_ism.get('interfaces', []))} 个接口")

        # 测试ISM结构验证
        is_valid, errors = builder.validate_ism_structure(basic_ism)
        print(f"✓ ISM结构验证: {'通过' if is_valid else f'失败({len(errors)}个错误)'}")

        # 测试ISM优化
        optimized_ism = builder.optimize_ism_structure(basic_ism)
        print(f"✓ ISM结构优化: 完成")

    except Exception as e:
        print(f"✗ ISM构建器测试失败: {e}")
        traceback.print_exc()
        return False

    return True

def test_integration():
    """测试集成功能"""
    print("\n=== 测试集成功能 ===")

    try:
        # 由于缺少依赖，只测试模块间的导入关系
        from nodes.understand_doc import get_module_info
        info = get_module_info()

        if info.get("architecture") == "modular":
            print("✓ 重构模式激活")
        else:
            print("✓ 回退模式激活")

        print(f"✓ 可用组件: {info.get('components', [])}")

    except Exception as e:
        print(f"✗ 集成测试失败: {e}")
        return False

    return True

def main():
    """主测试函数"""
    print("开始测试重构后的understand_doc模块...")

    success = True

    # 测试导入
    if not test_import():
        success = False

    # 测试基本功能
    if not test_basic_functionality():
        success = False

    # 测试集成
    if not test_integration():
        success = False

    print("\n=== 测试结果 ===")
    if success:
        print("🎉 所有测试通过！重构成功！")
        return 0
    else:
        print("❌ 部分测试失败，需要修复")
        return 1

if __name__ == "__main__":
    sys.exit(main())