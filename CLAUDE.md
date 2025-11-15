# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI Agent MVP that converts Feishu (Lark) document URLs into low-code workflow generation using a LangGraph-based state machine with 7 nodes. The project processes documents, extracts semantic information, generates execution plans, and outputs JSON-based workflow definitions.

## Tech Stack

- **Python**: 3.10+
- **LangGraph**: 1.0.2+ (workflow orchestration)
- **FastAPI**: 0.120.4+ (REST API server)
- **LangSmith**: 0.4.39+ (monitoring and tracing)
- **uv**: Package manager
- **LangGraph Studio**: Visual debugging tool
- **DeepSeek**: LLM integration for document understanding
- **Feishu API**: Document content retrieval

## Development Commands

### Environment Setup
```bash
# Install dependencies
uv sync

# Install LangGraph Studio support
uv add "langgraph-cli[inmem]"

# Create .env file from template
cp .env.example .env  # Edit with your API keys
```

### Running the Application

#### Method 1: LangGraph Studio (Recommended for development)
```bash
# Start Studio development server
uv run langgraph dev --port 8123

# Access Studio UI at: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8123
```

#### Method 2: FastAPI Server
```bash
# Start REST API server
uv run python server.py

# Server runs on http://localhost:8123
```

#### Method 3: Direct Workflow Execution
```bash
# Run workflow directly
uv run python app.py
```

### Testing
```bash
# Run specific debug scripts
uv run python debug_understand_doc.py
uv run python debug_context_extraction.py

# Run parallel processing test
uv run python -m nodes.understand_doc_parallel
```

## Architecture

### Core Workflow (7-node state machine)
```
ingest_input → fetch_feishu_doc → split_document → understand_doc_parallel
→ normalize_and_validate_ism → plan_from_ism → apply_flow_patch → finalize
```

### State Management
The project uses a strict state management pattern where each node can only modify specific fields:
- `ingest_input`: `feishu_urls`, `user_intent`, `trace_id`
- `fetch_feishu_doc`: `raw_docs`
- `split_document`: `doc_chunks`, `chunk_metadata`
- `understand_doc_parallel`: `ism_raw`
- `normalize_and_validate_ism`: `ism`, `diag`
- `plan_from_ism`: `plan`
- `apply_flow_patch`: `final_flow_json`, `mcp_payloads`
- `finalize`: `response`

### Key Components

#### Models (`models/state.py`)
- `AgentState`: TypedDict defining the complete workflow state with governance fields
- Supports both single URL (`feishu_url`) and multiple URLs (`feishu_urls`)
- Includes document chunking and processing control flags

#### Nodes (`nodes/`)
- Each node is a pure function that takes `AgentState` and returns updated `AgentState`
- Nodes use structured logging with trace ID propagation
- Error handling with graceful degradation to mock data

#### Utilities (`utils/`)
- `logger.py`: Structured JSON logging service
- `llm_cache.py`: LLM response caching
- `adaptive_batching.py`: Dynamic batch processing optimization
- `model_load_balancer.py`: LLM model distribution

## Configuration

### Environment Variables (.env)
```env
# Feishu API
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret

# DeepSeek API
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_BASE_URL=https://api.deepseek.com

# Workflow Control
FORCE_REAL_FEISHU_DATA=false  # Set to true to disable mock fallback
LOG_LEVEL=INFO

# LangSmith
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=ai-agent-mvp
```

### Key Configurations (`config.py`)
- `Config.has_feishu_auth()`: Checks if Feishu credentials are configured
- `Config.should_use_real_feishu_api()`: Determines whether to use real API
- `Config.allow_mock_fallback()`: Controls graceful degradation behavior

## API Usage

### REST API Endpoints
```bash
# Create thread
curl -X POST "http://localhost:8123/threads" -H "Content-Type: application/json" -d '{}'

# Run workflow
curl -X POST "http://localhost:8123/threads/{thread_id}/runs/wait" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "agent",
    "input": {
      "feishu_urls": ["https://feishu.cn/doc/123"],
      "user_intent": "generate_crud"
    }
  }'
```

### Sample Input
```json
{
  "feishu_urls": ["https://feishu.cn/doc/123"],
  "user_intent": "generate_crud",
  "trace_id": "test-001"
}
```

## Document Processing Features

### 1. Feishu Integration
- Multi-document URL support
- Authenticated API access with mock fallback
- Document content retrieval and parsing

### 2. Document Splitting (`nodes/split_document.py`)
- Intelligent document chunking for large content
- Preserves document structure and context
- Metadata tracking for chunk relationships

### 3. Parallel Processing (`nodes/understand_doc_parallel.py`)
- Concurrent document understanding using LLM
- Load balancing across multiple models
- Adaptive batching for optimal throughput

### 4. ISM (Intermediate Semantic Model)
- Structured semantic extraction from documents
- Entity-relationship modeling
- Action and view identification

### 5. Workflow Generation
- Plan compilation from ISM
- DAG-based workflow synthesis
- MCP payload generation for execution

## Development Patterns

### Structured Logging
All nodes use the structured logger:
```python
from utils.logger import logger

logger.start(trace_id, step_name, "Beginning operation")
logger.end(trace_id, step_name, "Operation completed", extra={"count": results})
logger.error(trace_id, step_name, "Operation failed", extra={"error": str(e)})
```

### Error Handling
- Graceful degradation to mock data
- Comprehensive error logging with trace IDs
- Validation at each workflow stage

### Testing Strategy
- Individual node testing with debug scripts
- End-to-end workflow testing
- Mock data for isolated development

## File Structure Notes

### Missing Files Notice
- `app.py` exists and is the main workflow entry point
- `studio_app.py` is specifically for LangGraph Studio configuration
- Both files define similar workflows but with different node import paths

### Key Files to Understand
- `models/state.py`: Complete state definition and governance rules
- `app.py`: Main workflow assembly and execution
- `studio_app.py`: Studio-specific configuration
- `server.py`: FastAPI REST API wrapper
- `config.py`: Environment and feature configuration

## Extension Points

1. **RAG Integration**: Insert between `fetch_feishu_doc` and `split_document`
2. **Advanced Caching**: Document-level caching before processing
3. **Multi-LLM Support**: Extend `model_load_balancer.py` for additional providers
4. **Real MCP Integration**: Replace mock MCP client in `apply_flow_patch`
5. **Custom Validation**: Add validation nodes after ISM and plan generation

## Troubleshooting

1. **Studio Won't Start**: Ensure `langgraph-cli[inmem]` is installed
2. **API Access Issues**: Check `.env` configuration and URL format
3. **Processing Failures**: Use `LOG_LEVEL=DEBUG` for detailed tracing
4. **Memory Issues**: Adjust batch sizes in `adaptive_batching.py`

## Performance Optimization

- Parallel document processing with configurable concurrency
- LLM response caching to reduce API calls
- Adaptive batching based on content size and system load
- Model load balancing for optimal resource utilization