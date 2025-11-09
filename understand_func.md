# 函数设计：`understand_doc(state)`

> 目标：把上一步“飞书 Docx → Markdown”得到的文本，交给 LLM，产出一个 **固定结构的 ISM (Intermediate Semantic Model)**，供后续 `plan_from_ism` 使用。  
> 要求：输出必须是 JSON，结构稳定，有兜底，不乱造。

---

## 1. 函数签名

```python
def understand_doc(state: dict) -> dict:
    ...
```
## 2. 输入（state 中需要的字段）

`state["raw_doc"]` (必需)
- 类型：str
- 说明：上一步从飞书 blocks 转出来的 markdown-ish 文本（已经保留了标题、段落、列表、图片占位）

`state.get("feishu_blocks")` (可选)
- 类型：list[dict]
- 说明：飞书返回的原始 blocks，主要用来再提取“图表/图片/表格”提示，辅助 LLM 识别视图
`state.get("templates")` (可选)
- 类型：list | dict
- 说明：RAG 检索到的团队规范、命名规则、图表模板、MCP 示例等，传了就拼进 prompt

`state.get("feishu_url")` (可选)
- 类型：str
- 说明：可以写回到 ism.doc_meta.url，方便溯源

`state.get("trace_id")` (可选)
- 类型：str
- 说明：日志用

## 3. 输出（写回 state）

`state["ism"]` (必需)
- 类型：dict
- 说明：固定结构的 ISM (Intermediate Semantic Model)，供后续 `plan_from_ism` 使用。

固定结构如下：
```
{
  "doc_meta": {
    "title": "string",
    "url": "string",
    "version": "string"
  },
  "entities": [],
  "views": [],
  "actions": [],
  "__pending__": []
}
```
注意：这几个 key 必须都在，不允许缺字段，就算是空数组也要有

## 4. ISM 目标结构说明
```
{
  "doc_meta": {
    "title": "从文档标题或一级标题里推",
    "url": "<state.feishu_url>",
    "version": "latest"
  },
  "entities": [
    {
      "id": "ent_users",
      "name": "users",
      "label": "用户",
      "fields": [
        {"name": "id", "type": "string", "required": true, "desc": "主键"},
        {"name": "channel", "type": "string", "required": false, "desc": "投放渠道"}
      ]
    }
  ],
  "views": [
    {
      "id": "view_channel_users",
      "type": "chart",
      "title": "按渠道统计用户数",
      "data_entity": "ent_users",
      "dimension": "channel",
      "metric": "count(*)",
      "chart_type": "bar"
    }
  ],
  "actions": [
    {
      "id": "act_users_crud",
      "type": "crud",
      "target_entity": "ent_users",
      "ops": ["create", "read", "update", "delete"]
    }
  ],
  "__pending__": [
    "文档里提到 [动态表格.png]，但没有给出字段，待补充"
  ]
}
```
## 5. 实现思路（步骤）
1. 从 `state` 取数据
- 取 raw_doc（主内容）
- 取 feishu_blocks，做一次轻量抽取，把所有像 “[xxx.png]” / “图” / “表” 的文本摘出来，形成 block_hints
- 取 templates，如果没有就用 []

2. 构建 Prompt
- system_prompt：限定角色 + 限定必须输出 JSON + 限定字段名 + 限定没信息就放 __pending__
- context_prompt：把 templates 拼进去（JSON 或 yaml 形式都行）
- user_prompt：把 block_hints 和 raw_doc 拼进去，明确说“请转成 ISM JSON”

3. 调用 LLM
- 用项目里统一的 LLM 调用方法（留空给你们接网关）
- 返回是一个字符串（期望是 JSON）

4. 解析 LLM 输出
- json.loads(...) 尝试转成 dict
- 如果失败，构造一个最小的 ISM，把原始输出丢进 __pending__

5. 补全 ISM 结构
- 不管成功失败，都要跑一遍 ensure_ism_shape(...)，保证 5 个 key 都在

6. 写回 state
- state["ism"] = ism

7. 日志里打上：实体数、视图数、动作数、pending 数

## 6. Prompt 参考

