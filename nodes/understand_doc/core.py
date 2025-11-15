"""
文档理解核心模块
重构后的主入口，协调各个组件完成文档理解任务
"""

from typing import Dict, Any, Optional

from models.state import AgentState
from utils.logger import logger
from .config import understand_doc_config
from .chunk_processor import ChunkProcessor
from .ism_builder import ISMBuilder
from .grid_parser import GridParser


def understand_doc(state: AgentState) -> AgentState:
    """
    并行LLM文档理解节点
    支持基于文档块的并行处理和传统的文档处理模式

    约束：只能写：ism
    """
    trace_id = state["trace_id"]
    step_name = "understand_doc"

    # 检查处理模式
    use_chunked = state.get("use_chunked_processing", False)
    doc_chunks = state.get("doc_chunks", [])
    raw_docs = state["raw_docs"]
    feishu_urls = state.get("feishu_urls", [])

    mode = "块处理" if use_chunked and doc_chunks else "传统文档"
    logger.start(trace_id, step_name, f"文档理解 - {mode}模式")

    try:
        # 创建处理器
        chunk_processor = ChunkProcessor(trace_id, step_name)
        ism_builder = ISMBuilder(trace_id, step_name)

        if use_chunked and doc_chunks:
            # 新的块处理模式
            return _process_with_chunks(state, chunk_processor, ism_builder, trace_id, step_name)
        else:
            # 传统文档处理模式（向后兼容）
            return _process_with_raw_docs(state, chunk_processor, ism_builder, trace_id, step_name)

    except Exception as e:
        logger.error(trace_id, step_name, f"文档理解失败: {str(e)}")
        # 生成兜底的ISM
        return _generate_fallback_ism(state, str(e), trace_id, step_name)


def _process_with_chunks(state: AgentState, chunk_processor: ChunkProcessor,
                        ism_builder: ISMBuilder, trace_id: str, step_name: str) -> AgentState:
    """
    基于文档块的并行处理模式
    """
    doc_chunks = state["doc_chunks"]
    feishu_urls = state.get("feishu_urls", [])
    chunk_metadata = state.get("chunk_metadata", {})

    logger.info(trace_id, step_name, f"块处理模式: {len(doc_chunks)} 个块")

    try:
        # 1. 处理文档块
        interface_results = chunk_processor.process_with_chunks(doc_chunks, chunk_metadata)

        # 2. 构建文档元数据
        title = ism_builder.extract_title_from_chunks(doc_chunks)
        doc_meta = ism_builder.build_doc_meta(
            feishu_urls=feishu_urls,
            chunks=doc_chunks,
            chunk_metadata=chunk_metadata,
            parsing_mode=understand_doc_config.PARSING_MODE_CHUNKED,
            title=title
        )

        # 3. 构建ISM
        final_ism = ism_builder.build_ism_from_chunk_results(interface_results, doc_meta, doc_chunks)

        # 验证ISM结构
        is_valid, errors = ism_builder.validate_ism_structure(final_ism)
        if not is_valid:
            logger.warning(trace_id, step_name, f"ISM结构验证失败: {errors}")
            final_ism["__validation_errors"] = errors

        # 优化ISM结构
        final_ism = ism_builder.optimize_ism_structure(final_ism)

        result_state = state.copy()
        result_state["ism"] = final_ism

        logger.end(trace_id, step_name, f"块处理完成: {len(interface_results)} 个接口，{len(doc_chunks)} 个块")

        return result_state

    except Exception as e:
        logger.error(trace_id, step_name, f"块处理失败: {str(e)}")
        return _generate_fallback_ism(state, f"块处理失败: {str(e)}", trace_id, step_name)


def _process_with_raw_docs(state: AgentState, chunk_processor: ChunkProcessor,
                          ism_builder: ISMBuilder, trace_id: str, step_name: str) -> AgentState:
    """
    传统文档处理模式（保持原有逻辑）
    """
    raw_docs = state["raw_docs"]
    feishu_urls = state.get("feishu_urls", [])

    logger.info(trace_id, step_name, f"传统模式: {len(raw_docs)} 个文档，{sum(len(doc) for doc in raw_docs)} 字符")

    try:
        # 1. 处理原始文档
        interface_results = chunk_processor.process_with_raw_docs(raw_docs, feishu_urls)

        # 2. 构建文档元数据
        doc_meta = ism_builder.build_doc_meta(
            feishu_urls=feishu_urls,
            parsing_mode=understand_doc_config.PARSING_MODE_PARALLEL
        )

        # 尝试从文档中提取标题
        if raw_docs:
            combined_content = "\n\n".join(raw_docs)
            grid_parser = GridParser(trace_id, step_name)
            grid_blocks = grid_parser.extract_grid_blocks(combined_content)

            # 如果没有grid块，使用基础ISM生成
            if not grid_blocks:
                logger.warning(trace_id, step_name, "文档中没有发现grid块，生成基础ISM")
                basic_ism = ism_builder.generate_basic_ism(state, combined_content)
                result_state = state.copy()
                result_state["ism"] = basic_ism
                return result_state

            # 尝试从文档中提取标题
            lines = combined_content.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('# '):
                    doc_meta["title"] = line[2:].strip()
                    break

        # 3. 合并接口为完整的ISM
        final_ism = ism_builder.merge_interfaces_to_ism(interface_results, doc_meta)

        # 验证ISM结构
        is_valid, errors = ism_builder.validate_ism_structure(final_ism)
        if not is_valid:
            logger.warning(trace_id, step_name, f"ISM结构验证失败: {errors}")
            final_ism["__validation_errors"] = errors

        # 优化ISM结构
        final_ism = ism_builder.optimize_ism_structure(final_ism)

        # 4. 写入state
        result_state = state.copy()
        result_state["ism"] = final_ism

        logger.end(trace_id, step_name, "并行ISM生成完成",
                  extra={
                      "interfaces_count": len(final_ism.get("interfaces", [])),
                      "pending_count": len(final_ism["__pending__"]),
                      "doc_title": final_ism["doc_meta"].get("title", "未知"),
                      "processed_docs": len(raw_docs)
                  })

        return result_state

    except Exception as e:
        logger.error(trace_id, step_name, "传统模式处理过程中发生错误", extra={"error": str(e)})

        # 构造错误兜底ISM
        fallback_ism = ism_builder.generate_fallback_ism(state, str(e))

        result_state = state.copy()
        result_state["ism"] = fallback_ism

        logger.end(trace_id, step_name, "ISM生成完成（错误兜底）",
                  extra={
                      "interfaces_count": 0,
                      "pending_count": len(fallback_ism["__pending__"])
                  })

        return result_state


