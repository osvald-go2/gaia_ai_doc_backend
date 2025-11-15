#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重构后的文档理解节点 - 使用模块化架构
这个文件替代了原始的1563行understand_doc.py，使用模块化组件提升可维护性
"""

from models.state import AgentState
from utils.logger import logger

# 导入重构后的模块化组件
try:
    from .understand_doc.core import understand_doc as core_understand_doc
    from .understand_doc.config import understand_doc_config
except ImportError:
    # 如果导入失败，回退到原始实现
    logger.warning("", "understand_doc", "无法导入重构后的模块，回退到原始实现")
    from .understand_doc_original import understand_doc as original_understand_doc
    core_understand_doc = None


def understand_doc(state: AgentState) -> AgentState:
    """
    文档理解节点 - 重构版本
    使用模块化架构，提升可维护性和可测试性

    约束：只能写：ism
    """
    trace_id = state.get("trace_id", "")
    step_name = "understand_doc"

    try:
        if core_understand_doc:
            # 使用重构后的模块化实现
            logger.info(trace_id, step_name, "使用重构后的模块化文档理解实现")
            return core_understand_doc(state)
        else:
            # 回退到原始实现
            logger.info(trace_id, step_name, "使用原始文档理解实现（回退模式）")
            return original_understand_doc(state)
    except Exception as e:
        logger.error(trace_id, step_name, f"文档理解实现失败: {str(e)}")
        # 最后的兜底处理
        return _generate_emergency_fallback_ism(state, str(e))


def _generate_emergency_fallback_ism(state: AgentState, error_msg: str) -> AgentState:
    """
    紧急兜底ISM生成（当所有实现都失败时）
    """
    trace_id = state.get("trace_id", "")
    feishu_urls = state.get("feishu_urls", [])

    emergency_ism = {
        "doc_meta": {
            "title": "紧急兜底文档",
            "url": feishu_urls[0] if feishu_urls else "",
            "version": "1.0",
            "parsing_mode": "emergency_fallback",
            "error": error_msg
        },
        "interfaces": [
            {
                "id": "emergency_interface",
                "name": "紧急接口",
                "type": "emergency",
                "description": f"系统错误时生成的紧急接口: {error_msg}",
                "fields": [
                    {"name": "id", "type": "string", "required": True, "description": "主键ID"}
                ],
                "operations": ["read"]
            }
        ],
        "entities": [],
        "actions": [],
        "views": [],
        "__pending__": [f"文档理解系统发生严重错误: {error_msg}"],
        "__emergency_mode": True
    }

    result_state = state.copy()
    result_state["ism"] = emergency_ism

    logger.error(trace_id, "understand_doc", f"生成紧急兜底ISM: {error_msg}")

    return result_state


# 兼容性别名
def understand_doc_parallel(state: AgentState) -> AgentState:
    """
    文档理解节点 - 并行版本（向后兼容）
    """
    return understand_doc(state)


# 健康检查函数
def health_check() -> dict:
    """
    文档理解模块健康检查
    """
    try:
        if core_understand_doc:
            # 尝试导入重构后的模块进行健康检查
            from .understand_doc.core import health_check as core_health_check
            return core_health_check()
        else:
            return {
                "status": "degraded",
                "message": "使用原始实现，重构模块不可用",
                "original_mode": True
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# 模块信息
def get_module_info() -> dict:
    """
    获取模块信息
    """
    try:
        if core_understand_doc:
            from .understand_doc.config import understand_doc_config
            return {
                "version": "2.0.0-refactored",
                "architecture": "modular",
                "components": [
                    "config.py",
                    "grid_parser.py",
                    "interface_extractor.py",
                    "chunk_processor.py",
                    "ism_builder.py",
                    "core.py"
                ],
                "config_loaded": bool(understand_doc_config),
                "mode": "refactored"
            }
        else:
            return {
                "version": "1.0.0-original",
                "architecture": "monolithic",
                "components": ["understand_doc_original.py"],
                "mode": "original_fallback"
            }
    except Exception as e:
        return {
            "version": "unknown",
            "error": str(e)
        }