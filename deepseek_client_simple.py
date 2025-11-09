#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek API 客户端 - 简化版本
用于调用 DeepSeek 模型进行文档理解
"""

import os
import requests
import json
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class DeepSeekClient:
    """DeepSeek API 客户端"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        初始化 DeepSeek 客户端

        Args:
            api_key: DeepSeek API密钥，如果不提供则从环境变量读取
            base_url: API基础URL，如果不提供则使用默认值
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/chat/completions")

        if not self.api_key:
            print("未配置DEEPSEEK_API_KEY，将使用mock模式")
            self.use_mock = True
        else:
            self.use_mock = False
            print(f"DeepSeek客户端初始化成功 - base_url: {self.base_url}")

    def call_llm(self, system_prompt: str, user_prompt: str, model: str = "deepseek-chat",
                 temperature: float = 0.1, max_tokens: int = 40000) -> str:
        """
        调用 DeepSeek 模型

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            model: 模型名称，默认为 deepseek-chat
            temperature: 温度参数，控制输出的随机性
            max_tokens: 最大输出token数

        Returns:
            模型响应文本
        """
        if self.use_mock:
            return self._mock_response(system_prompt, user_prompt)

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False
            }
            print(f"system_prompt: {system_prompt}")
            print(f"user_prompt: {user_prompt}")
            print(f"调用DeepSeek API - model: {model} , temperature: {temperature} , max_tokens: {max_tokens}")

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            print(f"DeepSeek API响应状态码: {response.status_code} 响应内容: {response.text}" )
            response.raise_for_status()
            result = response.json()

            if "choices" not in result or len(result["choices"]) == 0:
                raise ValueError("API响应格式异常：缺少choices字段")

            content = result["choices"][0]["message"]["content"]

            # 清理markdown代码块标记（如果存在）
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]  # 移除 ```json
            if content.startswith("```"):
                content = content[3:]   # 移除 ```
            if content.endswith("```"):
                content = content[:-3]  # 移除 ```
            content = content.strip()

            print(f"DeepSeek API调用成功 - response_length: {len(content)}")
            return content

        except requests.exceptions.Timeout:
            print("DeepSeek API调用超时")
            raise Exception("DeepSeek API调用超时")
        except requests.exceptions.RequestException as e:
            print(f"DeepSeek API网络错误: {str(e)}")
            raise Exception(f"DeepSeek API网络错误: {str(e)}")
        except json.JSONDecodeError as e:
            print(f"DeepSeek API响应JSON解析失败: {str(e)}")
            raise Exception(f"DeepSeek API响应格式错误: {str(e)}")
        except Exception as e:
            print(f"DeepSeek API调用失败: {str(e)}")
            # 降级到mock响应
            print("降级使用mock响应")
            return self._mock_response(system_prompt, user_prompt)

    def _mock_response(self, system_prompt: str, user_prompt: str) -> str:
        """
        Mock响应，用于开发和测试

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词

        Returns:
            模拟的ISM JSON响应
        """
        print("使用DeepSeek Mock响应")

        # 根据用户提示词内容智能生成mock响应
        if "商品" in user_prompt and "订单" in user_prompt:
            # 电商系统场景
            mock_ism_response = """{
  "doc_meta": {
    "title": "电商系统需求文档",
    "url": "",
    "version": "latest"
  },
  "entities": [
    {
      "id": "ent_products",
      "name": "products",
      "label": "商品",
      "fields": [
        {"name": "id", "type": "string", "required": true, "desc": "主键"},
        {"name": "name", "type": "string", "required": true, "desc": "商品名称"},
        {"name": "price", "type": "decimal", "required": true, "desc": "价格"},
        {"name": "category", "type": "string", "required": true, "desc": "分类"},
        {"name": "stock", "type": "integer", "required": true, "desc": "库存"}
      ]
    },
    {
      "id": "ent_orders",
      "name": "orders",
      "label": "订单",
      "fields": [
        {"name": "id", "type": "string", "required": true, "desc": "主键"},
        {"name": "user_id", "type": "string", "required": true, "desc": "用户ID"},
        {"name": "total_amount", "type": "decimal", "required": true, "desc": "总金额"},
        {"name": "status", "type": "string", "required": true, "desc": "状态"},
        {"name": "created_at", "type": "datetime", "required": true, "desc": "创建时间"}
      ]
    },
    {
      "id": "ent_users",
      "name": "users",
      "label": "用户",
      "fields": [
        {"name": "id", "type": "string", "required": true, "desc": "主键"},
        {"name": "username", "type": "string", "required": true, "desc": "用户名"},
        {"name": "email", "type": "string", "required": true, "desc": "邮箱"},
        {"name": "phone", "type": "string", "required": false, "desc": "电话"},
        {"name": "address", "type": "text", "required": false, "desc": "地址"}
      ]
    }
  ],
  "views": [
    {
      "id": "view_product_category_stats",
      "type": "chart",
      "title": "商品分类统计",
      "data_entity": "ent_products",
      "dimension": "category",
      "metric": "count(*)",
      "chart_type": "pie"
    },
    {
      "id": "view_order_status_stats",
      "type": "chart",
      "title": "订单状态分布",
      "data_entity": "ent_orders",
      "dimension": "status",
      "metric": "count(*)",
      "chart_type": "bar"
    }
  ],
  "actions": [
    {
      "id": "act_products_crud",
      "type": "crud",
      "target_entity": "ent_products",
      "ops": ["create", "read", "update", "delete"]
    },
    {
      "id": "act_orders_crud",
      "type": "crud",
      "target_entity": "ent_orders",
      "ops": ["create", "read", "update", "delete"]
    },
    {
      "id": "act_users_crud",
      "type": "crud",
      "target_entity": "ent_users",
      "ops": ["create", "read", "update", "delete"]
    }
  ],
  "__pending__": []
}"""
        elif "用户" in user_prompt and "订单" in user_prompt:
            # 用户和订单系统场景
            mock_ism_response = """{
  "doc_meta": {
    "title": "用户订单管理系统",
    "url": "",
    "version": "latest"
  },
  "entities": [
    {
      "id": "ent_users",
      "name": "users",
      "label": "用户",
      "fields": [
        {"name": "id", "type": "string", "required": true, "desc": "主键"},
        {"name": "name", "type": "string", "required": true, "desc": "用户姓名"},
        {"name": "email", "type": "string", "required": false, "desc": "邮箱"}
      ]
    },
    {
      "id": "ent_orders",
      "name": "orders",
      "label": "订单",
      "fields": [
        {"name": "id", "type": "string", "required": true, "desc": "主键"},
        {"name": "user_id", "type": "string", "required": true, "desc": "用户ID"},
        {"name": "amount", "type": "decimal", "required": true, "desc": "订单金额"},
        {"name": "status", "type": "string", "required": true, "desc": "订单状态"}
      ]
    }
  ],
  "views": [
    {
      "id": "view_order_stats",
      "type": "chart",
      "title": "订单状态统计",
      "data_entity": "ent_orders",
      "dimension": "status",
      "metric": "count(*)",
      "chart_type": "bar"
    }
  ],
  "actions": [
    {
      "id": "act_users_crud",
      "type": "crud",
      "target_entity": "ent_users",
      "ops": ["create", "read", "update", "delete"]
    },
    {
      "id": "act_orders_crud",
      "type": "crud",
      "target_entity": "ent_orders",
      "ops": ["create", "read", "update", "delete"]
    }
  ],
  "__pending__": []
}"""
        else:
            # 默认用户系统场景
            mock_ism_response = """{
  "doc_meta": {
    "title": "用户管理系统需求",
    "url": "",
    "version": "latest"
  },
  "entities": [
    {
      "id": "ent_users",
      "name": "users",
      "label": "用户",
      "fields": [
        {"name": "id", "type": "string", "required": true, "desc": "主键"},
        {"name": "name", "type": "string", "required": true, "desc": "用户姓名"},
        {"name": "email", "type": "string", "required": false, "desc": "邮箱地址"},
        {"name": "channel", "type": "string", "required": false, "desc": "注册渠道"},
        {"name": "created_at", "type": "datetime", "required": true, "desc": "创建时间"}
      ]
    }
  ],
  "views": [
    {
      "id": "view_user_channel_stats",
      "type": "chart",
      "title": "用户渠道分布统计",
      "data_entity": "ent_users",
      "dimension": "channel",
      "metric": "count(*)",
      "chart_type": "pie"
    }
  ],
  "actions": [
    {
      "id": "act_users_crud",
      "type": "crud",
      "target_entity": "ent_users",
      "ops": ["create", "read", "update", "delete"]
    }
  ],
  "__pending__": []
}"""

        return mock_ism_response

    def test_connection(self) -> bool:
        """
        测试API连接

        Returns:
            连接是否成功
        """
        if self.use_mock:
            print("Mock模式，跳过连接测试")
            return True

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "user", "content": "测试连接"}
                ],
                "max_tokens": 10
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=10
            )

            response.raise_for_status()
            print("DeepSeek API连接测试成功")
            return True

        except Exception as e:
            print(f"DeepSeek API连接测试失败: {str(e)}")
            return False


# 全局客户端实例
_deepseek_client = None


def get_deepseek_client() -> DeepSeekClient:
    """
    获取DeepSeek客户端实例（单例模式）

    Returns:
        DeepSeek客户端实例
    """
    global _deepseek_client
    if _deepseek_client is None:
        _deepseek_client = DeepSeekClient()
    return _deepseek_client


def call_deepseek_llm(system_prompt: str, user_prompt: str, **kwargs) -> str:
    """
    便捷函数：调用DeepSeek模型

    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        **kwargs: 其他参数

    Returns:
        模型响应文本
    """
    client = get_deepseek_client()
    return client.call_llm(system_prompt, user_prompt, **kwargs)