def _generate_fallback_ism(state: AgentState, error_msg: str, trace_id: str, step_name: str) -> AgentState:
    """生成兜底ISM"""
    ism_builder = ISMBuilder(trace_id, step_name)
    fallback_ism = ism_builder.generate_fallback_ism(state, error_msg)

    result_state = state.copy()
    result_state["ism"] = fallback_ism

    logger.error(trace_id, step_name, f"生成兜底ISM: {error_msg}")

    return result_state


# ==================== 兼容性函数 ====================

# 保持向后兼容，原来的函数名也能工作
def understand_doc_parallel(state: AgentState) -> AgentState:
    """
    文档理解节点 - 并行处理版本（向后兼容）
    """
    return understand_doc(state)


# 高级处理函数，支持更多自定义选项
def understand_doc_advanced(state: AgentState, options: Optional[Dict[str, Any]] = None) -> AgentState:
    """
    高级文档理解节点，支持自定义处理选项

    Args:
        state: AgentState
        options: 自定义选项
            - force_chunked: bool - 强制使用块处理模式
            - custom_config: dict - 自定义配置
            - validation_level: str - 验证级别 (strict/normal/lenient)
            - optimize_level: str - 优化级别 (none/basic/aggressive)
    """
    trace_id = state["trace_id"]
    step_name = "understand_doc_advanced"

    logger.start(trace_id, step_name, "高级文档理解开始")

    # 应用自定义选项
    if options:
        if options.get("force_chunked"):
            state["use_chunked_processing"] = True

        if options.get("custom_config"):
            # 可以在这里应用自定义配置
            pass

    # 执行标准文档理解
    result_state = understand_doc(state)

    # 应用额外的后处理
    if options and options.get("validation_level") == "strict":
        ism = result_state.get("ism", {})
        if ism:
            ism_builder = ISMBuilder(trace_id, step_name)
            is_valid, errors = ism_builder.validate_ism_structure(ism)
            if not is_valid:
                logger.error(trace_id, step_name, f"严格验证失败: {errors}")
                # 可以在这里决定是否抛出异常或进行修正

    if options and options.get("optimize_level") == "aggressive":
        # 应用激进的优化
        ism = result_state.get("ism", {})
        if ism:
            ism_builder = ISMBuilder(trace_id, step_name)
            result_state["ism"] = ism_builder.optimize_ism_structure(ism)

    logger.end(trace_id, step_name, "高级文档理解完成")

    return result_state


# 批量处理函数
def understand_doc_batch(states: list, options: Optional[Dict[str, Any]] = None) -> list:
    """
    批量处理多个文档理解任务
    """
    results = []
    for state in states:
        try:
            if options:
                result = understand_doc_advanced(state, options)
            else:
                result = understand_doc(state)
            results.append(result)
        except Exception as e:
            # 生成错误结果
            error_state = state.copy()
            ism_builder = ISMBuilder(state.get("trace_id", ""), "understand_doc_batch")
            error_state["ism"] = ism_builder.generate_fallback_ism(state, str(e))
            results.append(error_state)

    return results


# 健康检查函数
def health_check() -> Dict[str, Any]:
    """
    文档理解模块健康检查
    """
    try:
        # 测试各个组件是否正常
        grid_parser = GridParser()
        interface_extractor = create_interface_extractor()
        chunk_processor = create_chunk_processor()
        ism_builder = create_ism_builder()

        # 基本功能测试
        test_content = "```grid\ngrid_column:\n  - width_ratio: 50\n    content: test\n```"
        grid_blocks = grid_parser.extract_grid_blocks(test_content)

        return {
            "status": "healthy",
            "components": {
                "grid_parser": "ok",
                "interface_extractor": "ok",
                "chunk_processor": "ok",
                "ism_builder": "ok"
            },
            "test_results": {
                "grid_blocks_found": len(grid_blocks),
                "config_loaded": bool(understand_doc_config)
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# 工厂函数
def create_interface_extractor(trace_id: str = "", step_name: str = ""):
    """创建接口提取器实例"""
    from .interface_extractor import create_interface_extractor
    return create_interface_extractor(trace_id, step_name)


def create_chunk_processor(trace_id: str = "", step_name: str = ""):
    """创建文档块处理器实例"""
    from .chunk_processor import create_chunk_processor
    return create_chunk_processor(trace_id, step_name)


def create_ism_builder(trace_id: str = "", step_name: str = ""):
    """创建ISM构建器实例"""
    from .ism_builder import create_ism_builder
    return create_ism_builder(trace_id, step_name)


def create_grid_parser(trace_id: str = "", step_name: str = ""):
    """创建Grid解析器实例"""
    from .grid_parser import create_grid_parser
    return create_grid_parser(trace_id, step_name)