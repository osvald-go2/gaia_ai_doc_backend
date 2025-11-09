#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动态批处理优化器
根据文档复杂度和系统负载动态调整并行策略
"""

import time
import psutil
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from utils.logger import logger


@dataclass
class ProcessingConfig:
    """处理配置"""
    chunk_size: int           # 每个块包含的接口数量
    max_workers: int          # 最大并发数
    timeout_seconds: int      # 超时时间
    batch_mode: str           # 批处理模式: "aggressive", "balanced", "conservative"


class SystemMonitor:
    """系统资源监控器"""

    def __init__(self):
        self.cpu_threshold = 80  # CPU使用率阈值
        self.memory_threshold = 80  # 内存使用率阈值

    def get_system_load(self) -> Dict[str, float]:
        """获取系统负载"""
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "available_memory_gb": psutil.virtual_memory().available / (1024**3)
        }

    def is_system_busy(self) -> bool:
        """判断系统是否繁忙"""
        load = self.get_system_load()
        return (load["cpu_percent"] > self.cpu_threshold or
                load["memory_percent"] > self.memory_threshold)


class DocumentComplexityAnalyzer:
    """文档复杂度分析器"""

    def analyze_complexity(self, content: str, grid_blocks: List[Tuple[str, int]]) -> Dict[str, Any]:
        """分析文档复杂度"""
        total_chars = len(content)
        total_grid_chars = sum(len(grid_content) for grid_content, _ in grid_blocks)
        avg_grid_size = total_grid_chars / len(grid_blocks) if grid_blocks else 0

        # 分析字段数量
        field_count = 0
        metric_count = 0
        dimension_count = 0

        for grid_content, _ in grid_blocks:
            lines = grid_content.split('\n')
            for line in lines:
                line = line.strip()
                if ':' in line:
                    field_count += 1
                    if any(keyword in line for keyword in ['金额', '数量', '比率', '率']):
                        metric_count += 1
                    elif any(keyword in line for keyword in ['时间', 'ID', '分类', '状态']):
                        dimension_count += 1

        complexity_score = 0
        complexity_level = "low"

        # 计算复杂度分数
        if total_chars > 3000:
            complexity_score += 2
        elif total_chars > 1500:
            complexity_score += 1

        if len(grid_blocks) > 8:
            complexity_score += 2
        elif len(grid_blocks) > 4:
            complexity_score += 1

        if avg_grid_size > 400:
            complexity_score += 1

        if field_count > 30:
            complexity_score += 2
        elif field_count > 15:
            complexity_score += 1

        # 确定复杂度级别
        if complexity_score >= 5:
            complexity_level = "high"
        elif complexity_score >= 3:
            complexity_level = "medium"
        else:
            complexity_level = "low"

        return {
            "complexity_level": complexity_level,
            "complexity_score": complexity_score,
            "total_chars": total_chars,
            "grid_blocks_count": len(grid_blocks),
            "avg_grid_size": avg_grid_size,
            "field_count": field_count,
            "metric_count": metric_count,
            "dimension_count": dimension_count
        }


class BatchOptimizer:
    """动态批处理优化器"""

    def __init__(self):
        self.system_monitor = SystemMonitor()
        self.complexity_analyzer = DocumentComplexityAnalyzer()
        self.performance_history: List[Dict[str, Any]] = []

    def optimize_config(self, content: str, grid_blocks: List[Tuple[str, int]],
                       performance_hint: str = "balanced") -> ProcessingConfig:
        """
        根据文档复杂度和系统负载优化处理配置

        Args:
            content: 文档内容
            grid_blocks: grid块列表
            performance_hint: 性能提示: "aggressive", "balanced", "conservative"

        Returns:
            优化的处理配置
        """
        # 分析文档复杂度
        complexity = self.complexity_analyzer.analyze_complexity(content, grid_blocks)
        logger.info(f"文档复杂度分析: {complexity}")

        # 获取系统负载
        system_load = self.system_monitor.get_system_load()
        system_busy = self.system_monitor.is_system_busy()
        logger.info(f"系统负载: CPU={system_load['cpu_percent']:.1f}%, 内存={system_load['memory_percent']:.1f}%")

        # 基础配置
        base_config = self._get_base_config(performance_hint)

        # 根据复杂度调整
        config = self._adjust_for_complexity(base_config, complexity)

        # 根据系统负载调整
        if system_busy:
            config = self._adjust_for_system_load(config, system_load)

        # 根据历史性能调整
        config = self._adjust_for_history(config)

        logger.info(f"优化配置: chunk_size={config.chunk_size}, max_workers={config.max_workers}, "
                   f"timeout={config.timeout_seconds}s, mode={config.batch_mode}")

        return config

    def _get_base_config(self, performance_hint: str) -> ProcessingConfig:
        """获取基础配置"""
        configs = {
            "aggressive": ProcessingConfig(
                chunk_size=1, max_workers=8, timeout_seconds=90, batch_mode="aggressive"
            ),
            "balanced": ProcessingConfig(
                chunk_size=2, max_workers=5, timeout_seconds=60, batch_mode="balanced"
            ),
            "conservative": ProcessingConfig(
                chunk_size=3, max_workers=3, timeout_seconds=45, batch_mode="conservative"
            )
        }
        return configs.get(performance_hint, configs["balanced"])

    def _adjust_for_complexity(self, config: ProcessingConfig, complexity: Dict[str, Any]) -> ProcessingConfig:
        """根据复杂度调整配置"""
        level = complexity["complexity_level"]
        grid_count = complexity["grid_blocks_count"]
        avg_size = complexity["avg_grid_size"]

        if level == "high":
            # 高复杂度：更小的块，更多并发
            config.chunk_size = max(1, config.chunk_size - 1)
            config.max_workers = min(8, config.max_workers + 2)
            config.timeout_seconds = max(90, config.timeout_seconds + 30)
        elif level == "low":
            # 低复杂度：可以适当增加块大小
            if grid_count <= 3:
                config.chunk_size = min(3, config.chunk_size + 1)
                config.max_workers = max(2, config.max_workers - 1)

        # 根据平均块大小调整超时时间
        if avg_size > 500:
            config.timeout_seconds = max(90, config.timeout_seconds + 30)

        return config

    def _adjust_for_system_load(self, config: ProcessingConfig, system_load: Dict[str, Any]) -> ProcessingConfig:
        """根据系统负载调整配置"""
        if system_load["cpu_percent"] > 80:
            # CPU繁忙：减少并发
            config.max_workers = max(1, config.max_workers // 2)
            config.batch_mode = "conservative"
        elif system_load["memory_percent"] > 80:
            # 内存繁忙：减少并发，增加超时
            config.max_workers = max(1, config.max_workers - 1)
            config.timeout_seconds += 15

        # 根据可用内存调整
        if system_load["available_memory_gb"] < 1:
            config.max_workers = 1
            config.timeout_seconds = max(120, config.timeout_seconds)

        return config

    def _adjust_for_history(self, config: ProcessingConfig) -> ProcessingConfig:
        """根据历史性能调整配置"""
        if not self.performance_history:
            return config

        # 获取最近的性能记录
        recent_history = self.performance_history[-5:]
        if len(recent_history) < 3:
            return config

        # 计算平均性能指标
        avg_success_rate = sum(h["success_rate"] for h in recent_history) / len(recent_history)
        avg_processing_time = sum(h["processing_time"] for h in recent_history) / len(recent_history)

        # 根据成功率调整
        if avg_success_rate < 0.8:
            # 成功率低：减少并发，增加超时
            config.max_workers = max(1, config.max_workers - 1)
            config.timeout_seconds += 30
            config.batch_mode = "conservative"
        elif avg_success_rate > 0.95 and avg_processing_time < 20:
            # 成功率高且速度快：可以更激进
            config.max_workers = min(8, config.max_workers + 1)
            config.batch_mode = "aggressive"

        return config

    def record_performance(self, config: ProcessingConfig, processing_time: float,
                          success_count: int, total_count: int) -> None:
        """记录性能数据"""
        performance_record = {
            "timestamp": time.time(),
            "config": {
                "chunk_size": config.chunk_size,
                "max_workers": config.max_workers,
                "timeout_seconds": config.timeout_seconds,
                "batch_mode": config.batch_mode
            },
            "processing_time": processing_time,
            "success_count": success_count,
            "total_count": total_count,
            "success_rate": success_count / total_count if total_count > 0 else 0
        }

        self.performance_history.append(performance_record)

        # 保留最近100条记录
        if len(self.performance_history) > 100:
            self.performance_history = self.performance_history[-100:]

        logger.info(f"记录性能数据: 成功率={performance_record['success_rate']:.2f}, "
                   f"处理时间={processing_time:.2f}s")

    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        if not self.performance_history:
            return {"message": "暂无性能数据"}

        recent = self.performance_history[-20:]  # 最近20条记录

        return {
            "total_records": len(self.performance_history),
            "recent_records": len(recent),
            "avg_success_rate": sum(r["success_rate"] for r in recent) / len(recent),
            "avg_processing_time": sum(r["processing_time"] for r in recent) / len(recent),
            "best_config": self._find_best_config(),
            "performance_trend": self._analyze_trend()
        }

    def _find_best_config(self) -> Dict[str, Any]:
        """找到历史最佳配置"""
        if not self.performance_history:
            return {}

        # 综合考虑成功率和处理时间
        best_record = min(self.performance_history,
                         key=lambda x: x["processing_time"] / max(x["success_rate"], 0.1))

        return best_record["config"]

    def _analyze_trend(self) -> str:
        """分析性能趋势"""
        if len(self.performance_history) < 5:
            return "数据不足"

        recent = self.performance_history[-5:]
        earlier = self.performance_history[-10:-5] if len(self.performance_history) >= 10 else []

        if not earlier:
            return "数据不足"

        recent_avg = sum(r["success_rate"] for r in recent) / len(recent)
        earlier_avg = sum(r["success_rate"] for r in earlier) / len(earlier)

        if recent_avg > earlier_avg + 0.05:
            return "性能改善"
        elif recent_avg < earlier_avg - 0.05:
            return "性能下降"
        else:
            return "性能稳定"


# 全局优化器实例
_batch_optimizer = None


def get_batch_optimizer() -> BatchOptimizer:
    """获取全局批处理优化器实例"""
    global _batch_optimizer
    if _batch_optimizer is None:
        _batch_optimizer = BatchOptimizer()
    return _batch_optimizer