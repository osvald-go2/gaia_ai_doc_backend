# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
# Run the main AI Agent MVP workflow
uv run python app.py

# Or activate the virtual environment first
uv shell
python app.py
```

### Package Management
```bash
# Install dependencies
uv sync

# Add new dependencies
uv add <package_name>

# Check installed packages
uv pip list

# Update dependencies
uv sync --upgrade
```

### Python Environment
- Requires Python >=3.10 (specified in pyproject.toml)
- Uses uv as the package manager
- Virtual environment is created automatically in `.venv/`

## Architecture Overview

This is an AI Agent MVP that implements a document-to-workflow pipeline using LangGraph. The system processes Feishu document URLs and generates low-code workflow descriptions.

### Core Workflow Pipeline

The system implements a **6-node sequential workflow** using LangGraph's StateGraph:

```
ingest_input → fetch_feishu_doc → understand_doc → plan_from_ism → apply_flow_patch → finalize
```

Each node has **strict state isolation** - nodes can only write to specific fields in the AgentState:

- **ingest_input**: Writes `feishu_url`, `user_intent`, `trace_id`
- **fetch_feishu_doc**: Writes `raw_doc` (mock implementation)
- **understand_doc**: Writes `ism` (ISM - Intermediate Semantic Model)
- **plan_from_ism**: Writes `plan` (MCP-compatible execution steps)
- **apply_flow_patch**: Writes `final_flow_json` (DAG representation)
- **finalize**: Writes `response` (final output)

### State Management Architecture

The `AgentState` TypedDict enforces strict data flow:
- **Input Layer**: URL and user intent
- **Document Layer**: Raw document content
- **Semantic Layer**: ISM representation with entities and actions
- **Plan Layer**: MCP tool calls
- **Execution Layer**: DAG JSON structure
- **Output Layer**: Final response object

### Key Design Patterns

**Node Pattern**: Each node follows this structure:
1. Extract trace_id and required inputs from state
2. Log start phase with structured logger
3. Perform node-specific logic
4. Write only to allowed state fields
5. Log end phase with metrics
6. Return new state

**Mock Implementation**: The MVP uses mock data for:
- Feishu document fetching
- ISM generation (rule-based entity extraction)
- No real LLM calls or API integrations

**Structured Logging**: All nodes use `utils.logger.StructuredLogger` with:
- JSON format output
- trace_id for request correlation
- start/end/error phases
- Performance metrics

### Extension Points

The architecture is designed for future enhancement at specific insertion points:

1. **RAG/Memory**: Between `fetch_feishu_doc` and `understand_doc`
2. **Document Caching**: Before `fetch_feishu_doc`
3. **Validation**: After `understand_doc` (`validate_ism`) and after `plan_from_ism` (`validate_plan`)
4. **Real Flow Patching**: Replace `apply_flow_patch` with actual flow manipulation
5. **MCP Execution**: After `apply_flow_patch` for actual tool execution

### Data Structures

**ISM (Intermediate Semantic Model)**:
```python
{
    "doc_meta": {"title": str, "url": str},
    "entities": [{"id": str, "name": str, "fields": [...]}],
    "actions": [{"id": str, "type": str, "target_entity": str, "ops": [...]}],
    "views": []
}
```

**Plan Format**:
```python
[
    {
        "tool": "mcp.create_entity",
        "args": {"name": str, "fields": [...]}
    },
    {
        "tool": "mcp.create_crud_page",
        "args": {"target_entity": str, "ops": [...]}
    }
]
```

**Flow DAG JSON**:
```python
{
    "nodes": [{"id": str, "type": str, "config": {...}}],
    "edges": [{"id": str, "source": str, "target": str}]
}
```

## Dependencies

- **langgraph>=1.0.2**: Workflow orchestration and state management
- **langsmith>=0.4.39**: Monitoring and tracing
- **Python 3.10+**: Required for LangGraph compatibility

## Development Notes

- The system is designed to be **stateless** and **traceable** via trace_id
- All logging is structured JSON for easy parsing
- The mock implementation can be replaced with real integrations
- Node state isolation prevents unintended side effects
- The workflow is linear but can be extended with conditional edges in LangGraph