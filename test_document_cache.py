#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档缓存功能测试脚本
测试文档缓存系统的完整功能
"""

import time
import json
from utils.document_cache import get_document_cache, try_get_document_cache, store_document_cache
from utils.logger import logger


def test_basic_cache_operations():
    """测试基本缓存操作"""
    print("=" * 50)
    print("测试基本缓存操作")
    print("=" * 50)

    # 获取缓存实例
    cache = get_document_cache()

    # 准备测试数据
    raw_docs = [
        "# 测试文档\n这是一个测试文档，包含用户表信息\n字段：id, name, email",
        "# 第二个测试文档\n包含订单表信息\n字段：order_id, user_id, amount"
    ]
    feishu_urls = ["https://feishu.cn/doc/test123", "https://feishu.cn/doc/test456"]
    user_intent = "generate_crud"

    # 测试缓存存储
    print("1. 测试缓存存储...")
    test_ism = {"doc_meta": {"title": "测试文档"}, "interfaces": []}
    test_plan = [{"step": "create_table", "table": "users"}]
    test_flow = '{"nodes": [], "edges": []}'
    test_mcp = [{"action": "create", "target": "users"}]
    test_response = {"status": "success", "message": "测试完成"}

    store_document_cache(
        raw_docs=raw_docs,
        feishu_urls=feishu_urls,
        user_intent=user_intent,
        ism_result=test_ism,
        plan_result=test_plan,
        final_flow_json=test_flow,
        mcp_payloads=test_mcp,
        final_response=test_response,
        processing_time_ms=1500.0
    )
    print("✓ 缓存存储成功")

    # 测试缓存检索
    print("\n2. 测试缓存检索...")
    cached_entry = try_get_document_cache(raw_docs, user_intent)
    if cached_entry:
        print("✓ 缓存检索成功")
        print(f"  文档hash: {cached_entry.doc_hash[:16]}...")
        print(f"  命中次数: {cached_entry.hit_count}")
        print(f"  处理时间: {cached_entry.processing_time_ms}ms")
        print(f"  文档预览: {cached_entry.doc_preview[:50]}...")
    else:
        print("✗ 缓存检索失败")
        return False

    # 测试相同内容再次检索（应该命中）
    print("\n3. 测试相同内容再次检索...")
    cached_entry2 = try_get_document_cache(raw_docs, user_intent)
    if cached_entry2 and cached_entry2.hit_count > 1:
        print(f"✓ 缓存再次命中，命中次数: {cached_entry2.hit_count}")
    else:
        print("✗ 缓存命中次数未增加")
        return False

    return True


def test_cache_with_different_content():
    """测试不同内容的缓存区分"""
    print("\n" + "=" * 50)
    print("测试不同内容的缓存区分")
    print("=" * 50)

    cache = get_document_cache()

    # 原始文档
    raw_docs1 = ["# 测试文档1\n用户表：id, name"]
    user_intent = "generate_crud"

    # 不同文档
    raw_docs2 = ["# 测试文档2\n产品表：id, product_name, price"]

    # 存储第一个文档
    print("1. 存储第一个文档...")
    store_document_cache(
        raw_docs=raw_docs1,
        feishu_urls=["https://feishu.cn/doc/doc1"],
        user_intent=user_intent,
        ism_result={"doc_meta": {"title": "文档1"}},
        plan_result=[],
        final_flow_json="{}",
        mcp_payloads=[],
        final_response={"status": "success"}
    )

    # 检索第一个文档
    print("2. 检索第一个文档...")
    entry1 = try_get_document_cache(raw_docs1, user_intent)
    if entry1:
        print("✓ 第一个文档缓存命中")
    else:
        print("✗ 第一个文档缓存未命中")
        return False

    # 检索第二个文档（应该未命中）
    print("3. 检索第二个文档（应该未命中）...")
    entry2 = try_get_document_cache(raw_docs2, user_intent)
    if entry2 is None:
        print("✓ 第二个文档正确区分，缓存未命中")
    else:
        print("✗ 第二个文档缓存错误命中")
        return False

    return True


def test_cache_with_different_intent():
    """测试不同用户意图的缓存区分"""
    print("\n" + "=" * 50)
    print("测试不同用户意图的缓存区分")
    print("=" * 50)

    raw_docs = ["# 测试文档\n用户表：id, name, email"]

    # 测试不同意图
    intents = ["generate_crud", "generate_api", "generate_dashboard"]

    for intent in intents:
        print(f"1. 测试意图: {intent}")
        entry = try_get_document_cache([raw_docs[0]], intent)
        if entry is None:
            print(f"✓ 意图 '{intent}' 缓存未命中（正确）")

            # 存储缓存
            store_document_cache(
                raw_docs=[raw_docs[0]],
                feishu_urls=[f"https://feishu.cn/doc/{intent}"],
                user_intent=intent,
                ism_result={"doc_meta": {"title": f"文档_{intent}"}},
                plan_result=[],
                final_flow_json="{}",
                mcp_payloads=[],
                final_response={"status": "success", "intent": intent}
            )
            print(f"✓ 意图 '{intent}' 缓存已存储")
        else:
            print(f"! 意图 '{intent}' 缓存已存在")

    # 验证每个意图都有独立的缓存
    print("\n2. 验证不同意图的缓存独立性...")
    for intent in intents:
        entry = try_get_document_cache([raw_docs[0]], intent)
        if entry and entry.user_intent == intent:
            print(f"✓ 意图 '{intent}' 有独立缓存")
        else:
            print(f"✗ 意图 '{intent}' 缓存异常")
            return False

    return True


def test_cache_statistics():
    """测试缓存统计功能"""
    print("\n" + "=" * 50)
    print("测试缓存统计功能")
    print("=" * 50)

    cache = get_document_cache()

    # 获取统计信息
    stats = cache.get_stats()
    print("缓存统计信息:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # 列出最近的缓存条目
    print("\n最近的缓存条目:")
    entries = cache.list_entries(limit=5)
    for i, entry in enumerate(entries, 1):
        print(f"  {i}. {entry['doc_hash']} - {entry['user_intent']} - 命中: {entry['hit_count']}次")

    return True


def test_cache_expiration():
    """测试缓存过期功能"""
    print("\n" + "=" * 50)
    print("测试缓存过期功能")
    print("=" * 50)

    # 创建一个短期缓存实例
    from utils.document_cache import DocumentCache
    short_cache = DocumentCache(cache_dir="./cache_test", ttl_seconds=1)

    # 直接使用短期缓存实例进行存储和检索
    raw_docs = ["# 过期测试文档"]
    user_intent = "test_expire"

    # 存储测试数据
    print("1. 存储短期缓存数据...")
    short_cache.put(
        raw_docs=raw_docs,
        feishu_urls=["https://feishu.cn/doc/expire"],
        user_intent=user_intent,
        ism_result={"doc_meta": {"title": "过期测试"}},
        plan_result=[],
        final_flow_json="{}",
        mcp_payloads=[],
        final_response={"status": "success"}
    )

    # 立即检索（应该命中）
    print("2. 立即检索缓存...")
    entry = short_cache.get(raw_docs, user_intent)
    if entry:
        print("✓ 缓存命中")
    else:
        print("✗ 缓存未命中")
        return False

    # 等待过期
    print("3. 等待缓存过期（2秒）...")
    time.sleep(2)

    # 再次检索（应该未命中）
    print("4. 缓存过期后检索...")
    entry = short_cache.get(raw_docs, user_intent)
    if entry is None:
        print("✓ 缓存正确过期")
    else:
        print("✗ 缓存未过期")
        return False

    return True


def test_cache_cleanup():
    """测试缓存清理功能"""
    print("\n" + "=" * 50)
    print("测试缓存清理功能")
    print("=" * 50)

    cache = get_document_cache()

    # 获取清理前的统计
    stats_before = cache.get_stats()
    print(f"清理前缓存条目数: {stats_before['total_entries']}")

    # 执行清理
    print("1. 执行过期缓存清理...")
    cleaned_count = cache.cleanup_expired()
    print(f"✓ 清理了 {cleaned_count} 个过期条目")

    # 获取清理后的统计
    stats_after = cache.get_stats()
    print(f"清理后缓存条目数: {stats_after['total_entries']}")

    return True


def main():
    """主测试函数"""
    print("开始文档缓存功能测试")
    print("=" * 80)

    test_functions = [
        test_basic_cache_operations,
        test_cache_with_different_content,
        test_cache_with_different_intent,
        test_cache_statistics,
        test_cache_expiration,
        test_cache_cleanup
    ]

    passed_tests = 0
    total_tests = len(test_functions)

    for i, test_func in enumerate(test_functions, 1):
        try:
            print(f"\n[{i}/{total_tests}] 运行测试: {test_func.__name__}")
            if test_func():
                print(f"✓ 测试 {test_func.__name__} 通过")
                passed_tests += 1
            else:
                print(f"✗ 测试 {test_func.__name__} 失败")
        except Exception as e:
            print(f"✗ 测试 {test_func.__name__} 异常: {str(e)}")
            import traceback
            traceback.print_exc()

    # 测试总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    print(f"总测试数: {total_tests}")
    print(f"通过测试: {passed_tests}")
    print(f"失败测试: {total_tests - passed_tests}")
    print(f"通过率: {passed_tests/total_tests*100:.1f}%")

    if passed_tests == total_tests:
        print("\n🎉 所有测试通过！文档缓存功能正常工作")
    else:
        print(f"\n⚠️  有 {total_tests - passed_tests} 个测试失败，需要检查")


if __name__ == "__main__":
    main()