"""
文档理解模块
拆分后的模块化文档理解功能，提升可维护性和可测试性
"""

from .core import understand_doc
from .config import understand_doc_config

# 兼容性别名
def understand_doc_parallel(state):
    """文档理解节点 - 并行版本（向后兼容）"""
    return understand_doc(state)

__all__ = [
    'understand_doc',
    'understand_doc_config',
    'understand_doc_parallel'
]