from config import config
from models.state import AgentState
from utils.logger import logger
from feishu_client import feishu_url_to_markdown


def fetch_feishu_doc(state: AgentState) -> AgentState:
    """
    职责：根据多个 URL 拿到多个文档内容。
    优先使用真实的飞书 API，如果环境变量未配置则使用 mock。

    约束：只能写：raw_docs
    """
    trace_id = state["trace_id"]
    step_name = "fetch_feishu_doc"
    feishu_urls = state["feishu_urls"]

    logger.start(trace_id, step_name, "开始获取多个飞书文档内容",
                extra={"urls_count": len(feishu_urls), "urls": feishu_urls})

    raw_docs = []

    # 使用配置检查是否可以使用真实API
    use_real_api = config.should_use_real_feishu_api()
    allow_mock_fallback = config.allow_mock_fallback()

    # 获取认证方式信息
    auth_method = []
    if config.FEISHU_APP_ID and config.FEISHU_APP_SECRET:
        auth_method.append("AppCredentials")

    logger.info(trace_id, step_name, f"获取模式: {'真实API' if use_real_api else 'Mock模式'}",
               extra={
                   "use_real_api": use_real_api,
                   "auth_method": auth_method,
                   "allow_mock_fallback": allow_mock_fallback,
                   "force_real_data": config.FORCE_REAL_FEISHU_DATA
               })

    if use_real_api:
        # 使用真实的飞书 API
        for i, url in enumerate(feishu_urls):
            try:
                logger.info(trace_id, step_name, f"正在获取文档 {i+1}: {url}")

                # 调用飞书 API 获取文档内容（使用实时token获取）
                result = feishu_url_to_markdown(url)

                # 提取 markdown 内容
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

                logger.info(trace_id, step_name, f"文档 {i+1} 获取成功",
                           extra={
                               "document_id": document_id,
                               "content_length": len(markdown_content),
                               "blocks_count": len(result.get("blocks", []))
                           })

            except Exception as e:
                logger.error(trace_id, step_name, f"文档 {i+1} 获取失败: {str(e)}")

                if allow_mock_fallback:
                    # 降级到 mock 内容
                    mock_doc = _generate_mock_content(url, i, state.get("user_intent", "generate_crud"))
                    raw_docs.append(mock_doc)
                    logger.warning(trace_id, step_name, f"文档 {i+1} 已降级为 Mock 内容")
                else:
                    # 不允许降级，抛出异常
                    error_msg = f"文档 {i+1} 获取失败且不允许Mock降级: {str(e)}"
                    logger.error(trace_id, step_name, error_msg)
                    raise Exception(error_msg)
    else:
        # Mock 模式
        logger.info(trace_id, step_name, "使用 Mock 模式生成文档内容")

        for i, url in enumerate(feishu_urls):
            mock_doc = _generate_mock_content(url, i, state.get("user_intent", "generate_crud"))
            raw_docs.append(mock_doc)

    # 写入 state - 只写允许的字段
    result_state = state.copy()
    result_state["raw_docs"] = raw_docs

    logger.end(trace_id, step_name, f"多个文档内容获取完成 ({'真实API' if use_real_api else 'Mock'})",
              extra={
                  "docs_count": len(raw_docs),
                  "total_length": sum(len(doc) for doc in raw_docs),
                  "use_real_api": use_real_api
              })

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