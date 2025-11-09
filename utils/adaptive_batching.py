#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自适应批处理大小优化器
根据实时性能指标动态调整批处理策略
"""

import time
import threading
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict
from collections import deque
import psutil
from utils.logger import logger


@dataclass
class PerformanceMetrics:
    """性能指标"""
    processing_time: float
    throughput: float  # 接口/秒
    success_rate: float
    cpu_usage: float
    memory_usage: float
    cache_hit_rate: float
    error_rate: float
    timestamp: float


@dataclass
class BatchConfig:
    """批处理配置"""
    chunk_size: int
    max_workers: int
    timeout_seconds: int
    retry_attempts: int
    adaptive_mode: str  # "aggressive", "balanced", "conservative"


class AdaptiveBatchingOptimizer:
    """自适应批处理优化器"""

    def __init__(self, initial_config: Optional[BatchConfig] = None):
        self.current_config = initial_config or BatchConfig(
            chunk_size=2,
            max_workers=5,
            timeout_seconds=60,
            retry_attempts=3,
            adaptive_mode="balanced"
        )

        # 性能历史记录
        self.performance_history: deque = deque(maxlen=100)
        self.config_history: deque = deque(maxlen=50)

        # 实时监控
        self.monitoring_enabled = True
        self.monitoring_thread = None
        self.system_metrics = {}
        self.last_optimization_time = 0

        # 优化参数
        self.optimization_interval = 60  # 秒
        self.min_chunk_size = 1
        self.max_chunk_size = 5
        self.min_workers = 1
        self.max_workers = 10

        # 启动监控线程
        self._start_monitoring()

    def _start_monitoring(self):
        """启动系统监控"""
        if self.monitoring_thread is None or not self.monitoring_thread.is_alive():
            self.monitoring_thread = threading.Thread(target=self._monitor_system, daemon=True)
            self.monitoring_thread.start()

    def _monitor_system(self):
        """监控系统资源"""
        while self.monitoring_enabled:
            try:
                # CPU使用率
                cpu_percent = psutil.cpu_percent(interval=1)

                # 内存使用率
                memory = psutil.virtual_memory()
                memory_percent = memory.percent

                # 可用内存
                available_memory_gb = memory.available / (1024**3)

                self.system_metrics = {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent,
                    "available_memory_gb": available_memory_gb,
                    "timestamp": time.time()
                }

            except Exception as e:
                logger.warning("adaptive_batching", "monitoring_error", f"监控错误: {str(e)}")

            time.sleep(5)  # 每5秒更新一次

    def record_performance(self, metrics: PerformanceMetrics):
        """记录性能指标"""
        self.performance_history.append(metrics)

        # 定期优化配置
        current_time = time.time()
        if current_time - self.last_optimization_time > self.optimization_interval:
            self._optimize_config()
            self.last_optimization_time = current_time

    def _optimize_config(self):
        """优化配置"""
        if len(self.performance_history) < 5:
            return  # 数据不足，不优化

        # 获取最近的性能数据
        recent_metrics = list(self.performance_history)[-10:]

        # 计算平均指标
        avg_processing_time = sum(m.processing_time for m in recent_metrics) / len(recent_metrics)
        avg_throughput = sum(m.throughput for m in recent_metrics) / len(recent_metrics)
        avg_success_rate = sum(m.success_rate for m in recent_metrics) / len(recent_metrics)
        avg_cache_hit_rate = sum(m.cache_hit_rate for m in recent_metrics) / len(recent_metrics)
        avg_error_rate = sum(m.error_rate for m in recent_metrics) / len(recent_metrics)

        # 获取系统负载
        system_load = self.system_metrics
        cpu_usage = system_load.get("cpu_percent", 50)
        memory_usage = system_load.get("memory_percent", 50)

        # 计算优化分数
        optimization_score = self._calculate_optimization_score(
            avg_processing_time, avg_throughput, avg_success_rate,
            avg_cache_hit_rate, avg_error_rate, cpu_usage, memory_usage
        )

        # 根据分数调整配置
        new_config = self._adjust_config_by_score(optimization_score, system_load)

        # 应用新配置
        if self._should_apply_new_config(new_config):
            self.config_history.append(self.current_config)
            self.current_config = new_config

            logger.info("adaptive_batching", "config_optimized",
                       f"优化配置: chunk_size={new_config.chunk_size}, "
                       f"max_workers={new_config.max_workers}, "
                       f"优化分数: {optimization_score:.2f}")

    def _calculate_optimization_score(
        self, processing_time: float, throughput: float, success_rate: float,
        cache_hit_rate: float, error_rate: float, cpu_usage: float, memory_usage: float
    ) -> float:
        """计算优化分数"""
        score = 0

        # 处理时间（越低越好）
        if processing_time < 10:
            score += 30
        elif processing_time < 20:
            score += 20
        elif processing_time < 30:
            score += 10

        # 吞吐量（越高越好）
        if throughput > 1.0:
            score += 25
        elif throughput > 0.5:
            score += 15
        elif throughput > 0.2:
            score += 5

        # 成功率（越高越好）
        score += success_rate * 20

        # 缓存命中率（越高越好）
        score += cache_hit_rate * 15

        # 错误率（越低越好）
        score += (1.0 - error_rate) * 10

        # 系统负载（越低越好）
        load_penalty = (cpu_usage + memory_usage) / 200  # 0-1之间
        score -= load_penalty * 10

        return max(0, min(100, score))

    def _adjust_config_by_score(self, score: float, system_metrics: Dict) -> BatchConfig:
        """根据分数和系统负载调整配置"""
        new_config = BatchConfig(**asdict(self.current_config))

        if score > 80:  # 优秀性能，可以更激进
            new_config.adaptive_mode = "aggressive"
            new_config.chunk_size = min(self.max_chunk_size, new_config.chunk_size + 1)
            new_config.max_workers = min(self.max_workers, new_config.max_workers + 2)
            new_config.timeout_seconds = max(30, new_config.timeout_seconds - 10)

        elif score > 60:  # 良好性能，保持平衡
            new_config.adaptive_mode = "balanced"
            # 微调参数
            if new_config.chunk_size < self.max_chunk_size and system_metrics["cpu_percent"] < 70:
                new_config.chunk_size += 1

        elif score > 40:  # 一般性能，需要优化
            new_config.adaptive_mode = "conservative"
            # 减少并发
            new_config.max_workers = max(self.min_workers, new_config.max_workers - 1)
            new_config.chunk_size = max(self.min_chunk_size, new_config.chunk_size - 1)
            new_config.timeout_seconds = min(120, new_config.timeout_seconds + 15)

        else:  # 性能差，大幅调整
            new_config.adaptive_mode = "conservative"
            new_config.chunk_size = self.min_chunk_size
            new_config.max_workers = max(1, new_config.max_workers // 2)
            new_config.timeout_seconds = 120
            new_config.retry_attempts = max(1, new_config.retry_attempts - 1)

        # 根据系统资源进一步调整
        if system_metrics["cpu_percent"] > 85:
            new_config.max_workers = max(1, new_config.max_workers // 2)

        if system_metrics["memory_percent"] > 85:
            new_config.max_workers = max(1, new_config.max_workers - 1)

        if system_metrics["available_memory_gb"] < 1:
            new_config.max_workers = 1
            new_config.chunk_size = 1

        return new_config

    def _should_apply_new_config(self, new_config: BatchConfig) -> bool:
        """判断是否应该应用新配置"""
        # 检查配置是否有显著变化
        config_changed = (
            new_config.chunk_size != self.current_config.chunk_size or
            new_config.max_workers != self.current_config.max_workers or
            new_config.adaptive_mode != self.current_config.adaptive_mode
        )

        # 检查是否频繁变更
        if len(self.config_history) > 0:
            last_config = self.config_history[-1]
            recently_changed = (
                time.time() - self.config_history[-1].timestamp < 30 if
                hasattr(last_config, 'timestamp') else False
            )
        else:
            recently_changed = False

        return config_changed and not recently_changed

    def get_optimal_config(self, content_length: int, interface_count: int) -> BatchConfig:
        """获取最优配置"""
        # 基于内容特征预调整
        adjusted_config = BatchConfig(**asdict(self.current_config))

        # 根据内容长度调整
        if content_length > 5000:  # 长文档
            adjusted_config.chunk_size = max(1, adjusted_config.chunk_size - 1)
            adjusted_config.timeout_seconds = min(120, adjusted_config.timeout_seconds + 30)
        elif content_length < 1000:  # 短文档
            adjusted_config.chunk_size = min(self.max_chunk_size, adjusted_config.chunk_size + 1)

        # 根据接口数量调整
        if interface_count > 10:  # 大量接口
            adjusted_config.max_workers = min(self.max_workers, adjusted_config.max_workers + 2)
        elif interface_count < 3:  # 少量接口
            adjusted_config.max_workers = max(1, adjusted_config.max_workers - 1)

        # 根据系统实时负载调整
        if self.system_metrics.get("cpu_percent", 50) > 80:
            adjusted_config.max_workers = max(1, adjusted_config.max_workers // 2)

        return adjusted_config

    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        if not self.performance_history:
            return {"message": "暂无性能数据"}

        recent_metrics = list(self.performance_history)[-20:]

        return {
            "current_config": asdict(self.current_config),
            "performance_summary": {
                "avg_processing_time": sum(m.processing_time for m in recent_metrics) / len(recent_metrics),
                "avg_throughput": sum(m.throughput for m in recent_metrics) / len(recent_metrics),
                "avg_success_rate": sum(m.success_rate for m in recent_metrics) / len(recent_metrics),
                "avg_cache_hit_rate": sum(m.cache_hit_rate for m in recent_metrics) / len(recent_metrics),
                "avg_error_rate": sum(m.error_rate for m in recent_metrics) / len(recent_metrics)
            },
            "system_metrics": self.system_metrics,
            "optimization_history": len(self.config_history),
            "performance_samples": len(self.performance_history)
        }

    def force_optimization(self):
        """强制立即优化配置"""
        self._optimize_config()

    def reset_to_default(self):
        """重置为默认配置"""
        self.current_config = BatchConfig(
            chunk_size=2,
            max_workers=5,
            timeout_seconds=60,
            retry_attempts=3,
            adaptive_mode="balanced"
        )
        logger.info("adaptive_batching", "config_reset", "配置已重置为默认值")

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring_enabled = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)


# 全局自适应批处理优化器实例
_adaptive_optimizer = None
_optimizer_lock = threading.Lock()


def get_adaptive_optimizer() -> AdaptiveBatchingOptimizer:
    """获取全局自适应批处理优化器实例"""
    global _adaptive_optimizer
    if _adaptive_optimizer is None:
        with _optimizer_lock:
            if _adaptive_optimizer is None:
                _adaptive_optimizer = AdaptiveBatchingOptimizer()
    return _adaptive_optimizer


def record_batch_performance(
    processing_time: float, interfaces_count: int, success_count: int,
    cache_hits: int, error_count: int, trace_id: str = None
):
    """记录批处理性能"""
    optimizer = get_adaptive_optimizer()

    metrics = PerformanceMetrics(
        processing_time=processing_time,
        throughput=interfaces_count / processing_time if processing_time > 0 else 0,
        success_rate=success_count / interfaces_count if interfaces_count > 0 else 0,
        cpu_usage=optimizer.system_metrics.get("cpu_percent", 0),
        memory_usage=optimizer.system_metrics.get("memory_percent", 0),
        cache_hit_rate=cache_hits / interfaces_count if interfaces_count > 0 else 0,
        error_rate=error_count / interfaces_count if interfaces_count > 0 else 0,
        timestamp=time.time()
    )

    optimizer.record_performance(metrics)

    if trace_id:
        logger.info(trace_id, "batch_performance",
                   f"处理时间: {processing_time:.2f}s, "
                   f"吞吐量: {metrics.throughput:.2f} interfaces/s, "
                   f"成功率: {metrics.success_rate:.2f}, "
                   f"缓存命中率: {metrics.cache_hit_rate:.2f}")