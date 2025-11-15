#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书认证客户端
处理飞书应用的完整认证流程
"""

import os
import json
import time
import requests
from typing import Dict, Optional
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class FeishuAuthClient:
    """飞书认证客户端"""

    def __init__(self, app_id: str, app_secret: str):
        """
        初始化认证客户端

        Args:
            app_id: 飞书应用 ID
            app_secret: 飞书应用密钥
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = "https://open.feishu.cn/open-apis"
        self._token_cache = {}

    def get_tenant_access_token(self, force_refresh: bool = False) -> str:
        """
        获取租户访问令牌

        Args:
            force_refresh: 是否强制刷新令牌

        Returns:
            访问令牌
        """
        # 检查缓存
        if not force_refresh and "tenant_access_token" in self._token_cache:
            cached_token = self._token_cache["tenant_access_token"]
            if time.time() < cached_token["expires_at"] - 300:  # 提前5分钟刷新
                return cached_token["token"]

        # 请求新的令牌
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()

            result = response.json()
            if result.get("code") != 0:
                raise Exception(f"获取令牌失败: {result.get('msg', 'Unknown error')}")

            token = result.get("tenant_access_token")
            expires_in = result.get("expire", 7200)  # 默认2小时

            # 缓存令牌
            self._token_cache["tenant_access_token"] = {
                "token": token,
                "expires_at": time.time() + expires_in
            }

            print(f"[SUCCESS] 获取访问令牌成功，有效期: {expires_in}秒")
            return token

        except requests.RequestException as e:
            raise Exception(f"请求飞书认证API失败: {str(e)}")

    def get_app_access_token(self, force_refresh: bool = False) -> str:
        """
        获取应用访问令牌

        Args:
            force_refresh: 是否强制刷新令牌

        Returns:
            访问令牌
        """
        # 检查缓存
        if not force_refresh and "app_access_token" in self._token_cache:
            cached_token = self._token_cache["app_access_token"]
            if time.time() < cached_token["expires_at"] - 300:  # 提前5分钟刷新
                return cached_token["token"]

        # 请求新的令牌
        url = f"{self.base_url}/auth/v3/app_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()

            result = response.json()
            if result.get("code") != 0:
                raise Exception(f"获取应用令牌失败: {result.get('msg', 'Unknown error')}")

            token = result.get("app_access_token")
            expires_in = result.get("expire", 7200)  # 默认2小时

            # 缓存令牌
            self._token_cache["app_access_token"] = {
                "token": token,
                "expires_at": time.time() + expires_in
            }

            print(f"[SUCCESS] 获取应用访问令牌成功，有效期: {expires_in}秒")
            return token

        except requests.RequestException as e:
            raise Exception(f"请求飞书认证API失败: {str(e)}")


def init_feishu_auth_from_env() -> Optional[FeishuAuthClient]:
    """
    从环境变量初始化飞书认证客户端

    Returns:
        认证客户端实例，如果配置不全则返回 None
    """
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")

    if not app_id or not app_secret:
        print("[WARN] 未配置飞书应用凭证 (FEISHU_APP_ID, FEISHU_APP_SECRET)")
        return None

    return FeishuAuthClient(app_id, app_secret)


def test_feishu_auth():
    """
    测试飞书认证功能
    """
    print("飞书认证测试")
    print("=" * 50)

    # 从环境变量获取配置
    auth_client = init_feishu_auth_from_env()
    if not auth_client:
        print("[ERROR] 请配置环境变量:")
        print("export FEISHU_APP_ID='your_app_id'")
        print("export FEISHU_APP_SECRET='your_app_secret'")
        return

    try:
        # 测试获取租户访问令牌
        print("正在获取租户访问令牌...")
        tenant_token = auth_client.get_tenant_access_token()
        print(f"租户访问令牌: {tenant_token[:20]}...")

        # 测试获取应用访问令牌
        print("\n正在获取应用访问令牌...")
        app_token = auth_client.get_app_access_token()
        print(f"应用访问令牌: {app_token[:20]}...")

        print("\n[SUCCESS] 认证测试成功!")

        # 返回可用的令牌
        return {
            "tenant_access_token": tenant_token,
            "app_access_token": app_token
        }

    except Exception as e:
        print(f"[ERROR] 认证测试失败: {e}")
        return None


if __name__ == "__main__":
    test_feishu_auth()