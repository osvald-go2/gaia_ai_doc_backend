"""
文档理解模块的常量配置
提取自understand_doc.py的硬编码值，提升可配置性和可维护性
"""

import os
import json
from typing import List, Dict, Any


class UnderstandDocConfig:
    """文档理解配置类"""

    # ==================== 并发和性能配置 ====================
    MAX_WORKERS = int(os.getenv("UNDERSTAND_DOC_MAX_WORKERS", "3"))
    CHUNK_MAX_WORKERS = int(os.getenv("CHUNK_MAX_WORKERS", "3"))
    PARALLEL_MAX_WORKERS = int(os.getenv("PARALLEL_MAX_WORKERS", "5"))

    # 超时配置（秒）
    DEFAULT_TIMEOUT = int(os.getenv("UNDERSTAND_DOC_DEFAULT_TIMEOUT", "60"))
    CHUNK_TIMEOUT = int(os.getenv("UNDERSTAND_DOC_CHUNK_TIMEOUT", "120"))
    LLM_TIMEOUT = int(os.getenv("UNDERSTAND_DOC_LLM_TIMEOUT", "300"))

    # 批处理配置
    MAX_INTERFACES_PER_CHUNK = int(os.getenv("MAX_INTERFACES_PER_CHUNK", "3"))
    MAX_CHUNK_SIZE = int(os.getenv("MAX_CHUNK_SIZE", "2000"))

    # ==================== LLM配置 ====================
    DEFAULT_MODEL = os.getenv("UNDERSTAND_DOC_DEFAULT_MODEL", "deepseek-chat")
    DEFAULT_TEMPERATURE = float(os.getenv("UNDERSTAND_DOC_TEMPERATURE", "0.1"))

    # Token配置
    SINGLE_INTERFACE_MAX_TOKENS = int(os.getenv("SINGLE_INTERFACE_MAX_TOKENS", "2000"))
    GENERAL_UNDERSTANDING_TOKENS = int(os.getenv("GENERAL_UNDERSTANDING_TOKENS", "3000"))
    FULL_DOCUMENT_TOKENS = int(os.getenv("FULL_DOCUMENT_TOKENS", "4000"))

    # ==================== 预期接口配置 ====================
    EXPECTED_INTERFACES: List[str] = [
        "总筛选项",
        "消耗波动详情",
        "素材明细",
        "消耗趋势",
        "交易趋势"
    ]

    # 接口类型映射
    INTERFACE_TYPE_MAPPING = {
        "filter_dimension": ["筛选条件", "过滤字段", "查询参数", "总筛选项"],
        "data_display": ["数据列表", "明细", "表格内容", "素材明细"],
        "trend_analysis": ["时间序列", "趋势图", "对比分析", "消耗趋势", "交易趋势", "消耗波动详情"],
        "analytics_metric": ["指标", "统计", "计算值"],
        "export_report": ["导出", "报表", "下载"],
        "custom_action": ["自定义操作", "特殊业务逻辑"]
    }

    # ==================== 系统提示词配置 ====================
    INTERFACE_SYSTEM_PROMPT = """你是一个专业的PRD接口解析器，专注于从产品设计文档中提取可转化为接口的功能模块。

**PRD解析原则**：
你解析的是PRD文档中的功能设计部分，而不是项目背景、需求概述等非功能内容。只关注能够直接转化为API接口的功能模块。

**需要忽略的内容**：
- 项目背景、产品概述、业务目标
- 需求背景、用户故事、业务场景
- 技术架构、系统设计、数据流程图
- 测试计划、上线计划、项目里程碑
- 团队信息、联系方式、会议记录
- 任何非功能性的描述性内容

**需要重点关注的内容**：
- 具体的功能模块设计（筛选、查询、分析、导出等）
- 数据结构和字段定义
- 业务规则和约束条件
- 用户界面设计和交互逻辑
- 系统行为和业务流程

你需要解析的是Markdown格式的grid块，通常包含界面设计和字段定义：
```grid
grid_column:
  - width_ratio: 50
    content: |
        功能界面示意图/原型图
  - width_ratio: 50
    content: |
        字段列表、维度、指标定义
```

**功能识别优先级**（按重要程度排序）：
1. **筛选过滤功能** - 查询条件、过滤参数、筛选器（总筛选项等）
2. **数据分析功能** - 趋势分析、统计报表、数据展示（消耗趋势、交易趋势等）
3. **数据管理功能** - 列表展示、详情查看、数据导出（素材明细等）
4. **业务操作功能** - 创建、编辑、删除、审批等操作
5. **配置管理功能** - 系统设置、参数配置、权限管理

**接口类型识别规则**：
- **filter_dimension**: 筛选条件、过滤字段、查询参数（总筛选项、查询条件）
- **trend_analysis**: 时间序列、趋势图、对比分析（消耗趋势、交易趋势、波动分析）
- **data_display**: 数据列表、明细展示、表格内容（素材明细、数据列表）
- **analytics_metric**: 统计指标、计算字段、业务指标
- **export_report**: 数据导出、报表生成、文件下载
- **crud_operation**: 数据增删改查、业务操作处理
- **config_management**: 系统配置、参数设置、业务规则配置

**字段处理规则**：
- 识别有效的业务字段，忽略UI装饰字段
- 提取字段的数据类型和约束条件
- 识别字段间的依赖关系和业务规则
- 对每个有效字段生成标准化结构：
  - name：字段名称（保留中文原意）
  - expression：英文标识符（驼峰命名，如：totalFilter、consumptionTrend）
  - data_type：数据类型（string/number/date/boolean）
  - required：是否必填（筛选条件通常true，指标通常false）
  - description：字段说明和业务规则

**输出格式（必须是JSON）**：
{
  "id": "api_功能英文名_类型标识",
  "name": "功能中文名称",
  "type": "接口类型",
  "description": "功能描述和业务价值",
  "fields": [
    {
      "name": "字段中文名",
      "expression": "fieldEnglishName",
      "data_type": "string/number/date/boolean",
      "required": true/false,
      "description": "字段说明和约束"
    }
  ],
  "operations": ["read", "create", "update", "delete"],
  "business_value": "该功能解决的业务问题"
}

**内容过滤要求**：
- **绝对跳过**：如果grid块包含"项目背景"、"产品概述"、"团队介绍"、"技术架构"等非功能内容
- **谨慎处理**：如果grid块是纯文字描述，没有明确的字段定义或业务规则
- **优先处理**：包含字段列表、数据结构、业务规则的grid块
- **必须处理**：明确的功能设计、界面原型、数据定义

**功能区分指导**：
- **消耗趋势** vs **交易趋势**：关注不同的业务指标（广告消耗 vs 交易数据）
- **筛选条件** vs **查询参数**：前者是过滤条件，后者是查询参数
- **数据列表** vs **统计分析**：前者是数据展示，后者是数据分析
- 即使界面相似，根据业务功能和数据内容区分不同接口

**重要提醒**：
- **只解析功能设计部分**，忽略项目背景等非功能内容
- **优先识别明确的业务功能**，跳过模糊的描述性内容
- **确保每个接口对应具体的业务功能**，而不是抽象的概念
- **保持接口的独立性和完整性**，每个接口解决一个明确的业务问题

只输出JSON格式的接口定义，不要包含分析过程或其他文字说明。"""

    GENERAL_SYSTEM_PROMPT = "你是一个专业的文档理解专家，擅长从需求文档中提取业务模型和接口定义。"

    BUSINESS_ANALYST_PROMPT = "你是一个专业的业务分析师，擅长从需求文档中提取业务模型、数据结构和接口定义。"

    # ==================== 上下文提取配置 ====================
    CONTEXT_SIZE = int(os.getenv("UNDERSTAND_DOC_CONTEXT_SIZE", "15"))
    MAX_CONTEXT_LINES = int(os.getenv("MAX_CONTEXT_LINES", "3"))
    MAX_TITLE_LENGTH = int(os.getenv("MAX_TITLE_LENGTH", "50"))
    MAX_DESCRIPTION_LENGTH = int(os.getenv("MAX_DESCRIPTION_LENGTH", "150"))

    # 标题识别关键词
    TITLE_KEYWORDS = [
        '详情', '列表', '查询', '统计', '分析', '导出', '配置', '管理', '设置'
    ]

    # 内容过滤关键词
    CONTENT_STOP_KEYWORDS = [
        '```', '!', '|', '-', '*', '参考口径:'
    ]

    # ==================== Grid匹配配置 ====================
    GRID_IDENTIFIER_LINES = int(os.getenv("GRID_IDENTIFIER_LINES", "5"))
    GRID_MATCH_THRESHOLD = float(os.getenv("GRID_MATCH_THRESHOLD", "0.6"))
    GRID_CONTENT_FRAGMENTS = int(os.getenv("GRID_CONTENT_FRAGMENTS", "3"))
    GRID_FRAGMENT_MIN_LENGTH = int(os.getenv("GRID_FRAGMENT_MIN_LENGTH", "10"))

    # ==================== 降级处理配置 ====================
    FALLBACK_RETRY_COUNT = int(os.getenv("FALLBACK_RETRY_COUNT", "3"))
    FALLBACK_INTERFACE_TYPES = [
        "fallback", "unknown", "basic", "emergency"
    ]

    # 默认字段定义
    DEFAULT_FIELDS = [
        {"name": "id", "type": "string", "required": True, "description": "主键ID"}
    ]

    # 默认操作
    DEFAULT_OPERATIONS = ["read"]
    CRUD_OPERATIONS = ["create", "read", "update", "delete"]

    # ==================== 日志配置 ====================
    LOG_PREVIEW_LENGTH = int(os.getenv("LOG_PREVIEW_LENGTH", "100"))
    LOG_RESULT_PREVIEW_LENGTH = int(os.getenv("LOG_RESULT_PREVIEW_LENGTH", "300"))
    LOG_ERROR_TRUNCATE_LENGTH = int(os.getenv("LOG_ERROR_TRUNCATE_LENGTH", "100"))

    # ==================== ISM构建配置 ====================
    INTERFACE_ID_PREFIX = "interface_"
    ENTITY_ID_PREFIX = "entity_"
    CHUNK_ID_PREFIX = "chunk_"

    # ISM版本信息
    ISM_VERSION = "1.0"
    PARSING_MODE_CHUNKED = "chunked_parallel"
    PARSING_MODE_PARALLEL = "parallel"
    PARSING_MODE_BASIC = "basic_fallback"
    PARSING_MODE_ERROR = "error_fallback"

    # ==================== 文档分割配置 ====================
    DOCUMENT_SEPARATOR = "\n\n=== 文档 {} ===\n"
    CHUNK_SEPARATOR = "\n\n=== 块 {} ({}) ===\n"

    # ==================== 响应格式配置 ====================
    JSON_PARSE_ERROR_TYPES = [
        json.JSONDecodeError,
        ValueError,
        TypeError
    ]

    # 支持的接口方法
    SUPPORTED_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]

    # 支持的接口类型
    SUPPORTED_INTERFACE_TYPES = [
        "filter_dimension", "data_display", "trend_analysis",
        "analytics_metric", "export_report", "custom_action",
        "crud", "config", "analytics", "fallback", "basic", "emergency"
    ]

    @classmethod
    def get_interface_type_by_keyword(cls, content: str) -> str:
        """根据关键词推断接口类型"""
        content_lower = content.lower()

        for interface_type, keywords in cls.INTERFACE_TYPE_MAPPING.items():
            if any(keyword in content for keyword in keywords):
                return interface_type

        return "custom"

    @classmethod
    def is_valid_interface_type(cls, interface_type: str) -> bool:
        """检查接口类型是否有效"""
        return interface_type in cls.SUPPORTED_INTERFACE_TYPES

    @classmethod
    def is_valid_method(cls, method: str) -> bool:
        """检查HTTP方法是否有效"""
        return method.upper() in cls.SUPPORTED_METHODS

    @classmethod
    def get_max_tokens_by_task(cls, task_type: str) -> int:
        """根据任务类型获取最大token数"""
        token_mapping = {
            "single_interface": cls.SINGLE_INTERFACE_MAX_TOKENS,
            "general_understanding": cls.GENERAL_UNDERSTANDING_TOKENS,
            "full_document": cls.FULL_DOCUMENT_TOKENS
        }
        return token_mapping.get(task_type, cls.SINGLE_INTERFACE_MAX_TOKENS)


# 全局配置实例
understand_doc_config = UnderstandDocConfig()