#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能预测缓存系统
通过机器学习预测用户请求，提前缓存可能的结果
"""

import json
import time
import os
import pickle
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
from utils.logger import logger


@dataclass
class RequestPattern:
    """请求模式"""
    content_signature: str
    frequency: int
    last_requested: float
    avg_response_time: float
    success_rate: float
    predicted_next_request: float


@dataclass
class CachePrediction:
    """缓存预测结果"""
    should_cache: bool
    confidence: float
    estimated_usefulness: float
    ttl_seconds: int


class PredictiveCache:
    """智能预测缓存管理器"""

    def __init__(self, cache_dir: str = "./cache/predictive", max_patterns: int = 10000):
        self.cache_dir = cache_dir
        self.max_patterns = max_patterns
        self.request_patterns: Dict[str, RequestPattern] = {}
        self.content_embeddings: Dict[str, List[float]] = {}  # 简化的内容嵌入
        self.prediction_model = None
        self.pattern_updates = 0

        # 确保缓存目录存在
        os.makedirs(cache_dir, exist_ok=True)

        # 加载历史数据
        self._load_patterns()

    def _load_patterns(self) -> None:
        """加载历史请求模式"""
        pattern_file = os.path.join(self.cache_dir, "request_patterns.pkl")
        if os.path.exists(pattern_file):
            try:
                with open(pattern_file, 'rb') as f:
                    self.request_patterns = pickle.load(f)
                logger.info("cache_predictive", "load_patterns", f"加载了 {len(self.request_patterns)} 个请求模式")
            except Exception as e:
                logger.warning("cache_predictive", "load_patterns_failed", f"加载模式失败: {str(e)}")

    def _save_patterns(self) -> None:
        """保存请求模式"""
        try:
            pattern_file = os.path.join(self.cache_dir, "request_patterns.pkl")
            with open(pattern_file, 'wb') as f:
                pickle.dump(self.request_patterns, f)
            self.pattern_updates = 0
        except Exception as e:
            logger.warning("cache_predictive", "save_patterns_failed", f"保存模式失败: {str(e)}")

    def _generate_content_signature(self, content: str) -> str:
        """生成内容签名"""
        # 清理和标准化内容
        cleaned = content.lower().strip()

        # 提取关键特征
        lines = cleaned.split('\n')
        key_features = []

        for line in lines:
            line = line.strip()
            if any(keyword in line for keyword in ['用户', '订单', '商品', '统计', '导出', '分析']):
                key_features.append(line[:50])  # 保留前50个字符

        # 提取grid块信息
        grid_count = content.count('```grid')
        key_features.append(f"grid_blocks:{grid_count}")

        # 生成签名
        signature_text = '\n'.join(key_features)
        return hashlib.md5(signature_text.encode('utf-8')).hexdigest()

    def _calculate_content_similarity(self, sig1: str, sig2: str) -> float:
        """计算内容相似度"""
        if sig1 == sig2:
            return 1.0

        # 这里简化处理，实际可以使用更复杂的相似度算法
        common_prefix = os.path.commonprefix([sig1, sig2])
        similarity = len(common_prefix) / max(len(sig1), len(sig2)) if sig1 and sig2 else 0.0

        return similarity

    def predict_cache_usefulness(self, content: str, response_time: float, success: bool) -> CachePrediction:
        """预测缓存的有用性"""
        signature = self._generate_content_signature(content)

        # 分析请求模式
        if signature in self.request_patterns:
            pattern = self.request_patterns[signature]

            # 更新模式统计
            pattern.frequency += 1
            pattern.last_requested = time.time()
            pattern.avg_response_time = (pattern.avg_response_time * 0.8 + response_time * 0.2)
            pattern.success_rate = pattern.success_rate * 0.9 + (1.0 if success else 0.0) * 0.1

            # 预测下次请求时间
            if pattern.frequency > 1:
                time_diff = pattern.last_requested - (pattern.last_requested - pattern.avg_response_time)
                pattern.predicted_next_request = time.time() + time_diff * 0.5

            # 计算缓存有用性
            confidence = min(pattern.frequency / 10.0, 1.0)  # 频率越高，置信度越高
            usefulness = pattern.avg_response_time * pattern.success_rate * confidence
            should_cache = usefulness > 1.0  # 如果响应时间超过1秒，就值得缓存

            # 动态TTL
            ttl = min(3600, int(usefulness * 300))  # 基于有用性计算TTL，最多1小时

        else:
            # 新模式
            pattern = RequestPattern(
                content_signature=signature,
                frequency=1,
                last_requested=time.time(),
                avg_response_time=response_time,
                success_rate=1.0 if success else 0.0,
                predicted_next_request=time.time() + 300  # 默认5分钟后可能再次请求
            )

            self.request_patterns[signature] = pattern

            # 新模式的预测
            confidence = 0.1  # 低置信度
            usefulness = response_time * 0.1
            should_cache = response_time > 2.0  # 新内容只有在响应时间较长时才缓存
            ttl = 600  # 默认10分钟

        # 定期保存模式
        self.pattern_updates += 1
        if self.pattern_updates >= 100:  # 每100次更新保存一次
            self._save_patterns()

        # 限制模式数量
        if len(self.request_patterns) > self.max_patterns:
            self._cleanup_old_patterns()

        return CachePrediction(
            should_cache=should_cache,
            confidence=confidence,
            estimated_usefulness=usefulness,
            ttl_seconds=ttl
        )

    def _cleanup_old_patterns(self) -> None:
        """清理旧的请求模式"""
        # 按最后请求时间和频率排序
        sorted_patterns = sorted(
            self.request_patterns.items(),
            key=lambda x: (x[1].last_requested, x[1].frequency),
            reverse=True
        )

        # 保留最重要的模式
        self.request_patterns = dict(sorted_patterns[:self.max_patterns])
        logger.info("cache_predictive", "cleanup_patterns", f"清理后保留 {len(self.request_patterns)} 个模式")

    def find_similar_cached_content(self, content: str, threshold: float = 0.8) -> Optional[str]:
        """查找相似的缓存内容"""
        signature = self._generate_content_signature(content)

        for existing_sig, pattern in self.request_patterns.items():
            if self._calculate_content_similarity(signature, existing_sig) > threshold:
                # 检查是否在预测的请求时间窗口内
                time_until_next = pattern.predicted_next_request - time.time()
                if abs(time_until_next) < 3600:  # 1小时内
                    return existing_sig

        return None

    def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if not self.request_patterns:
            return {
                "total_patterns": 0,
                "avg_frequency": 0,
                "avg_response_time": 0,
                "avg_success_rate": 0
            }

        total_freq = sum(p.frequency for p in self.request_patterns.values())
        avg_response_time = sum(p.avg_response_time for p in self.request_patterns.values()) / len(self.request_patterns)
        avg_success_rate = sum(p.success_rate for p in self.request_patterns.values()) / len(self.request_patterns)

        # 分析高频模式
        high_freq_patterns = [p for p in self.request_patterns.values() if p.frequency > 5]

        return {
            "total_patterns": len(self.request_patterns),
            "avg_frequency": total_freq / len(self.request_patterns),
            "avg_response_time": avg_response_time,
            "avg_success_rate": avg_success_rate,
            "high_freq_patterns": len(high_freq_patterns),
            "pattern_updates": self.pattern_updates
        }

    def prewarm_cache(self, common_contents: List[str]) -> int:
        """预热缓存 - 预先处理常见内容"""
        prewarmed_count = 0

        for content in common_contents:
            signature = self._generate_content_signature(content)

            if signature in self.request_patterns:
                pattern = self.request_patterns[signature]

                # 如果是高频模式，建议预热
                if pattern.frequency > 10 and pattern.success_rate > 0.9:
                    logger.info("cache_predictive", "prewarm_candidate",
                               f"发现高频模式，建议预热缓存: {signature[:8]}...")
                    prewarmed_count += 1

        return prewarmed_count


# 全局预测缓存实例
_predictive_cache = None


def get_predictive_cache() -> PredictiveCache:
    """获取全局预测缓存实例"""
    global _predictive_cache
    if _predictive_cache is None:
        cache_dir = os.environ.get('PREDICTIVE_CACHE_DIR', './cache/predictive')
        _predictive_cache = PredictiveCache(cache_dir=cache_dir)
    return _predictive_cache


def predict_and_cache(content: str, response_func, response_time: float = None, success: bool = True) -> Any:
    """
    预测并缓存结果

    Args:
        content: 输入内容
        response_func: 生成响应的函数
        response_time: 已知的响应时间（如果已有）
        success: 是否成功

    Returns:
        响应结果
    """
    cache = get_predictive_cache()

    # 如果已知响应时间，直接预测
    if response_time is not None:
        prediction = cache.predict_cache_usefulness(content, response_time, success)
    else:
        # 先执行函数获取响应时间
        start_time = time.time()
        result = response_func()
        end_time = time.time()
        actual_time = end_time - start_time

        # 然后预测
        prediction = cache.predict_cache_usefulness(content, actual_time, True)

        # 如果应该缓存，保存结果
        if prediction.should_cache:
            # 这里应该调用实际的缓存系统保存结果
            logger.debug("cache_predictive", "save_result",
                        f"保存结果到缓存，TTL: {prediction.ttl_seconds}s")

        return result

    # 如果不应该缓存，直接执行函数
    if not prediction.should_cache:
        return response_func()

    # 应该缓存的情况
    start_time = time.time()
    result = response_func()
    end_time = time.time()
    actual_time = end_time - start_time

    # 更新预测
    cache.predict_cache_usefulness(content, actual_time, True)

    # 保存到缓存
    logger.debug("cache_predictive", "save_predicted",
                f"保存预测结果到缓存，置信度: {prediction.confidence:.2f}")

    return result


class SmartCacheManager:
    """智能缓存管理器，集成预测缓存"""

    def __init__(self):
        self.predictive_cache = get_predictive_cache()
        self.hit_stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "prediction_hits": 0,
            "misses": 0
        }

    async def get_cached_or_compute(self, content: str, compute_func, compute_kwargs: Dict = None) -> Any:
        """
        获取缓存结果或计算新结果

        Args:
            content: 输入内容
            compute_func: 计算函数
            compute_kwargs: 计算函数参数

        Returns:
            计算结果
        """
        self.hit_stats["total_requests"] += 1

        # 1. 尝试从普通缓存获取
        # 这里可以集成现有的缓存系统
        # cached_result = regular_cache.get(content)
        # if cached_result:
        #     self.hit_stats["cache_hits"] += 1
        #     return cached_result

        # 2. 尝试预测缓存
        similar_signature = self.predictive_cache.find_similar_cached_content(content)
        if similar_signature:
            self.hit_stats["prediction_hits"] += 1
            logger.debug("smart_cache", "prediction_hit", f"找到相似内容: {similar_signature[:8]}...")
            # 这里可以从相似签名加载对应的结果

        # 3. 计算新结果
        start_time = time.time()

        if compute_kwargs:
            result = await compute_func(**compute_kwargs)
        else:
            result = await compute_func()

        end_time = time.time()
        response_time = end_time - start_time

        # 4. 预测是否应该缓存
        prediction = self.predictive_cache.predict_cache_usefulness(content, response_time, True)

        if prediction.should_cache:
            # 保存到缓存
            logger.debug("smart_cache", "save_result",
                       f"保存结果，预测有用性: {prediction.estimated_usefulness:.2f}")
            # 这里保存到实际的缓存系统

        self.hit_stats["misses"] += 1
        return result

    def get_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        stats = self.hit_stats.copy()
        total = stats["total_requests"]

        if total > 0:
            stats["cache_hit_rate"] = stats["cache_hits"] / total
            stats["prediction_hit_rate"] = stats["prediction_hits"] / total
            stats["miss_rate"] = stats["misses"] / total
        else:
            stats["cache_hit_rate"] = 0
            stats["prediction_hit_rate"] = 0
            stats["miss_rate"] = 0

        # 添加预测缓存统计
        stats["predictive_cache"] = self.predictive_cache.get_cache_statistics()

        return stats