import uuid
from models.state import AgentState
from utils.logger import logger


def ingest_input(state: AgentState) -> AgentState:
    """
    职责：接收来自浏览器插件或上层网关的输入，做最小的校验和标准化。

    约束：只能写：feishu_urls, user_intent, trace_id
    """
    trace_id = state.get("trace_id", f"req-{uuid.uuid4()}")
    step_name = "ingest_input"

    logger.start(trace_id, step_name, "开始接收并标准化用户输入")

    # 提取并标准化输入
    feishu_urls = state.get("feishu_urls", [])
    user_intent = state.get("user_intent", "generate_crud")  # 默认值

    # 处理单个URL的兼容性
    if "feishu_url" in state:
        single_url = state.get("feishu_url", "")
        if single_url:
            feishu_urls = [single_url]

    # 基本校验
    if not feishu_urls:
        logger.error(trace_id, step_name, "缺少必需的 feishu_urls 参数")
        raise ValueError("feishu_urls is required")

    # 验证每个URL
    valid_urls = []
    for i, url in enumerate(feishu_urls):
        if not url.startswith(("http://", "https://")):
            logger.error(trace_id, step_name, f"feishu_url[{i}] 格式无效: {url}")
            raise ValueError(f"feishu_url[{i}] must be a valid URL")
        valid_urls.append(url)

    # 写入 state - 只写允许的字段
    result_state = state.copy()
    result_state["feishu_urls"] = valid_urls
    result_state["user_intent"] = user_intent
    result_state["trace_id"] = trace_id

    logger.end(trace_id, step_name, "输入标准化完成",
              extra={
                  "feishu_urls_count": len(valid_urls),
                  "feishu_urls": valid_urls,
                  "user_intent": user_intent
              })

    return result_state