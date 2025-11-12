"""
文档切分节点
将原始文档切分为逻辑块，为并行处理做准备
"""

import re
import uuid
from typing import List, Dict, Any, Tuple
from models.state import AgentState
from utils.logger import logger


def split_document(state: AgentState) -> AgentState:
    """
    文档切分节点 - 基于简单规则将文档切分为逻辑块

    约束：只能写：doc_chunks, chunk_metadata, use_chunked_processing, chunking_strategy
    """
    trace_id = state["trace_id"]
    step_name = "split_document"
    raw_docs = state["raw_docs"]
    feishu_urls = state.get("feishu_urls", [])

    logger.start(trace_id, step_name, f"切分 {len(raw_docs)} 个文档，总计 {sum(len(doc) for doc in raw_docs)} 字符")

    try:
        # 1. 配置切分策略
        chunking_strategy = {
            "method": "rule_based",
            "max_chunk_size": 2000,      # 最大块大小（字符）
            "min_chunk_size": 100,       # 最小块大小
            "split_by_headers": True,    # 按标题切分
            "split_by_paragraphs": True, # 按段落切分
            "preserve_context": True     # 保留上下文
        }

        # 2. 执行文档切分
        all_chunks = []
        chunk_metadata = {
            "total_chunks": 0,
            "total_docs": len(raw_docs),
            "chunking_strategy": chunking_strategy,
            "doc_stats": []
        }

        for doc_index, doc in enumerate(raw_docs):
            logger.info(trace_id, step_name, f"切分文档 {doc_index + 1}: {len(doc)} 字符")

            # 切分单个文档
            doc_chunks = split_single_document(doc, doc_index, chunking_strategy, trace_id, step_name)
            all_chunks.extend(doc_chunks)

            logger.info(trace_id, step_name, f"文档 {doc_index + 1} 切分完成: {len(doc_chunks)} 个块")

        # 3. 更新元数据
        chunk_metadata["total_chunks"] = len(all_chunks)
        chunk_metadata["processing_enabled"] = len(all_chunks) > 1  # 只有多个块才启用块处理

        # 4. 决定是否启用块处理模式
        use_chunked_processing = (
            len(all_chunks) > 1 and                     # 有多个块
            sum(len(doc) for doc in raw_docs) > 500     # 总长度足够长
        )

        # 5. 显示切分结果
        logger.info(trace_id, step_name, f"切分完成: {len(all_chunks)} 个块，启用块处理: {use_chunked_processing}")

        # 6. 显示每个块的内容
        for i, chunk in enumerate(all_chunks):
            chunk_preview = chunk["content"][:100] + "..." if len(chunk["content"]) > 100 else chunk["content"]
            logger.info(trace_id, step_name, f"块 {i+1} [{chunk['chunk_type']}]: {chunk_preview}")

        # 7. 写入状态 - 只写允许的字段
        result_state = state.copy()
        result_state["doc_chunks"] = all_chunks
        result_state["chunk_metadata"] = chunk_metadata
        result_state["use_chunked_processing"] = use_chunked_processing
        result_state["chunking_strategy"] = chunking_strategy

        logger.end(trace_id, step_name, f"切分节点完成: {len(all_chunks)} 个块，块处理: {use_chunked_processing}")

        return result_state

    except Exception as e:
        logger.error(trace_id, step_name, f"文档切分失败: {str(e)}",
                    extra={"error": str(e)})

        # 失败时禁用块处理，保持向后兼容
        result_state = state.copy()
        result_state["use_chunked_processing"] = False
        result_state["chunk_metadata"] = {"error": str(e)}
        result_state["chunking_strategy"] = {"failed": True}

        return result_state


def split_single_document(doc: str, doc_index: int, strategy: dict, trace_id: str, step_name: str) -> List[dict]:
    """
    切分单个文档
    """
    chunks = []
    lines = doc.split('\n')

    # 策略1：按标题切分
    if strategy.get("split_by_headers", True):
        header_chunks = split_by_headers(lines, doc_index, trace_id, step_name)
        if header_chunks:
            chunks.extend(header_chunks)

    # 如果没有标题切分结果，使用段落切分
    if not chunks and strategy.get("split_by_paragraphs", True):
        paragraph_chunks = split_by_paragraphs(lines, doc_index, strategy, trace_id, step_name)
        chunks.extend(paragraph_chunks)

    # 如果还是没有切分结果，将整个文档作为一个块
    if not chunks:
        chunks.append(create_text_chunk(
            content=doc,
            doc_index=doc_index,
            chunk_type="full_document",
            start_line=0,
            end_line=len(lines) - 1,
            position=0
        ))

    # 应用大小限制
    chunks = apply_size_limits(chunks, strategy, trace_id, step_name)

    # 添加上下文信息
    if strategy.get("preserve_context", True):
        chunks = add_context_info(chunks, lines, trace_id, step_name)

    return chunks


