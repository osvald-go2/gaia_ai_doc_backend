understand_func_v2
更新点：
这一层语义的 Markdown。LLM 要知道：
这是一个“分栏的 UI 结构”
右边那一栏才是“真正的字段说明”
里面可能既有维度又有指标，还混着“参考口径”这种要忽略的行
所以提示词要显式讲清楚这些规则，不然模型会把 content: | 当普通文本，甚至会把左边的 [趋势图.png] 当成字段。
我给你一版改过的 prompt，你可以直接贴到 understand_doc 里（system+user）。
```
[system]
你是一个文档结构解析器，作用是把“产品设计”这部分的 Markdown 文档，转成一个固定的接口语义模型（ISM）。

现在的文档是我方自定义的 Markdown，包含如下结构：

1. 标题使用 # / ## 标识
2. 产品设计的每一小节使用 ```grid ... ``` 表示一个功能块（例如：总筛选项、消耗波动详情、素材明细、消耗趋势）
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
只解析类似“产品设计”或者“产品详细设计”里这一节
按照节名识别出这是哪一个接口
- “总筛选项” → 生成维度接口（dimension_group）
- “消耗波动详情” → 生成指标接口（metric_group）
- “素材明细” → 同时有维度和指标（mix）
- “消耗趋势” → 有时间维度的指标接口（trend）
只从 content: | 下面的真正字段行里提取维度/指标

忽略图片/示意图/参考口径（包含“参考口径:”的行不要输出）
对每个字段生成结构：
- name：保留文档里的原始名字（中/英都可以）
- expression：把 name 翻成英文的占位（公司ID→companyId，消耗→cost，天→day，CTR→ctr，CVR→cvr，CPA→cpa）
- data_type：维度一般是 string，指标是 number，时间是 date
- required：如果判断是关键条件（比如公司ID、时间），设为 true，否则 false
最终只能输出 JSON，字段必须是：
- doc_meta
- interfaces （数组，至少有 1 个）
- pending （数组，可为空）

如果文档里出现你无法判断的行，请写到 pending，不要编造。


然后 user prompt 这样写 👇

```text
[user]
下面是一段从“产品设计”中截出来的内容，请你只解析这一段，不要解析背景、需求、总结等其它部分。

请根据这段内容对应的标题，按下面的规则输出接口：

- 如果标题是“总筛选项”，请输出：
{
  "doc_meta": {...可空...},
  "interfaces": [
    {
      "id": "api_filter_options",
      "name": "总筛选项",
      "type": "dimension_group",
      "dimensions": [ { "name": "...", "expression": "...", "data_type": "string", "required": true/false } ]
    }
  ],
  "__pending__": []
}

- 如果标题是“消耗波动详情”，请输出：
{
  "doc_meta": {...},
  "interfaces": [
    {
      "id": "api_spend_fluctuation",
      "name": "消耗波动详情",
      "type": "metric_group",
      "metrics": [ { "name": "...", "expression": "...", "data_type": "number", "required": true/false } ]
    }
  ],
  "__pending__": []
}

- 如果标题是“素材明细”，请输出：
{
  "doc_meta": {...},
  "interfaces": [
    {
      "id": "api_material_detail",
      "name": "素材明细",
      "type": "mix",
      "dimensions": [...],
      "metrics": [...]
    }
  ],
  "__pending__": []
}

- 如果标题是“消耗趋势”，请输出：
{
  "doc_meta": {...},
  "interfaces": [
    {
      "id": "api_spend_trend",
      "name": "消耗趋势",
      "type": "trend",
      "dimensions": [...],
      "metrics": [...]
    }
  ],
  "__pending__": []
}

下面是要解析的内容：

{{MARKDOWN_SNIPPET}}
```
你要记住的点
1. 要改提示词：必须让 LLM 知道有 grid 和 content: | 的存在。
2. 要告诉它忽略参考口径：不然会把 参考口径: www.baidu.com 当成字段。
3. 要告诉它 4 种标题各自产什么 JSON：不让它自己想。
4. 要说 expression 是“name 的英文版占位”：不然它会直接 output “sum(消耗)”。

这样一改，你的链条就是真正的：

markdown (带 grid) → LLM（懂 grid） → ISM（四个接口） 