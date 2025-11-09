# AI Agent MVP

AI Agent MVP - 飞书URL解析到低代码工作流生成的核心链路

## 项目概述

本项目实现了一个最小可用的AI Agent，能够：
1. 接收飞书文档URL
2. 解析文档内容（MVP阶段使用mock数据）
3. 生成中间语义模型（ISM）
4. 制定执行计划
5. 合成JSON格式的低代码工作流
6. 返回最终结果

## 技术架构

```
[1] ingest_input → [2] fetch_feishu_doc → [3] understand_doc → [4] plan_from_ism → [5] apply_flow_patch → [6] finalize
```

## 项目结构

```
ai-agent-mvp/
├── app.py                 # 主入口，组装并运行工作流
├── studio_app.py          # LangGraph Studio 配置
├── models/
│   ├── __init__.py
│   └── state.py          # AgentState 状态定义
├── nodes/
│   ├── __init__.py
│   ├── ingest_input.py   # 输入接收和标准化
│   ├── fetch_feishu_doc.py  # 文档获取（mock版本）
│   ├── understand_doc.py     # ISM生成（mock版本）
│   ├── plan_from_ism.py      # 计划生成
│   ├── apply_flow_patch.py   # 流程合成
│   └── finalize.py           # 结果整理
├── utils/
│   ├── __init__.py
│   └── logger.py        # 结构化日志工具
├── pyproject.toml        # 项目配置
├── langgraph.json        # LangGraph Studio 配置
├── .env                  # 环境变量
├── .gitignore           # Git忽略文件
├── README.md            # 项目说明
├── STUDIO_GUIDE.md      # Studio 使用指南
└── CLAUDE.md            # Claude Code 指导文件
```

## 快速开始

### 环境要求

- Python 3.10+
- uv (推荐的Python包管理工具)

### 安装依赖

```bash
# 使用uv安装依赖
uv sync

# 安装 LangGraph Studio 支持
uv add "langgraph-cli[inmem]"
```

### 运行项目

#### 方法1：命令行运行
```bash
uv run python app.py
```

#### 方法2：使用 LangGraph Studio 调试
```bash
# 启动 Studio (默认端口 8123)
uv run langgraph dev --port 8123

# 然后在浏览器中访问 Studio UI:
# https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8123
```

详细使用说明请参考 [STUDIO_GUIDE.md](./STUDIO_GUIDE.md)

## 示例输出

运行项目后，你将看到类似以下的输出：

```json
{
  "ism": {
    "doc_meta": {
      "title": "from feishu",
      "url": "https://feishu.cn/doc/123"
    },
    "entities": [
      {
        "id": "ent_users",
        "name": "users",
        "fields": [
          {"name": "id", "type": "string", "required": true},
          {"name": "name", "type": "string"},
          {"name": "channel", "type": "string"}
        ]
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
    "views": []
  },
  "plan": [
    {
      "tool": "mcp.create_entity",
      "args": {
        "name": "users",
        "fields": [...]
      }
    },
    {
      "tool": "mcp.create_crud_page",
      "args": {
        "target_entity": "ent_users",
        "ops": ["create", "read", "update", "delete"]
      }
    }
  ],
  "flow_json": "{...DAG JSON...}",
  "trace_id": "req-demo-xxx",
  "status": "success"
}
```

## 开发说明

### 状态管理

项目使用 TypedDict 定义状态，确保每个节点只能修改特定的字段：

- `ingest_input`: 只能写 `feishu_url`, `user_intent`, `trace_id`
- `fetch_feishu_doc`: 只能写 `raw_doc`
- `understand_doc`: 只能写 `ism`
- `plan_from_ism`: 只能写 `plan`
- `apply_flow_patch`: 只能写 `final_flow_json`
- `finalize`: 只能写 `response`

### 日志记录

所有节点都使用结构化日志，包含以下字段：
- `timestamp`: 时间戳
- `level`: 日志级别
- `service`: 服务名称
- `trace_id`: 链路追踪ID
- `step`: 节点名称
- `phase`: 执行阶段（start/end/error）
- `message`: 日志消息
- `extra`: 额外信息（可选）

### 扩展性

该MVP设计预留了以下扩展位：

1. **RAG/长期记忆**: 在 `fetch_feishu_doc` 和 `understand_doc` 之间插入
2. **文档级短期记忆**: 在最前面插入缓存节点
3. **自检测**: 在 `understand_doc` 后插入 `validate_ism`；在 `plan_from_ism` 后插入 `validate_plan`
4. **真正的流程patch**: 替换 `apply_flow_patch` 为实际流程操作
5. **MCP调用**: 在 `apply_flow_patch` 后面添加执行节点

## 技术栈

- **Python**: 3.10+
- **LangGraph**: 1.0.2+ (工作流编排)
- **LangSmith**: 0.4.39+ (监控追踪)
- **uv**: 包管理器
- **LangGraph Studio**: 可视化调试工具

## 许可证

MIT License