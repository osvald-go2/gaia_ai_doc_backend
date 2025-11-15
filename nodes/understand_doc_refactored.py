#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重构后的文档理解节点 - 使用模块化架构
这个文件是原始understand_doc.py的重构版本，使用模块化组件提升可维护性
"""

from models.state import AgentState
from utils.logger import logger
from .understand_doc import understand_doc


def understand_doc(state: AgentState) -> AgentState:
    """
    文档理解节点 - 重构版本
    使用模块化架构，提升可维护性和可测试性

    约束：只能写：ism
    """
    return understand_doc(state)