def split_by_headers(lines: List[str], doc_index: int, trace_id: str, step_name: str) -> List[dict]:
    """
    按Markdown标题切分文档
    """
    chunks = []
    current_chunk_lines = []
    current_header_level = 0
    chunk_start_line = 0
    current_position = 0

    for i, line in enumerate(lines):
        # 检查是否是标题行
        header_match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())

        if header_match:
            header_level = len(header_match.group(1))
            header_text = header_match.group(2)

            # 如果已经有内容，且当前标题级别小于等于之前级别，则切分
            if (current_chunk_lines and
                current_header_level > 0 and
                header_level <= current_header_level):

                # 保存当前块
                chunk_content = '\n'.join(current_chunk_lines)
                chunk = create_text_chunk(
                    content=chunk_content,
                    doc_index=doc_index,
                    chunk_type="header_section",
                    start_line=chunk_start_line,
                    end_line=i - 1,
                    position=current_position
                )
                chunks.append(chunk)

                # 重置状态
                current_chunk_lines = []
                current_position += len(chunk_content) + 1
                chunk_start_line = i

            # 添加标题行
            current_chunk_lines.append(line)
            current_header_level = header_level
        else:
            current_chunk_lines.append(line)

    # 处理最后一个块
    if current_chunk_lines:
        chunk_content = '\n'.join(current_chunk_lines)
        chunk = create_text_chunk(
            content=chunk_content,
            doc_index=doc_index,
            chunk_type="header_section",
            start_line=chunk_start_line,
            end_line=len(lines) - 1,
            position=current_position
        )
        chunks.append(chunk)

    logger.info(trace_id, step_name, f"标题切分: {len(chunks)} 个块")

    return chunks


def split_by_paragraphs(lines: List[str], doc_index: int, strategy: dict, trace_id: str, step_name: str) -> List[dict]:
    """
    按段落切分文档（基于空行分隔）
    """
    chunks = []
    current_chunk_lines = []
    chunk_start_line = 0
    current_position = 0
    max_size = strategy.get("max_chunk_size", 2000)

    for i, line in enumerate(lines):
        # 检查是否是段落边界（空行）
        if line.strip() == "":
            if current_chunk_lines:
                chunk_content = '\n'.join(current_chunk_lines)

                # 检查大小限制
                if len(chunk_content) <= max_size:
                    chunk = create_text_chunk(
                        content=chunk_content,
                        doc_index=doc_index,
                        chunk_type="paragraph",
                        start_line=chunk_start_line,
                        end_line=i - 1,
                        position=current_position
                    )
                    chunks.append(chunk)

                    current_position += len(chunk_content) + 1
                    chunk_start_line = i + 1
                    current_chunk_lines = []
                else:
                    # 块太大，进一步切分
                    sub_chunks = split_large_text(chunk_content, doc_index, chunk_start_line, current_position, strategy)
                    chunks.extend(sub_chunks)

                    current_position += len(chunk_content) + 1
                    chunk_start_line = i + 1
                    current_chunk_lines = []
        else:
            current_chunk_lines.append(line)

    # 处理最后一个块
    if current_chunk_lines:
        chunk_content = '\n'.join(current_chunk_lines)
        if len(chunk_content) <= max_size:
            chunk = create_text_chunk(
                content=chunk_content,
                doc_index=doc_index,
                chunk_type="paragraph",
                start_line=chunk_start_line,
                end_line=len(lines) - 1,
                position=current_position
            )
            chunks.append(chunk)
        else:
            sub_chunks = split_large_text(chunk_content, doc_index, chunk_start_line, current_position, strategy)
            chunks.extend(sub_chunks)

    logger.info(trace_id, step_name, f"段落切分: {len(chunks)} 个块")

    return chunks


def split_large_text(text: str, doc_index: int, start_line: int, position: int, strategy: dict) -> List[dict]:
    """
    将大文本按句子切分为多个块
    """
    max_size = strategy.get("max_chunk_size", 2000)
    min_size = strategy.get("min_chunk_size", 100)

    # 按句子切分
    sentences = re.split(r'([.!?。！？]+\s*)', text)

    chunks = []
    current_chunk = ""
    current_line_offset = 0

    for i in range(0, len(sentences), 2):
        if i + 1 < len(sentences):
            sentence = sentences[i] + sentences[i + 1]
        else:
            sentence = sentences[i]

        # 如果当前块加上新句子超过限制，且当前块大小符合最小要求，则切分
        if (len(current_chunk) + len(sentence) > max_size and
            len(current_chunk) >= min_size):

            chunk = create_text_chunk(
                content=current_chunk.strip(),
                doc_index=doc_index,
                chunk_type="large_text_split",
                start_line=start_line + current_line_offset,
                end_line=start_line + current_line_offset,
                position=position
            )
            chunks.append(chunk)

            position += len(current_chunk)
            current_chunk = sentence
            current_line_offset = 0
        else:
            current_chunk += sentence
            current_line_offset += sentence.count('\n')

    # 处理最后一个块
    if current_chunk.strip():
        chunk = create_text_chunk(
            content=current_chunk.strip(),
            doc_index=doc_index,
            chunk_type="large_text_split",
            start_line=start_line + current_line_offset,
            end_line=start_line + current_line_offset,
            position=position
        )
        chunks.append(chunk)

    return chunks


