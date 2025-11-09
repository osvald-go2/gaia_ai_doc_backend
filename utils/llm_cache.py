#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM结果缓存系统
通过缓存相似的接口解析结果，避免重复LLM调用，提升性能
"""

import hashlib
import json
import time
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from utils.logger import logger


@dataclass
class CacheEntry:
    """缓存条目"""
    content_hash: str
    interface_result: Dict[str, Any]
    timestamp: float
    hit_count: int
    content_preview: str  # 原始内容预览，用于调试

    def is_expired(self, ttl_seconds: int = 3600) -> bool:
        """检查缓存是否过期"""
        return time.time() - self.timestamp > ttl_seconds


class LLMCache:
    """LLM结果缓存管理器"""

    def __init__(self, cache_dir: str = "./cache", ttl_seconds: int = 3600):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.memory_cache: Dict[str, CacheEntry] = {}

        # 确保缓存目录存在
        os.makedirs(cache_dir, exist_ok=True)

        # 加载现有缓存
        self._load_cache()

    def _get_cache_file_path(self) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, "llm_cache.json")

    def _generate_content_hash(self, content: str) -> str:
        """生成内容哈希"""
        # 清理内容：移除空格、换行等，只保留关键信息
        cleaned_content = content.strip()
        # 移除图片引用等不重要的部分
        lines = cleaned_content.split('\n')
        important_lines = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('![') and not line.startswith('```'):
                important_lines.append(line)

        normalized_content = '\n'.join(important_lines)
        return hashlib.md5(normalized_content.encode('utf-8')).hexdigest()

    def _extract_content_signature(self, content: str) -> Dict[str, Any]:
        """提取内容特征签名"""
        # 提取关键信息作为相似性判断的依据
        signature = {
            "field_patterns": [],  # 字段模式
            "interface_type": "",  # 接口类型线索
            "dimensions_count": 0,  # 维度数量
            "metrics_count": 0,    # 指标数量
        }

        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if ':' in line and not line.startswith('#'):
                # 提取字段模式
                if 'ID' in line or 'id' in line:
                    signature["field_patterns"].append("id_field")
                elif '时间' in line or 'time' in line.lower():
                    signature["field_patterns"].append("time_field")
                elif '数量' in line or 'count' in line.lower():
                    signature["field_patterns"].append("count_field")
                elif '金额' in line or 'amount' in line.lower():
                    signature["field_patterns"].append("amount_field")

                # 统计维度和指标
                if '维度' in line or 'dimension' in line.lower():
                    signature["dimensions_count"] += 1
                elif '指标' in line or 'metric' in line.lower():
                    signature["metrics_count"] += 1

            # 识别接口类型线索
            if '筛选' in line or 'filter' in line.lower():
                signature["interface_type"] = "filter_dimension"
            elif '导出' in line or 'export' in line.lower():
                signature["interface_type"] = "export_report"
            elif '统计' in line or 'analytics' in line.lower():
                signature["interface_type"] = "analytics_metric"
            elif '展示' in line or 'display' in line.lower():
                signature["interface_type"] = "data_display"

        return signature

    def _find_similar_cache(self, content: str) -> Optional[str]:
        """查找相似的缓存条目"""
        current_signature = self._extract_content_signature(content)

        for hash_key, entry in self.memory_cache.items():
            if entry.is_expired(self.ttl_seconds):
                continue

            cached_signature = self._extract_content_signature(entry.content_preview)

            # 计算相似度
            similarity_score = self._calculate_similarity(current_signature, cached_signature)

            # 如果相似度超过阈值，认为可以使用缓存
            if similarity_score > 0.8:
                logger.info("cache_manager", "similar_cache_found", f"找到相似缓存条目，相似度: {similarity_score:.2f}")
                return hash_key

        return None

    def _calculate_similarity(self, sig1: Dict[str, Any], sig2: Dict[str, Any]) -> float:
        """计算两个签名的相似度"""
        score = 0.0
        total_weight = 0.0

        # 字段模式相似度 (权重: 0.4)
        if sig1["field_patterns"] and sig2["field_patterns"]:
            common_patterns = set(sig1["field_patterns"]) & set(sig2["field_patterns"])
            total_patterns = set(sig1["field_patterns"]) | set(sig2["field_patterns"])
            if total_patterns:
                score += 0.4 * (len(common_patterns) / len(total_patterns))
                total_weight += 0.4

        # 接口类型相似度 (权重: 0.4)
        if sig1["interface_type"] and sig2["interface_type"]:
            if sig1["interface_type"] == sig2["interface_type"]:
                score += 0.4
            total_weight += 0.4

        # 维度数量相似度 (权重: 0.1)
        if sig1["dimensions_count"] > 0 and sig2["dimensions_count"] > 0:
            dim_diff = abs(sig1["dimensions_count"] - sig2["dimensions_count"])
            max_dim = max(sig1["dimensions_count"], sig2["dimensions_count"])
            if max_dim > 0:
                score += 0.1 * (1 - dim_diff / max_dim)
                total_weight += 0.1

        # 指标数量相似度 (权重: 0.1)
        if sig1["metrics_count"] > 0 and sig2["metrics_count"] > 0:
            metric_diff = abs(sig1["metrics_count"] - sig2["metrics_count"])
            max_metric = max(sig1["metrics_count"], sig2["metrics_count"])
            if max_metric > 0:
                score += 0.1 * (1 - metric_diff / max_metric)
                total_weight += 0.1

        return score / total_weight if total_weight > 0 else 0.0

    def get(self, content: str) -> Optional[Dict[str, Any]]:
        """获取缓存结果"""
        # 1. 尝试精确匹配
        content_hash = self._generate_content_hash(content)
        if content_hash in self.memory_cache:
            entry = self.memory_cache[content_hash]
            if not entry.is_expired(self.ttl_seconds):
                entry.hit_count += 1
                logger.info("cache_manager", "cache_hit_exact", f"缓存命中 (精确): {content_hash[:8]}...")
                return entry.interface_result
            else:
                # 删除过期缓存
                del self.memory_cache[content_hash]

        # 2. 尝试相似匹配
        similar_hash = self._find_similar_cache(content)
        if similar_hash:
            entry = self.memory_cache[similar_hash]
            entry.hit_count += 1
            logger.info("cache_manager", "cache_hit_similar", f"缓存命中 (相似): {similar_hash[:8]}...")

            # 为新的内容也创建缓存条目
            self.put(content, entry.interface_result)

            return entry.interface_result

        return None

    def put(self, content: str, result: Dict[str, Any]) -> None:
        """存储缓存结果"""
        content_hash = self._generate_content_hash(content)
        content_preview = content[:200] + "..." if len(content) > 200 else content

        entry = CacheEntry(
            content_hash=content_hash,
            interface_result=result,
            timestamp=time.time(),
            hit_count=1,
            content_preview=content_preview
        )

        self.memory_cache[content_hash] = entry

        # 定期保存到文件
        if len(self.memory_cache) % 10 == 0:
            self._save_cache()

    def _load_cache(self) -> None:
        """从文件加载缓存"""
        cache_file = self._get_cache_file_path()
        if not os.path.exists(cache_file):
            return

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            loaded_count = 0
            for entry_data in data.get('entries', []):
                try:
                    entry = CacheEntry(**entry_data)
                    if not entry.is_expired(self.ttl_seconds):
                        self.memory_cache[entry.content_hash] = entry
                        loaded_count += 1
                except Exception as e:
                    logger.warning("cache_manager", "load_entry_failed", f"加载缓存条目失败: {str(e)}")

            logger.info("cache_manager", "cache_loaded", f"从文件加载了 {loaded_count} 个有效缓存条目")

        except Exception as e:
            logger.warning("cache_manager", "load_file_failed", f"加载缓存文件失败: {str(e)}")

    def _save_cache(self) -> None:
        """保存缓存到文件"""
        try:
            cache_file = self._get_cache_file_path()
            entries_data = [asdict(entry) for entry in self.memory_cache.values()]

            data = {
                'version': '1.0',
                'created_at': time.time(),
                'entries': entries_data
            }

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.warning("cache_manager", "save_file_failed", f"保存缓存文件失败: {str(e)}")

    def clear(self) -> None:
        """清空缓存"""
        self.memory_cache.clear()
        cache_file = self._get_cache_file_path()
        if os.path.exists(cache_file):
            os.remove(cache_file)
        logger.info("cache_manager", "cache_cleared", "缓存已清空")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_entries = len(self.memory_cache)
        expired_entries = sum(1 for entry in self.memory_cache.values()
                            if entry.is_expired(self.ttl_seconds))
        total_hits = sum(entry.hit_count for entry in self.memory_cache.values())

        return {
            "total_entries": total_entries,
            "valid_entries": total_entries - expired_entries,
            "expired_entries": expired_entries,
            "total_hits": total_hits,
            "avg_hits_per_entry": total_hits / total_entries if total_entries > 0 else 0,
            "cache_size_mb": os.path.getsize(self._get_cache_file_path()) / (1024 * 1024)
                             if os.path.exists(self._get_cache_file_path()) else 0
        }


# 全局缓存实例
_cache_instance = None


def get_llm_cache() -> LLMCache:
    """获取全局LLM缓存实例"""
    global _cache_instance
    if _cache_instance is None:
        cache_dir = os.environ.get('LLM_CACHE_DIR', './cache')
        ttl = int(os.environ.get('LLM_CACHE_TTL', '3600'))
        _cache_instance = LLMCache(cache_dir=cache_dir, ttl_seconds=ttl)
    return _cache_instance


def cache_llm_result(content: str, result_func) -> Dict[str, Any]:
    """
    带缓存的LLM调用装饰器函数

    Args:
        content: 输入内容
        result_func: 生成结果的函数

    Returns:
        LLM结果（来自缓存或新生成）
    """
    cache = get_llm_cache()

    # 尝试从缓存获取
    cached_result = cache.get(content)
    if cached_result:
        return cached_result

    # 缓存未命中，调用函数生成结果
    result = result_func()

    # 存储到缓存
    cache.put(content, result)

    return result