system_prompt：
```
你是一个“产品文档结构化器”，负责把飞书PRD转成一个固定的JSON结构（中间语义模型，ISM）。
你必须：
1. 只能输出JSON，不能输出解释文字
2. 顶层必须有字段：doc_meta, entities, views, actions, __pending__
3. 文档中没写清楚、信息不完整、看不懂的内容，一律写到 __pending__，不要编造
4. 字段命名优先使用驼峰：startDate, endDate, createdAt, updatedAt
5. 若文档出现图片或图表占位（如：[趋势图.png]、[指标卡&趋势.png]），请推断成一个 views[*]，type=chart 或 card
```

user_prompt：
```
下面是团队给定的生成规范（可能为空）：
{{TEMPLATES}}

下面是从飞书blocks里识别到的“图表/图片/表格”提示，请一并转成 views：
{{HINTS}}

下面是PRD正文（已按段落和标题转换）：
{{RAW_DOC}}

请按要求输出JSON：
```
## 7. 代码骨架（可直接生成）
```
import json
from utils.logger import log_event

SYSTEM_PROMPT = """你是一个“产品文档结构化器”，负责把飞书PRD转成一个固定的JSON结构（中间语义模型，ISM）。
必须输出JSON，顶层字段：doc_meta, entities, views, actions, __pending__。没写清楚的放到 __pending__。字段命名用驼峰。
"""

def call_llm(system_prompt: str, user_prompt: str) -> str:
    # TODO: 替换成实际的 LLM 调用
    raise NotImplementedError

def ensure_ism_shape(ism: dict) -> dict:
    ism.setdefault("doc_meta", {})
    ism.setdefault("entities", [])
    ism.setdefault("views", [])
    ism.setdefault("actions", [])
    ism.setdefault("__pending__", [])
    return ism

def extract_block_hints(blocks):
    hints = []
    for b in blocks or []:
        if b.get("block_type") == 2:  # 段落
            for e in b.get("text", {}).get("elements", []):
                txt = e.get("text_run", {}).get("content", "")
                if not txt:
                    continue
                if ".png" in txt or "图" in txt or "表" in txt:
                    hints.append(txt.strip())
    return hints

def understand_doc(state: dict) -> dict:
    trace_id = state.get("trace_id", "unknown")
    raw_doc = state["raw_doc"]
    feishu_blocks = state.get("feishu_blocks", [])
    templates = state.get("templates", [])
    feishu_url = state.get("feishu_url")

    block_hints = extract_block_hints(feishu_blocks)
    tmpl_text = json.dumps(templates, ensure_ascii=False, indent=2) if templates else "[]"
    hints_text = "\n".join(f"- {h}" for h in block_hints) if block_hints else "(无图片/图表提示)"

    user_prompt = f"""
下面是团队的生成规范（可能为空）：
{tmpl_text}

下面是文档中出现的图表/图片/表格提示（请转成 views）：
{hints_text}

下面是PRD正文，请转成ISM JSON：
{raw_doc}
""".strip()

    log_event("info", trace_id, "understand_doc", "start", message="calling llm for ism")

    llm_resp = call_llm(SYSTEM_PROMPT, user_prompt)

    try:
        ism = json.loads(llm_resp)
    except Exception:
        ism = {
            "doc_meta": {},
            "entities": [],
            "views": [],
            "actions": [],
            "__pending__": [llm_resp, "LLM 输出不是合法 JSON，已兜底"]
        }

    ism = ensure_ism_shape(ism)

    # 写上来源URL，方便追踪
    if feishu_url:
        ism["doc_meta"].setdefault("url", feishu_url)

    state["ism"] = ism

    log_event(
        "info",
        trace_id,
        "understand_doc",
        "end",
        message="ism generated",
        extra={
            "entities": len(ism["entities"]),
            "views": len(ism["views"]),
            "actions": len(ism["actions"]),
            "pending": len(ism["__pending__"]),
        },
    )
    return state
```
## 8. 注意事项

1. 必须兜底：LLM 只要一输出非 JSON，就要用最小 ISM 包起来，不能让后续节点崩
2. 必须保留 __pending__：这是给后续“人工/二次LLM/规则补全”的入口，不是 patch
3. 要打日志：至少打 trace_id、step=understand_doc、entities/views/actions 数量
4. 不要在这个节点里做 plan：这里只做“理解成 ISM”，后面节点再做“怎么调 MCP”
