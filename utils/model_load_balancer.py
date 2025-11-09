#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多模型负载均衡器
支持多个LLM提供商的智能调度和故障转移
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import random
from utils.logger import logger


class ModelStatus(Enum):
    """模型状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    provider: str
    endpoint: str
    api_key: str
    model: str
    max_tokens: int
    temperature_range: Tuple[float, float]
    timeout: int
    priority: int  # 优先级，数字越小优先级越高
    cost_per_token: float  # 每个token的成本
    rate_limit: int  # 每分钟请求限制
    current_usage: int  # 当前使用量
    status: ModelStatus
    last_success: float
    last_error: str
    success_rate: float
    avg_response_time: float
    error_count: int


class ModelLoadBalancer:
    """多模型负载均衡器"""

    def __init__(self):
        self.models: Dict[str, ModelConfig] = {}
        self.round_robin_index = 0
        self.performance_history: Dict[str, List[Dict]] = {}
        self.health_check_interval = 30  # 30秒
        self.health_check_task = None

        # 初始化默认模型配置
        self._initialize_default_models()

        # 启动健康检查
        self._start_health_check()

    def _initialize_default_models(self):
        """初始化默认模型配置"""
        import os
        from dotenv import load_dotenv

        load_dotenv()

        # DeepSeek模型
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key:
            self.models["deepseek"] = ModelConfig(
                name="deepseek-chat",
                provider="deepseek",
                endpoint="https://api.deepseek.com",
                api_key=deepseek_key,
                model="deepseek-chat",
                max_tokens=4096,
                temperature_range=(0.0, 2.0),
                timeout=60,
                priority=1,
                cost_per_token=0.0001,
                rate_limit=100,
                current_usage=0,
                status=ModelStatus.HEALTHY,
                last_success=time.time(),
                last_error="",
                success_rate=1.0,
                avg_response_time=5.0,
                error_count=0
            )

        # 可以添加其他模型提供商
        # OpenAI模型
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            self.models["gpt-4"] = ModelConfig(
                name="gpt-4",
                provider="openai",
                endpoint="https://api.openai.com",
                api_key=openai_key,
                model="gpt-4",
                max_tokens=4096,
                temperature_range=(0.0, 2.0),
                timeout=90,
                priority=2,
                cost_per_token=0.0003,
                rate_limit=60,
                current_usage=0,
                status=ModelStatus.HEALTHY,
                last_success=time.time(),
                last_error="",
                success_rate=1.0,
                avg_response_time=8.0,
                error_count=0
            )

        # Claude模型
        claude_key = os.getenv("ANTHROPIC_API_KEY")
        if claude_key:
            self.models["claude"] = ModelConfig(
                name="claude-3-sonnet",
                provider="anthropic",
                endpoint="https://api.anthropic.com",
                api_key=claude_key,
                model="claude-3-sonnet-20240229",
                max_tokens=4096,
                temperature_range=(0.0, 1.0),
                timeout=120,
                priority=3,
                cost_per_token=0.00015,
                rate_limit=50,
                current_usage=0,
                status=ModelStatus.HEALTHY,
                last_success=time.time(),
                last_error="",
                success_rate=1.0,
                avg_response_time=10.0,
                error_count=0
            )

        logger.info("model_load_balancer", "models_initialized", f"初始化了 {len(self.models)} 个模型")

    def _start_health_check(self):
        """启动健康检查任务"""
        if self.health_check_task is None:
            self.health_check_task = asyncio.create_task(self._health_check_loop())

    async def _health_check_loop(self):
        """健康检查循环"""
        while True:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.health_check_interval)
            except Exception as e:
                logger.error("model_load_balancer", "health_check_error", f"健康检查错误: {str(e)}")
                await asyncio.sleep(60)  # 出错时等待更长时间

    async def _perform_health_checks(self):
        """执行健康检查"""
        tasks = []
        for model_name, model_config in self.models.items():
            if model_config.status != ModelStatus.UNAVAILABLE:
                tasks.append(self._check_model_health(model_name, model_config))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_model_health(self, model_name: str, model_config: ModelConfig):
        """检查单个模型的健康状态"""
        try:
            # 发送简单的测试请求
            headers = {
                "Authorization": f"Bearer {model_config.api_key}",
                "Content-Type": "application/json"
            }

            test_payload = {
                "model": model_config.model,
                "messages": [
                    {"role": "user", "content": "Hello"}
                ],
                "max_tokens": 10,
                "temperature": 0.1
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{model_config.endpoint}/chat/completions",
                    headers=headers,
                    json=test_payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        # 模型健康
                        if model_config.status != ModelStatus.HEALTHY:
                            model_config.status = ModelStatus.HEALTHY
                            logger.info("model_load_balancer", "model_recovered",
                                       f"模型 {model_name} 恢复健康状态")
                    else:
                        # 模型异常
                        model_config.status = ModelStatus.DEGRADED
                        model_config.last_error = f"HTTP {response.status}"
                        model_config.error_count += 1

        except Exception as e:
            model_config.status = ModelStatus.UNAVAILABLE
            model_config.last_error = str(e)
            model_config.error_count += 1
            logger.warning("model_load_balancer", "model_unhealthy",
                         f"模型 {model_name} 不可用: {str(e)}")

    def select_model(self, priority: str = "balanced") -> Optional[ModelConfig]:
        """
        选择最优模型

        Args:
            priority: 选择策略 - "fastest", "cheapest", "most_reliable", "balanced"

        Returns:
            选中的模型配置
        """
        healthy_models = [
            (name, config) for name, config in self.models.items()
            if config.status == ModelStatus.HEALTHY
        ]

        if not healthy_models:
            # 如果没有健康的模型，尝试降级的模型
            degraded_models = [
                (name, config) for name, config in self.models.items()
                if config.status == ModelStatus.DEGRADED
            ]
            if degraded_models:
                logger.warning("model_load_balancer", "no_healthy_models",
                             "使用降级模型")
                healthy_models = degraded_models

        if not healthy_models:
            logger.error("model_load_balancer", "no_available_models", "没有可用的模型")
            return None

        # 根据策略选择模型
        if priority == "fastest":
            return min(healthy_models, key=lambda x: x[1].avg_response_time)[1]
        elif priority == "cheapest":
            return min(healthy_models, key=lambda x: x[1].cost_per_token)[1]
        elif priority == "most_reliable":
            return max(healthy_models, key=lambda x: x[1].success_rate)[1]
        elif priority == "round_robin":
            # 轮询选择
            model = healthy_models[self.round_robin_index % len(healthy_models)][1]
            self.round_robin_index += 1
            return model
        else:  # balanced
            # 综合评分
            def calculate_score(name, config):
                score = 0
                # 成功率权重40%
                score += config.success_rate * 40
                # 响应时间权重30%（越快越好）
                score += (1.0 / (config.avg_response_time + 1)) * 30
                # 成本权重20%（越便宜越好）
                score += (1.0 / (config.cost_per_token + 0.0001)) * 20
                # 优先级权重10%
                score += (10 - config.priority) * 10
                return score

            return max(healthy_models, key=lambda x: calculate_score(*x))[1]

    async def call_model(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        priority: str = "balanced",
        model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        调用选中的模型

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 温度参数
            max_tokens: 最大token数
            priority: 选择策略
            model_name: 指定模型名称

        Returns:
            模型响应结果
        """
        start_time = time.time()

        # 如果指定了模型名称，优先使用
        if model_name and model_name in self.models:
            model_config = self.models[model_name]
            if model_config.status == ModelStatus.UNAVAILABLE:
                logger.warning("model_load_balancer", "model_unavailable",
                             f"指定模型 {model_name} 不可用，自动选择")
                model_config = None
        else:
            model_config = None

        # 自动选择模型
        if model_config is None:
            model_config = self.select_model(priority)
            if model_config is None:
                raise Exception("没有可用的模型")

        # 检查速率限制
        current_minute = int(time.time() / 60)
        if hasattr(model_config, 'rate_limit_minute'):
            if model_config.rate_limit_minute != current_minute:
                model_config.current_usage = 0
                model_config.rate_limit_minute = current_minute

        if model_config.current_usage >= model_config.rate_limit:
            # 超出速率限制，选择其他模型
            logger.warning("model_load_balancer", "rate_limit_exceeded",
                         f"模型 {model_config.name} 超出速率限制")
            model_config = self.select_model("cheapest")  # 选择最便宜的备选模型
            if model_config is None:
                raise Exception("所有模型都超出速率限制")

        try:
            # 调用模型
            result = await self._call_model_api(
                model_config, system_prompt, user_prompt, temperature, max_tokens
            )

            # 更新统计信息
            response_time = time.time() - start_time
            self._update_model_stats(model_config, True, response_time)

            # 增加使用计数
            model_config.current_usage += 1

            return {
                "model": model_config.name,
                "provider": model_config.provider,
                "response": result,
                "response_time": response_time,
                "cost": self._calculate_cost(model_config, result)
            }

        except Exception as e:
            # 更新错误统计
            self._update_model_stats(model_config, False, time.time() - start_time)

            # 尝试故障转移到其他模型
            logger.warning("model_load_balancer", "model_call_failed",
                         f"模型 {model_config.name} 调用失败: {str(e)}")

            # 尝试其他可用模型
            available_models = [
                config for name, config in self.models.items()
                if config != model_config and config.status == ModelStatus.HEALTHY
            ]

            if available_models:
                backup_model = available_models[0]
                logger.info("model_load_balancer", "fallback_model",
                           f"故障转移到模型: {backup_model.name}")

                return await self.call_model(
                    system_prompt, user_prompt, temperature, max_tokens,
                    "most_reliable", backup_model.name
                )

            raise e

    async def _call_model_api(
        self,
        model_config: ModelConfig,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int
    ) -> str:
        """调用模型API"""
        headers = {
            "Authorization": f"Bearer {model_config.api_key}",
            "Content-Type": "application/json"
        }

        # 根据不同提供商调整请求格式
        if model_config.provider == "deepseek":
            payload = {
                "model": model_config.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "max_tokens": min(max_tokens, model_config.max_tokens),
                "stream": False
            }
            endpoint = f"{model_config.endpoint}/chat/completions"

        elif model_config.provider == "openai":
            payload = {
                "model": model_config.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "max_tokens": min(max_tokens, model_config.max_tokens),
                "stream": False
            }
            endpoint = f"{model_config.endpoint}/v1/chat/completions"

        elif model_config.provider == "anthropic":
            payload = {
                "model": model_config.model,
                "max_tokens": min(max_tokens, model_config.max_tokens),
                "temperature": temperature,
                "messages": [
                    {"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}
                ]
            }
            headers["x-api-key"] = model_config.api_key
            headers["anthropic-version"] = "2023-06-01"
            endpoint = f"{model_config.endpoint}/v1/messages"

        else:
            raise ValueError(f"不支持的提供商: {model_config.provider}")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=model_config.timeout)
            ) as response:
                response.raise_for_status()
                result = await response.json()

                # 根据不同提供商解析响应
                if model_config.provider == "anthropic":
                    return result["content"][0]["text"]
                else:
                    return result["choices"][0]["message"]["content"]

    def _update_model_stats(self, model_config: ModelConfig, success: bool, response_time: float):
        """更新模型统计信息"""
        # 更新成功率
        if not hasattr(model_config, 'total_requests'):
            model_config.total_requests = 0
            model_config.successful_requests = 0

        model_config.total_requests += 1
        if success:
            model_config.successful_requests += 1
            model_config.last_success = time.time()
            model_config.last_error = ""
        else:
            model_config.error_count += 1

        # 更新成功率
        model_config.success_rate = model_config.successful_requests / model_config.total_requests

        # 更新平均响应时间
        if not hasattr(model_config, 'total_response_time'):
            model_config.total_response_time = 0
            model_config.response_count = 0

        model_config.total_response_time += response_time
        model_config.response_count += 1
        model_config.avg_response_time = model_config.total_response_time / model_config.response_count

        # 更新状态
        if model_config.success_rate < 0.5 and model_config.total_requests > 10:
            model_config.status = ModelStatus.DEGRADED
        elif model_config.success_rate < 0.1 and model_config.total_requests > 20:
            model_config.status = ModelStatus.UNAVAILABLE
        elif model_config.success_rate > 0.9 and model_config.total_requests > 5:
            model_config.status = ModelStatus.HEALTHY

    def _calculate_cost(self, model_config: ModelConfig, response: str) -> float:
        """计算调用成本"""
        # 简化计算：假设输入和输出的token数量
        input_tokens = len(response.split()) * 1.3  # 估算输入token
        output_tokens = len(response.split()) * 1.3  # 估算输出token

        total_tokens = input_tokens + output_tokens
        return total_tokens * model_config.cost_per_token

    def get_model_status(self) -> Dict[str, Dict]:
        """获取所有模型状态"""
        status = {}
        for name, config in self.models.items():
            status[name] = {
                "provider": config.provider,
                "status": config.status.value,
                "success_rate": config.success_rate,
                "avg_response_time": config.avg_response_time,
                "current_usage": config.current_usage,
                "rate_limit": config.rate_limit,
                "last_error": config.last_error,
                "priority": config.priority
            }
        return status

    def add_model(self, model_config: ModelConfig):
        """添加新模型"""
        self.models[model_config.name] = model_config
        logger.info("model_load_balancer", "model_added", f"添加模型: {model_config.name}")

    def remove_model(self, model_name: str):
        """移除模型"""
        if model_name in self.models:
            del self.models[model_name]
            logger.info("model_load_balancer", "model_removed", f"移除模型: {model_name}")

    def shutdown(self):
        """关闭负载均衡器"""
        if self.health_check_task:
            self.health_check_task.cancel()
            self.health_check_task = None


# 全局负载均衡器实例
_load_balancer = None


def get_model_load_balancer() -> ModelLoadBalancer:
    """获取全局模型负载均衡器实例"""
    global _load_balancer
    if _load_balancer is None:
        _load_balancer = ModelLoadBalancer()
    return _load_balancer


async def call_llm_with_load_balancing(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.1,
    max_tokens: int = 2000,
    priority: str = "balanced",
    model_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    使用负载均衡调用LLM

    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        temperature: 温度参数
        max_tokens: 最大token数
        priority: 选择策略
        model_name: 指定模型名称

    Returns:
        模型响应结果
    """
    balancer = get_model_load_balancer()
    return await balancer.call_model(
        system_prompt, user_prompt, temperature, max_tokens, priority, model_name
    )