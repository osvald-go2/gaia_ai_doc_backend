import json
import os
from models.state import AgentState
from utils.logger import logger
from typing import Optional, List, Dict, Any
from deepseek_client_simple import call_deepseek_llm


# System prompt for LLM - must output JSON only
SYSTEM_PROMPT = """你是一个智能文档结构解析器，作用是把"产品设计"这部分的 Markdown 文档，转成一个接口语义模型（ISM）。

现在的文档是我方自定义的 Markdown，包含如下结构：

1. 标题使用 # / ## 标识
2. 产品设计的每一小节使用 ```grid ... ``` 表示一个功能块
3. ```grid``` 内部是两列或多列，格式为：

```grid
grid_column:
  - width_ratio: 50
    content: |
        左侧内容，通常是图片/原型/示意图
  - width_ratio: 50
    content: |
        右侧内容，通常是字段列表、维度、指标
```

你的任务是：
1. 智能解析文档中所有的功能块（```grid块）
2. 根据功能块的内容和标题，自动推断接口类型
3. 从 content: | 下面提取真实的字段信息

接口类型智能识别规则：
- **filter_dimension**: 包含筛选条件、过滤字段、查询参数的功能块
- **data_display**: 展示数据列表、明细、表格内容的功能块
- **analytics_metric**: 包含指标、统计、计算值的功能块
- **trend_analysis**: 包含时间序列、趋势图、对比分析的功能块
- **summary_dashboard**: 综合概览、汇总信息、仪表板功能块
- **export_report**: 导出、报表、下载相关的功能块
- **configuration**: 配置设置、参数管理相关的功能块
- **custom_action**: 自定义操作、特殊业务逻辑的功能块

如果无法归类到以上类型，请根据功能块的实际情况选择最合适的类型。

字段处理规则：
- 忽略图片/示意图/参考口径（包含"参考口径:"的行不要输出）
- 对每个有效字段生成结构：
  - name：保留文档里的原始名字
  - expression：把 name 翻成英文占位符（公司ID→companyId，消耗→cost，天→day，CTR→ctr等）
  - data_type：维度一般是string，指标是number，时间是date，布尔值是boolean
  - required：如果判断是关键条件（如公司ID、时间），设为true，否则false

最终只能输出 JSON，字段必须是：
- doc_meta
- interfaces （数组，每个功能块一个接口）
- __pending__ （数组，可为空）

如果文档里出现你无法判断的行，请写到 __pending__，不要编造。"""


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """
    LLM调用函数 - 使用DeepSeek模型进行文档理解

    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词

    Returns:
        LLM响应文本，应为JSON格式的ISM结构
    """
    try:
        # 调用DeepSeek模型
        response = call_deepseek_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model="deepseek-chat",
            temperature=0.1,  # 较低的温度确保输出的稳定性
            max_tokens=4000   # 足够的token生成完整ISM
        )

        print(f"DeepSeek模型调用成功 - response_length: {len(response)}")

        return response

    except Exception as e:
        print(f"DeepSeek模型调用失败: {str(e)}")
        raise


def ensure_ism_shape(ism: dict) -> dict:
    """
    确保ISM具有正确的结构，所有必需的字段都存在
    """
    ism.setdefault("doc_meta", {})
    ism.setdefault("interfaces", [])  # 新的接口数组，替换entities, views, actions
    ism.setdefault("__pending__", [])

    # 如果旧版本的字段存在但interfaces不存在，进行迁移
    if "entities" in ism or "views" in ism or "actions" in ism:
        if not ism.get("interfaces"):
            # 简单的迁移逻辑：将旧字段合并为一个通用接口
            interfaces = []
            if ism.get("entities"):
                interfaces.append({
                    "id": "legacy_entities",
                    "name": "实体",
                    "type": "mix",
                    "dimensions": ism["entities"],
                    "metrics": []
                })
            if ism.get("actions"):
                interfaces.append({
                    "id": "legacy_actions",
                    "name": "操作",
                    "type": "action_group",
                    "dimensions": [],
                    "metrics": ism["actions"]
                })
            ism["interfaces"] = interfaces

        # 移除旧字段
        ism.pop("entities", None)
        ism.pop("views", None)
        ism.pop("actions", None)

    return ism


