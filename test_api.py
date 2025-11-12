#!/usr/bin/env python3
"""
API 测试脚本
测试 FastAPI 服务器的功能
"""

import requests
import json

def test_api():
    """测试 API 接口"""
    base_url = "http://localhost:8123"

    print("🚀 开始测试 AI Agent MVP API")
    print("=" * 50)

    # 1. 测试根路径
    try:
        response = requests.get(f"{base_url}/")
        print(f"✅ 根路径测试: {response.json()}")
    except Exception as e:
        print(f"❌ 根路径测试失败: {e}")
        return

    # 2. 创建 thread
    try:
        response = requests.post(f"{base_url}/threads", json={})
        thread_data = response.json()
        thread_id = thread_data["thread_id"]
        print(f"✅ 创建 Thread: {thread_id}")
    except Exception as e:
        print(f"❌ 创建 Thread 失败: {e}")
        return

    # 3. 运行工作流
    try:
        run_data = {
            "assistant_id": "agent",
            "input": {
                "feishu_urls": ["https://feishu.cn/doc/test123"],
                "user_intent": "generate_crud",
                "trace_id": "api-test-001"
            }
        }

        response = requests.post(
            f"{base_url}/threads/{thread_id}/runs/wait",
            json=run_data
        )

        if response.status_code == 200:
            result = response.json()
            print(f"✅ 工作流运行成功!")
            print(f"   Status: {result['status']}")
            print(f"   Trace ID: {result['result']['trace_id']}")
            print(f"   ISM 接口数: {len(result['result']['response']['ism']['interfaces'])}")
            print(f"   MCP 成功率: {result['result']['response']['mcp_execution']['success_rate']}")
        else:
            print(f"❌ 工作流运行失败: {response.status_code}")
            print(f"   错误: {response.text}")

    except Exception as e:
        print(f"❌ 工作流运行失败: {e}")

    print("=" * 50)
    print("🎉 API 测试完成!")

if __name__ == "__main__":
    test_api()