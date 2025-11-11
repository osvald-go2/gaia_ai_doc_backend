# CLAUDE.md - AI Agent MVP Project Guide

## Project Overview

This is an AI Agent MVP that converts Feishu document URLs into low-code workflow generation. It processes documents, extracts semantic information, generates execution plans, and outputs JSON-based workflow definitions.

**Architecture**: LangGraph-based state machine with 6 nodes.

## Tech Stack

- **Python**: 3.10+
- **LangGraph**: 1.0.2+ (workflow orchestration)
- **FastAPI**: 0.120.4+ (REST API server)
- **LangSmith**: 0.4.39+ (monitoring and tracing)
- **uv**: Package manager
- **LangGraph Studio**: Visual debugging tool
- **DeepSeek**: LLM integration for document understanding
- **Feishu API**: Document content retrieval

## Project Structure

```
ai-agent-mvp/
├── app.py                    # Main workflow entry point (MISSING)
├── studio_app.py             # LangGraph Studio configuration
├── server.py                 # FastAPI REST API server
├── config.py                 # Application configuration
├── .env                      # Environment variables
├── pyproject.toml            # Project dependencies
├── langgraph.json            # LangGraph Studio configuration
├── start-langgraph-dev.bat   # Development launcher
├── README.md                 # Project documentation
├── STUDIO_GUIDE.md          # LangGraph Studio usage guide
├── models/
│   └── state.py              # AgentState definition
├── nodes/                    # Workflow processing nodes
│   ├── ingest_input.py      # Input validation
│   ├── fetch_feishu_doc.py   # Document retrieval
│   ├── understand_doc_parallel.py  # Document understanding
│   ├── normalize_and_validate_ism.py  # ISM normalization
│   ├── plan_from_ism.py     # Plan generation
│   ├── apply_flow_patch.py   # Workflow synthesis
│   └── finalize.py          # Result finalization
├── utils/                    # Utility modules
│   ├── logger.py             # Structured logging
│   └── other utilities...
├── mock/                     # Mock implementations
│   └── mcp_client.py        # Mock MCP client
└── test_*.py                 # Test scripts
```

## Key Workflow (6 nodes)

```
ingest_input → fetch_feishu_doc → understand_doc_parallel → normalize_and_validate_ism → plan_from_ism → apply_flow_patch → finalize
```

## Development Setup

### Installation

```bash
# Install dependencies
uv sync
uv add "langgraph-cli[inmem]"
```

### Environment Configuration

Copy `.env` and configure API keys:

```env
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=ai-agent-mvp
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
DEEPSEEK_API_KEY=your_deepseek_key
LOG_LEVEL=INFO
```

## Running the Project

### Method 1: LangGraph Studio (Recommended)

```bash
uv run langgraph dev --port 8123
# Access: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8123
```

### Method 2: FastAPI Server

```bash
uv run python server.py
# Access: http://localhost:8123
```

## API Usage

### Create Thread & Run Workflow

```bash
# Create thread
curl -X POST "http://localhost:8123/threads" -H "Content-Type: application/json" -d '{}'

# Run workflow
curl -X POST "http://localhost:8123/threads/{thread_id}/runs/wait" \
  -H "Content-Type: application/json" \
  -d '{"assistant_id": "agent", "input": {"feishu_url": "https://feishu.cn/doc/123", "user_intent": "generate_crud"}}'
```

## Key Features

### 1. Document Processing
- Feishu Integration with mock fallback
- Parallel document understanding
- Grid Block Parsing for structured content
- DeepSeek-powered LLM integration

### 2. Workflow Generation
- ISM (Intermediate Semantic Model) generation
- Plan compilation to executable workflows
- DAG-based graph synthesis
- Multi-level validation

### 3. MCP Integration
- Mock MCP client for testing
- Structured payload generation
- Comprehensive error handling

## State Management

Each node has strict write permissions:
- `ingest_input`: Only writes `feishu_urls`, `user_intent`, `trace_id`
- `fetch_feishu_doc`: Only writes `raw_docs`
- `understand_doc_parallel`: Only writes `ism`
- `normalize_and_validate_ism`: Only writes `ism`, `diag`
- `plan_from_ism`: Only writes `plan`
- `apply_flow_patch`: Only writes `final_flow_json`, `mcp_payloads`
- `finalize`: Only writes `response`

## Important Notes

### Missing Files
- **app.py**: Imported in `server.py` but doesn't exist. Use `studio_app.py` or create `app.py`.

### Configuration
- Structured logging with JSON format
- Graceful degradation to mock data when APIs fail
- Comprehensive validation at each step
- Trace ID propagation for debugging

### Performance
- Parallel document processing
- LLM response caching
- Adaptive batching

## Testing

### Test Scripts
- `test_workflow.py`: Complete workflow testing
- `test_understand_doc.py`: Document understanding
- `test_grid_parsing.py`: Grid parsing
- `test_dynamic_titles.py`: Dynamic content

### Test Input Example
```json
{
  "feishu_url": "https://feishu.cn/doc/123",
  "user_intent": "generate_crud",
  "trace_id": "test-001"
}
```

## Troubleshooting

1. **Studio Won't Start**: Ensure `langgraph-cli[inmem]` is installed
2. **UI Access Issues**: Check port availability
3. **Execution Failures**: Check console logs and inputs
4. **API Issues**: Verify environment variables

### Debug Mode
Set `LOG_LEVEL=DEBUG` for verbose JSON logging.

## Extension Points

1. **RAG Integration**: Between document fetching and understanding
2. **Caching Layer**: Document-level caching
3. **Validation Nodes**: Additional validation after ISM/plan generation
4. **Real MCP Integration**: Replace mock with actual MCP
5. **Multiple LLM Support**: Different LLM providers

## Contributing

1. Follow existing node structure and state rules
2. Use structured logging with trace IDs
3. Add comprehensive validation
4. Include tests for new features
5. Update documentation as needed