def create_text_chunk(content: str, doc_index: int, chunk_type: str, start_line: int, end_line: int, position: int) -> dict:
    """
    创建文档块对象
    """
    return {
        # 基础信息
        "chunk_id": f"chunk_{doc_index}_{uuid.uuid4().hex[:8]}",
        "source_doc_index": doc_index,
        "chunk_type": chunk_type,
        "content": content,
        "position": position,
        "line_start": start_line,
        "line_end": end_line,

        # 上下文信息（稍后填充）
        "prev_chunk_id": None,
        "next_chunk_id": None,
        "context_before": "",
        "context_after": "",

        # 元数据
        "metadata": {
            "word_count": len(content.split()),
            "char_count": len(content),
            "line_count": content.count('\n') + 1,
            "has_grid": "```grid" in content,
            "has_code": "```" in content and "```grid" not in content,
            "importance_score": _calculate_importance_score(content, chunk_type),
            "processing_priority": _get_processing_priority(content, chunk_type)
        }
    }


def _calculate_importance_score(content: str, chunk_type: str) -> float:
    """
    计算块的重要性评分
    """
    score = 0.5  # 基础分数

    # 根据块类型调整
    if chunk_type == "header_section":
        score += 0.3
    elif chunk_type == "full_document":
        score += 0.2

    # 根据内容特征调整
    if "```grid" in content:
        score += 0.3  # 包含grid块很重要

    # 根据长度调整（适中的长度更重要）
    char_count = len(content)
    if 100 <= char_count <= 1000:
        score += 0.1
    elif char_count > 2000:
        score -= 0.1  # 太长可能不够聚焦

    return min(1.0, max(0.0, score))


def _get_processing_priority(content: str, chunk_type: str) -> int:
    """
    获取处理优先级（数字越小优先级越高）
    """
    if "```grid" in content:
        return 1  # 最高优先级
    elif chunk_type == "header_section":
        return 2
    elif chunk_type == "full_document":
        return 3
    else:
        return 4


def _get_chunk_type_distribution(chunks: List[dict]) -> dict:
    """
    获取块类型分布统计
    """
    distribution = {}
    for chunk in chunks:
        chunk_type = chunk["chunk_type"]
        distribution[chunk_type] = distribution.get(chunk_type, 0) + 1
    return distribution


def apply_size_limits(chunks: List[dict], strategy: dict, trace_id: str, step_name: str) -> List[dict]:
    """
    应用大小限制，对过大的块进行进一步切分
    """
    max_size = strategy.get("max_chunk_size", 2000)
    min_size = strategy.get("min_chunk_size", 100)

    result_chunks = []

    for chunk in chunks:
        content = chunk["content"]

        if len(content) > max_size:
            # 切分大块
            sub_chunks = split_large_text(
                content,
                chunk["source_doc_index"],
                chunk["line_start"],
                chunk["position"],
                strategy
            )
            result_chunks.extend(sub_chunks)
        elif len(content) < min_size and result_chunks:
            # 合并小块
            last_chunk = result_chunks[-1]
            if (len(last_chunk["content"]) + len(content) <= max_size and
                last_chunk["source_doc_index"] == chunk["source_doc_index"]):

                # 合并到最后一个块
                merged_content = last_chunk["content"] + "\n\n" + content
                last_chunk["content"] = merged_content
                last_chunk["line_end"] = chunk["line_end"]
                last_chunk["metadata"]["char_count"] = len(merged_content)
                last_chunk["metadata"]["word_count"] = len(merged_content.split())
                continue

        result_chunks.append(chunk)

    # 大小限制应用完成，移除详细日志

    return result_chunks


def add_context_info(chunks: List[dict], original_lines: List[str], trace_id: str, step_name: str) -> List[dict]:
    """
    为块添加上下文信息
    """
    for i, chunk in enumerate(chunks):
        # 设置前后块关系
        if i > 0:
            chunk["prev_chunk_id"] = chunks[i-1]["chunk_id"]
            # 添加前文摘要
            prev_content = chunks[i-1]["content"]
            chunk["context_before"] = prev_content[:200] + "..." if len(prev_content) > 200 else prev_content

        if i < len(chunks) - 1:
            chunk["next_chunk_id"] = chunks[i+1]["chunk_id"]
            # 添加后文摘要
            next_content = chunks[i+1]["content"]
            chunk["context_after"] = next_content[:200] + "..." if len(next_content) > 200 else next_content

    # 上下文信息添加完成，移除详细日志

    return chunks