def extract_block_hints(blocks: List[Dict]) -> List[str]:
    """
    从飞书blocks中提取图表/图片/表格的提示信息
    """
    hints = []
    for block in blocks or []:
        block_type = block.get("block_type")

        # 处理段落类型的块
        if block_type == 2:  # 段落
            for element in block.get("text", {}).get("elements", []):
                txt = element.get("text_run", {}).get("content", "")
                if not txt:
                    continue
                if ".png" in txt or "图" in txt or "表" in txt:
                    hints.append(txt.strip())

        # 处理图片类型的块
        elif block_type == 1:  # 图片
            image_name = block.get("image", {}).get("name", "")
            if image_name:
                hints.append(f"[{image_name}]")

        # 处理表格类型的块
        elif block_type == 3:  # 表格
            table_name = block.get("table", {}).get("name", "")
            if table_name:
                hints.append(f"[{table_name}]")
            else:
                hints.append("[表格]")

    return hints


def understand_doc(state: AgentState) -> AgentState:
    """
    职责：把飞书文档内容转换成固定结构的ISM（中间语义模型）

    约束：只能写：ism
    """
    trace_id = state["trace_id"]
    step_name = "understand_doc"

    # 获取输入数据
    raw_docs = state["raw_docs"]  # 必需：从飞书转换来的markdown文本列表
    feishu_urls = state.get("feishu_urls", [])  # 可选：原始URL列表
    feishu_blocks = state.get("feishu_blocks", [])  # 可选：原始blocks
    templates = state.get("templates", [])  # 可选：RAG检索到的规范

    logger.start(trace_id, step_name, "开始解析多个文档内容，生成合并的ISM",
                extra={
                    "docs_count": len(raw_docs),
                    "total_length": sum(len(doc) for doc in raw_docs),
                    "has_feishu_blocks": len(feishu_blocks) > 0,
                    "has_templates": len(templates) > 0
                })

    try:
        # 1. 合并多个文档内容
        combined_content = ""
        for i, doc in enumerate(raw_docs):
            combined_content += f"\n\n=== 文档 {i+1} ===\n{doc}"

        # 提取第一个URL作为主要URL（如果有）
        primary_feishu_url = feishu_urls[0] if feishu_urls else None

        # 2. 从blocks中提取图表/图片/表格提示
        block_hints = extract_block_hints(feishu_blocks)

        # 3. 准备模板文本
        templates_text = json.dumps(templates, ensure_ascii=False, indent=2) if templates else "[]"

        # 4. 准备提示文本
        hints_text = "\n".join(f"- {h}" for h in block_hints) if block_hints else "(无图片/图表提示)"

        # 5. 构建用户prompt
        user_prompt = f"""下面是从"产品设计"中截出来的内容，请你解析其中所有的功能块，不要解析背景、需求、总结等其它部分。

重要说明：
1. 文档中可能包含多个 ```grid ... ``` 块，每个都代表一个功能块
2. 你需要识别出所有的功能块，为每个功能块生成对应的接口
3. 不要只处理第一个grid块，要处理文档中出现的所有grid块

智能接口识别指南：
请根据功能块的标题和内容，智能判断接口类型：

1. **filter_dimension** - 如果功能块包含筛选、过滤、查询条件
2. **data_display** - 如果功能块展示数据列表、表格、明细信息
3. **analytics_metric** - 如果功能块包含指标、统计、计算数值
4. **trend_analysis** - 如果功能块涉及时间序列、趋势、对比分析
5. **summary_dashboard** - 如果功能块是概览、汇总、仪表板
6. **export_report** - 如果功能块涉及导出、报表、下载
7. **configuration** - 如果功能块是配置、设置、参数管理
8. **custom_action** - 其他特殊业务逻辑功能

接口生成规则：
- id: 使用 "api_" + 英文功能名（如：api_user_list, api_data_export）
- name: 使用功能块的中文名称
- type: 根据上面指南智能选择
- dimensions/metrics: 根据字段类型自动分类（查询条件放dimensions，数值指标放metrics）

最终输出格式要求：
{{
  "doc_meta": {{
    "title": "从文档中提取的主要标题",
    "url": "{primary_feishu_url or ''}"
  }},
  "interfaces": [
    {{
      "id": "api_function_name",
      "name": "功能块名称",
      "type": "intelligent_interface_type",
      "dimensions": [ // 如果有查询条件字段
        {{ "name": "字段名", "expression": "englishName", "data_type": "string", "required": true/false }}
      ],
      "metrics": [ // 如果有数值指标字段
        {{ "name": "指标名", "expression": "englishName", "data_type": "number", "required": true/false }}
      ]
    }}
    // 继续添加其他识别出的功能块接口...
  ],
  "__pending__": []
}}

下面是要解析的内容：

{combined_content}

请按要求输出JSON：""".strip()

        logger.info(trace_id, step_name, "准备调用LLM生成ISM",
                   extra={
                       "docs_count": len(raw_docs),
                       "block_hints_count": len(block_hints),
                       "templates_count": len(templates) if isinstance(templates, list) else 1
                   })

        # 6. 调用LLM
        llm_response = call_llm(SYSTEM_PROMPT, user_prompt)

        # 7. 解析LLM响应
        try:
            ism = json.loads(llm_response)
            logger.info(trace_id, step_name, "LLM返回的JSON解析成功")
        except json.JSONDecodeError as e:
            logger.warning(trace_id, step_name, "LLM输出不是合法JSON，使用兜底逻辑",
                          extra={"error": str(e), "llm_response": llm_response[:200]})

            # 构造最小的ISM结构
            ism = {
                "doc_meta": {
                    "title": "解析失败的文档",
                    "url": primary_feishu_url or "",
                    "version": "latest"
                },
                "interfaces": [],
                "__pending__": [
                    "LLM输出不是合法JSON",
                    f"原始LLM响应: {llm_response[:500]}...",
                    f"解析错误: {str(e)}"
                ]
            }

        # 8. 确保ISM结构完整
        ism = ensure_ism_shape(ism)

        # 9. 补充元数据
        if primary_feishu_url:
            ism["doc_meta"].setdefault("url", primary_feishu_url)

        # 如果有多个URL，添加到元数据中
        if len(feishu_urls) > 1:
            ism["doc_meta"]["source_urls"] = feishu_urls
            ism["doc_meta"]["source_count"] = len(feishu_urls)

        if not ism["doc_meta"].get("title"):
            # 尝试从第一个文档中提取标题
            first_doc = raw_docs[0] if raw_docs else ""
            lines = first_doc.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('# '):
                    ism["doc_meta"]["title"] = line[2:].strip()
                    break
            else:
                if len(raw_docs) == 1:
                    ism["doc_meta"]["title"] = "未命名文档"
                else:
                    ism["doc_meta"]["title"] = f"合并文档 ({len(raw_docs)}个)"

        # 10. 写入state
        result_state = state.copy()
        result_state["ism"] = ism

        logger.end(trace_id, step_name, "ISM生成完成",
                  extra={
                      "interfaces_count": len(ism.get("interfaces", [])),
                      "pending_count": len(ism["__pending__"]),
                      "doc_title": ism["doc_meta"].get("title", "未知"),
                      "processed_docs": len(raw_docs)
                  })

        return result_state

    except Exception as e:
        logger.error(trace_id, step_name, "ISM生成过程中发生错误", extra={"error": str(e)})

        # 构造错误兜底ISM
        fallback_ism = {
            "doc_meta": {
                "title": "处理出错的文档",
                "url": feishu_urls[0] if feishu_urls else "",
                "version": "latest"
            },
            "interfaces": [],
            "__pending__": [
                f"处理过程中发生错误: {str(e)}",
                "需要人工检查和补全"
            ]
        }

        result_state = state.copy()
        result_state["ism"] = fallback_ism

        logger.end(trace_id, step_name, "ISM生成完成（错误兜底）",
                  extra={
                      "interfaces_count": 0,
                      "pending_count": len(fallback_ism["__pending__"])
                  })

        return result_state