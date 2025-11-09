#!/usr/bin/env python3
"""
FastAPI 服务器 - 提供前端调用的API接口
"""

import uuid
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import create_graph
from models.state import AgentState
from utils.logger import logger

app = FastAPI(title="AI Agent MVP API", version="1.0.0")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建工作流图
workflow = create_graph()


class ThreadCreate(BaseModel):
    """创建Thread的请求模型"""
    pass


class RunCreate(BaseModel):
    """创建Run的请求模型"""
    assistant_id: str
    input: Dict[str, Any]


class ThreadResponse(BaseModel):
    """Thread响应模型"""
    thread_id: str


class RunResponse(BaseModel):
    """Run响应模型"""
    status: str
    result: Dict[str, Any]
    thread_id: str


# 存储threads（内存存储，生产环境应使用数据库）
threads = {}


@app.post("/threads", response_model=ThreadResponse)
async def create_thread(request: ThreadCreate):
    """创建新的thread"""
    thread_id = str(uuid.uuid4())
    threads[thread_id] = {
        "id": thread_id,
        "runs": {}
    }
    print(f"创建thread: {thread_id}")
    return ThreadResponse(thread_id=thread_id)


@app.post("/threads/{thread_id}/runs/wait", response_model=RunResponse)
async def run_workflow_wait(thread_id: str, request: RunCreate):
    """运行工作流并等待完成"""
    if thread_id not in threads:
        raise HTTPException(status_code=404, detail="Thread not found")

    run_id = str(uuid.uuid4())

    try:
        # 准备输入状态
        input_state = AgentState(
            feishu_urls=request.input.get("feishu_urls", []),
            feishu_url=request.input.get("feishu_url"),
            user_intent=request.input.get("user_intent", "generate_crud"),
            trace_id=request.input.get("trace_id", f"api-{run_id[:8]}")
        )

        print(f"开始运行工作流 - thread_id: {thread_id}, run_id: {run_id}, trace_id: {input_state['trace_id']}")

        # 运行工作流
        result = workflow.invoke(input_state)

        # 记录运行结果
        threads[thread_id]["runs"][run_id] = {
            "id": run_id,
            "status": "completed",
            "result": result
        }

        print(f"工作流运行完成 - thread_id: {thread_id}, run_id: {run_id}, trace_id: {input_state['trace_id']}, status: success")

        return RunResponse(
            status="completed",
            result=result,
            thread_id=thread_id
        )

    except Exception as e:
        print(f"工作流运行失败 - thread_id: {thread_id}, run_id: {run_id}, error: {str(e)}")

        # 记录失败结果
        threads[thread_id]["runs"][run_id] = {
            "id": run_id,
            "status": "failed",
            "error": str(e)
        }

        raise HTTPException(status_code=500, detail=str(e))


@app.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    """获取thread信息"""
    if thread_id not in threads:
        raise HTTPException(status_code=404, detail="Thread not found")
    return threads[thread_id]


@app.get("/")
async def root():
    """根路径"""
    return {"message": "AI Agent MVP API is running", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8123)