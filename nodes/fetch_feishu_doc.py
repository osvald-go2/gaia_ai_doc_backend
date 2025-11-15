from config import config
from models.state import AgentState
from utils.logger import logger
from client.feishu_client import feishu_url_to_markdown


def fetch_feishu_doc(state: AgentState) -> AgentState:
    """
    职责：根据多个 URL 拿到多个文档内容。
    优先使用真实的飞书 API，如果环境变量未配置则使用 mock。

    约束：只能写：raw_docs
    """
    trace_id = state["trace_id"]
    step_name = "fetch_feishu_doc"
    feishu_urls = state["feishu_urls"]

    logger.start(trace_id, step_name, f"获取 {len(feishu_urls)} 个文档: {feishu_urls}")

    raw_docs = []

    # 使用配置检查是否可以使用真实API
    use_real_api = config.should_use_real_feishu_api()

    if use_real_api:
        # 使用真实的飞书 API
        for i, url in enumerate(feishu_urls):
            try:
                # 调用飞书 API 获取文档内容
                result = feishu_url_to_markdown(url)
                markdown_content = result.get("markdown", "")
                document_id = result.get("document_id", "")

                # 添加文档元信息
                doc_content = (
                    f"# 飞书文档 {i+1}\n"
                    f"文档ID: {document_id}\n"
                    f"来源URL: {url}\n"
                    f"---\n"
                    f"{markdown_content}"
                )

                raw_docs.append(doc_content)
                logger.info(trace_id, step_name, f"文档 {i+1} 获取成功: {len(markdown_content)} 字符")

            except Exception as e:
                logger.error(trace_id, step_name, f"文档 {i+1} 获取失败: {str(e)}")

                # 降级到 mock 内容
                mock_doc = _generate_mock_content(url, i, state.get("user_intent", "generate_crud"))
                raw_docs.append(mock_doc)
                logger.warning(trace_id, step_name, f"文档 {i+1} 使用 Mock 内容")
    else:
        # Mock 模式
        for i, url in enumerate(feishu_urls):
            mock_doc = _generate_mock_content(url, i, state.get("user_intent", "generate_crud"))
            raw_docs.append(mock_doc)

    # 写入 state - 只写允许的字段
    result_state = state.copy()
    result_state["raw_docs"] = raw_docs

    # 显示获取的文档内容摘要
    for i, doc in enumerate(raw_docs):
        content_preview = doc[:200] + "..." if len(doc) > 200 else doc
        logger.info(trace_id, step_name, f"文档 {i+1} 内容: {content_preview}")

    logger.end(trace_id, step_name, f"获取完成: {len(raw_docs)} 个文档，总计 {sum(len(doc) for doc in raw_docs)} 字符")

    return result_state


def _generate_mock_content(url: str, index: int, user_intent: str) -> str:
    """
    生成 Mock 文档内容

    Args:
        url: 飞书文档 URL
        index: 文档索引
        user_intent: 用户意图

    Returns:
        Mock 文档内容
    """
    if user_intent == "generate_crud":
        # 为每个文档生成不同的 mock 内容
        if index == 0:
            mock_doc = (
                f"# mock feishu doc {index+1}\n"
                "需求：生成用户表(users)，字段：id(string,pk), name(string), channel(string)\n"
                "并生成对应的CRUD页面\n"
                "\n"
                "功能要求：\n"
                "- 支持用户的增删改查\n"
                "- 列表页要有分页功能\n"
                "- 支持按姓名搜索"
            )
        else:
            mock_doc = (
                f"# mock feishu doc {index+1}\n"
                "需求：生成订单表(orders)，字段：id(string,pk), user_id(string), amount(decimal), status(string)\n"
                "并生成对应的CRUD页面\n"
                "\n"
                "功能要求：\n"
                "- 支持订单的增删改查\n"
                "- 列表页要有分页和筛选功能\n"
                "- 支持按用户ID和状态搜索"
            )
    else:
        # 默认 mock 内容
        mock_doc = (
            f"# mock feishu doc {index+1}\n"
            "这是一个示例文档内容\n"
            f"文档来源: {url}\n"
            "包含一些业务需求描述"
        )

    return mock_doc