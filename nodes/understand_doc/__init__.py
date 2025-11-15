"""
文档理解模块
拆分后的模块化文档理解功能，提升可维护性和可测试性
"""

from .core import understand_doc
from .config import understand_doc_config

__all__ = [
    'understand_doc',
    'understand_doc_config'
]