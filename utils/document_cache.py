#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档缓存系统
基于文档内容hash缓存完整的接口生成结果，避免重复处理相同文档
"""

import hashlib
import json
import time
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from utils.logger import logger


@dataclass
class DocumentCacheEntry:
    """文档缓存条目"""
    doc_hash: str                    # 文档内容hash
    feishu_urls: List[str]          # 原始URL列表
    user_intent: str                # 用户意图
    doc_chunks: List[dict]          # 文档分片信息
    chunk_metadata: dict            # 文档分片元数据
    ism_result: Dict[str, Any]      # ISM分析结果
    plan_result: List[dict]         # 执行计划结果
    final_flow_json: str            # 最终工作流JSON
    mcp_payloads: List[dict]        # MCP载荷
    final_response: Dict[str, Any]  # 最终响应
    timestamp: float                # 缓存时间
    hit_count: int                  # 命中次数
    doc_preview: str                # 文档预览(前200字符)
    processing_time_ms: float       # 原处理时间(毫秒)

    def is_expired(self, ttl_seconds: int = 86400) -> bool:
        """检查缓存是否过期 (默认24小时)"""
        return time.time() - self.timestamp > ttl_seconds

    def to_response_dict(self) -> Dict[str, Any]:
        """转换为响应格式"""
        return {
            "doc_chunks": self.doc_chunks,
            "chunk_metadata": self.chunk_metadata,
            "ism": self.ism_result,
            "plan": self.plan_result,
            "final_flow_json": self.final_flow_json,
            "mcp_payloads": self.mcp_payloads,
            "response": self.final_response
        }


class DocumentCache:
    """文档缓存管理器"""

    def __init__(self, cache_dir: str = "./cache", ttl_seconds: int = 86400):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.memory_cache: Dict[str, DocumentCacheEntry] = {}

        # 确保缓存目录存在
        os.makedirs(cache_dir, exist_ok=True)

        # 加载现有缓存
        self._load_cache()

    def _get_cache_file_path(self) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, "document_cache.json")

    def _generate_document_hash(self, raw_docs: List[str], user_intent: str) -> str:
        """
        生成文档内容的hash值

        Args:
            raw_docs: 文档内容列表
            user_intent: 用户意图

        Returns:
            文档hash值
        """
        # 合并所有文档内容
        combined_content = "\n---DOCUMENT_SEPARATOR---\n".join(raw_docs)

        # 添加用户意图到hash计算中
        hash_input = combined_content + f"\nINTENT:{user_intent}"

        # 标准化内容：移除不影响语义的空白字符
        normalized_lines = []
        for line in hash_input.split('\n'):
            # 移除行首尾空白，压缩连续空白
            normalized_line = ' '.join(line.strip().split())
            if normalized_line:
                normalized_lines.append(normalized_line)

        normalized_content = '\n'.join(normalized_lines)

        # 生成hash
        return hashlib.sha256(normalized_content.encode('utf-8')).hexdigest()

    def get(self, raw_docs: List[str], user_intent: str) -> Optional[DocumentCacheEntry]:
        """
        获取文档缓存

        Args:
            raw_docs: 文档内容列表
            user_intent: 用户意图

        Returns:
            缓存条目或None
        """
        doc_hash = self._generate_document_hash(raw_docs, user_intent)

        if doc_hash in self.memory_cache:
            entry = self.memory_cache[doc_hash]
            if not entry.is_expired(self.ttl_seconds):
                entry.hit_count += 1
                logger.info("doc_cache", "cache_hit",
                          f"文档缓存命中: {doc_hash[:16]}..., 命中次数: {entry.hit_count}")
                return entry
            else:
                # 删除过期缓存
                del self.memory_cache[doc_hash]
                logger.info("doc_cache", "cache_expired",
                          f"删除过期缓存: {doc_hash[:16]}...")

        logger.info("doc_cache", "cache_miss", f"文档缓存未命中: {doc_hash[:16]}...")
        return None

    def put(self,
            raw_docs: List[str],
            feishu_urls: List[str],
            user_intent: str,
            doc_chunks: List[dict],
            chunk_metadata: dict,
            ism_result: Dict[str, Any],
            plan_result: List[dict],
            final_flow_json: str,
            mcp_payloads: List[dict],
            final_response: Dict[str, Any],
            processing_time_ms: float = 0.0) -> None:
        """
        存储文档缓存

        Args:
            raw_docs: 原始文档内容列表
            feishu_urls: 飞书URL列表
            user_intent: 用户意图
            doc_chunks: 文档分片信息
            chunk_metadata: 文档分片元数据
            ism_result: ISM分析结果
            plan_result: 执行计划结果
            final_flow_json: 最终工作流JSON
            mcp_payloads: MCP载荷
            final_response: 最终响应
            processing_time_ms: 处理耗时(毫秒)
        """
        doc_hash = self._generate_document_hash(raw_docs, user_intent)
        doc_preview = raw_docs[0][:200] + "..." if raw_docs and len(raw_docs[0]) > 200 else (raw_docs[0] if raw_docs else "")

        entry = DocumentCacheEntry(
            doc_hash=doc_hash,
            feishu_urls=feishu_urls.copy(),
            user_intent=user_intent,
            doc_chunks=doc_chunks.copy() if doc_chunks else [],
            chunk_metadata=chunk_metadata.copy() if chunk_metadata else {},
            ism_result=ism_result,
            plan_result=plan_result.copy() if plan_result else [],
            final_flow_json=final_flow_json,
            mcp_payloads=mcp_payloads.copy() if mcp_payloads else [],
            final_response=final_response,
            timestamp=time.time(),
            hit_count=1,
            doc_preview=doc_preview,
            processing_time_ms=processing_time_ms
        )

        self.memory_cache[doc_hash] = entry

        # 保存到文件
        self._save_cache()

        logger.info("doc_cache", "cache_stored",
                  f"文档已缓存: {doc_hash[:16]}..., 文档数: {len(raw_docs)}, 预览: {doc_preview[:50]}...")

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
                    entry = DocumentCacheEntry(**entry_data)
                    if not entry.is_expired(self.ttl_seconds):
                        self.memory_cache[entry.doc_hash] = entry
                        loaded_count += 1
                except Exception as e:
                    logger.warning("doc_cache", "load_entry_failed",
                                 f"加载缓存条目失败: {str(e)}")

            logger.info("doc_cache", "cache_loaded",
                      f"从文件加载了 {loaded_count} 个有效文档缓存条目")

        except Exception as e:
            logger.warning("doc_cache", "load_file_failed",
                         f"加载文档缓存文件失败: {str(e)}")

    def _save_cache(self) -> None:
        """保存缓存到文件"""
        try:
            cache_file = self._get_cache_file_path()
            entries_data = [asdict(entry) for entry in self.memory_cache.values()]

            data = {
                'version': '1.0',
                'created_at': time.time(),
                'ttl_seconds': self.ttl_seconds,
                'entries': entries_data
            }

            # 临时写入，确保原子性
            temp_file = cache_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # 原子性重命名
            os.rename(temp_file, cache_file)

        except Exception as e:
            logger.warning("doc_cache", "save_file_failed",
                         f"保存文档缓存文件失败: {str(e)}")

    def clear(self) -> None:
        """清空缓存"""
        self.memory_cache.clear()
        cache_file = self._get_cache_file_path()
        if os.path.exists(cache_file):
            os.remove(cache_file)
        logger.info("doc_cache", "cache_cleared", "文档缓存已清空")

    def cleanup_expired(self) -> int:
        """清理过期缓存，返回清理的条目数"""
        expired_keys = [
            key for key, entry in self.memory_cache.items()
            if entry.is_expired(self.ttl_seconds)
        ]

        for key in expired_keys:
            del self.memory_cache[key]

        if expired_keys:
            self._save_cache()

        logger.info("doc_cache", "cleanup_completed",
                  f"清理了 {len(expired_keys)} 个过期缓存条目")

        return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_entries = len(self.memory_cache)
        expired_entries = sum(1 for entry in self.memory_cache.values()
                            if entry.is_expired(self.ttl_seconds))
        total_hits = sum(entry.hit_count for entry in self.memory_cache.values())
        total_processing_time_saved = sum(
            entry.processing_time_ms * (entry.hit_count - 1)
            for entry in self.memory_cache.values()
        ) / 1000  # 转换为秒

        cache_file_size = 0
        cache_file = self._get_cache_file_path()
        if os.path.exists(cache_file):
            cache_file_size = os.path.getsize(cache_file) / (1024 * 1024)  # MB

        return {
            "total_entries": total_entries,
            "valid_entries": total_entries - expired_entries,
            "expired_entries": expired_entries,
            "total_hits": total_hits,
            "avg_hits_per_entry": total_hits / total_entries if total_entries > 0 else 0,
            "cache_file_size_mb": cache_file_size,
            "total_processing_time_saved_seconds": total_processing_time_saved,
            "ttl_hours": self.ttl_seconds / 3600
        }

    def list_entries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """列出最近的缓存条目"""
        entries = sorted(
            self.memory_cache.values(),
            key=lambda x: x.timestamp,
            reverse=True
        )

        return [
            {
                "doc_hash": entry.doc_hash[:16] + "...",
                "feishu_urls": entry.feishu_urls,
                "user_intent": entry.user_intent,
                "doc_preview": entry.doc_preview,
                "timestamp": entry.timestamp,
                "hit_count": entry.hit_count,
                "processing_time_ms": entry.processing_time_ms,
                "expired": entry.is_expired(self.ttl_seconds)
            }
            for entry in entries[:limit]
        ]


# 全局文档缓存实例
_doc_cache_instance = None


def get_document_cache() -> DocumentCache:
    """获取全局文档缓存实例"""
    global _doc_cache_instance
    if _doc_cache_instance is None:
        cache_dir = os.environ.get('DOC_CACHE_DIR', './cache')
        ttl = int(os.environ.get('DOC_CACHE_TTL', '86400'))  # 默认24小时
        _doc_cache_instance = DocumentCache(cache_dir=cache_dir, ttl_seconds=ttl)
    return _doc_cache_instance


def try_get_document_cache(raw_docs: List[str], user_intent: str) -> Optional[DocumentCacheEntry]:
    """
    尝试获取文档缓存

    Args:
        raw_docs: 文档内容列表
        user_intent: 用户意图

    Returns:
        缓存条目或None
    """
    cache = get_document_cache()
    return cache.get(raw_docs, user_intent)


def store_document_cache(
    raw_docs: List[str],
    feishu_urls: List[str],
    user_intent: str,
    doc_chunks: List[dict],
    chunk_metadata: dict,
    ism_result: Dict[str, Any],
    plan_result: List[dict],
    final_flow_json: str,
    mcp_payloads: List[dict],
    final_response: Dict[str, Any],
    processing_time_ms: float = 0.0
) -> None:
    """
    存储文档缓存

    Args:
        raw_docs: 原始文档内容列表
        feishu_urls: 飞书URL列表
        user_intent: 用户意图
        doc_chunks: 文档分片信息
        chunk_metadata: 文档分片元数据
        ism_result: ISM分析结果
        plan_result: 执行计划结果
        final_flow_json: 最终工作流JSON
        mcp_payloads: MCP载荷
        final_response: 最终响应
        processing_time_ms: 处理耗时(毫秒)
    """
    cache = get_document_cache()
    cache.put(
        raw_docs=raw_docs,
        feishu_urls=feishu_urls,
        user_intent=user_intent,
        doc_chunks=doc_chunks,
        chunk_metadata=chunk_metadata,
        ism_result=ism_result,
        plan_result=plan_result,
        final_flow_json=final_flow_json,
        mcp_payloads=mcp_payloads,
        final_response=final_response,
        processing_time_ms=processing_time_ms
    )