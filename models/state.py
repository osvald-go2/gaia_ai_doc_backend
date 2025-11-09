from typing import TypedDict, List, Any, Optional


class AgentState(TypedDict, total=False):
    # 输入层
    feishu_urls: List[str]  # 支持多个文档URL
    user_intent: str        # 默认 generate_crud
    trace_id: str           # 入口生成，日志用

    # 文档层
    raw_docs: List[str]     # 多个文档内容

    # 语义层 - 原始
    ism_raw: dict          # understand_doc 输出的原始ISM
    # 语义层 - 规范化后
    ism: dict              # normalize_and_validate_ism 输出的规范化ISM
    # 诊断信息
    diag: dict             # 标准化和校验过程中的诊断信息

    # 计划层
    plan: List[dict]        # 基于 规范化ISM的执行计划

    # 执行/合成层
    final_flow_json: str    # 把 plan 转成一个简单 flow JSON
    mcp_payloads: List[dict] # MCP载荷数组，每个元素可直接提交给MCP

    # 输出层
    response: dict          # 最终返回