import json
from models.state import AgentState
from utils.logger import logger
from mock.mcp_client import save_graph, get_mcp_statistics, list_mcp_graphs


def finalize(state: AgentState) -> AgentState:
    """
    职责：
    1. 应用 MCP 载荷，执行实际的图创建/更新操作
    2. 把 state 里的关键信息和执行结果整理出来，返回给调用方

    约束：只能写：response
    """
    trace_id = state["trace_id"]
    step_name = "finalize"

    logger.start(trace_id, step_name, "开始整理最终响应结果并应用MCP载荷",
                extra={"has_mcp_payloads": "mcp_payloads" in state})

    # 获取MCP载荷
    mcp_payloads = state.get("mcp_payloads", [])
    mcp_results = []

    # 应用每个MCP载荷
    for i, payload in enumerate(mcp_payloads):
        try:
            if payload.get("tool") == "mcp.save_graph":
                args = payload.get("args", {})
                graph_json = args.get("graph_json", "")
                interface_id = args.get("interface_id", f"interface_{i}")
                interface_name = args.get("interface_name", "Unknown")

                logger.info(trace_id, step_name,
                          f"执行MCP操作: {interface_name}",
                          extra={
                              "interface_id": interface_id,
                              "interface_name": interface_name,
                              "payload_index": i,
                              "validation_passed": args.get("validation_passed", False)
                          })

                # 调用Mock MCP客户端
                mcp_result = save_graph(
                    graph_json=graph_json,
                    interface_id=interface_id,
                    interface_name=interface_name
                )

                mcp_results.append(mcp_result)

                if mcp_result.get("success"):
                    logger.info(trace_id, step_name,
                              f"MCP操作成功: {interface_name}",
                              extra={
                                  "graph_id": mcp_result.get("graph_id"),
                                  "action": mcp_result.get("action"),
                                  "node_count": mcp_result.get("metadata", {}).get("node_count", 0),
                                  "edge_count": mcp_result.get("metadata", {}).get("edge_count", 0)
                              })
                else:
                    logger.error(trace_id, step_name,
                               f"MCP操作失败: {interface_name}",
                               extra={
                                   "interface_id": interface_id,
                                   "error": mcp_result.get("error", "Unknown error")
                               })

            else:
                logger.warning(trace_id, step_name,
                             f"跳过未知的MCP工具: {payload.get('tool')}",
                             extra={"payload_index": i})

        except Exception as e:
            error_msg = f"执行MCP载荷时发生异常: {str(e)}"
            logger.error(trace_id, step_name, error_msg,
                        extra={"payload_index": i, "error": str(e)})

            mcp_results.append({
                "success": False,
                "payload_index": i,
                "error": error_msg
            })

    # 统计MCP执行结果
    successful_mcp = len([r for r in mcp_results if r.get("success")])
    failed_mcp = len(mcp_results) - successful_mcp

    # 获取MCP统计信息
    mcp_stats = get_mcp_statistics()

    # 构建最终响应
    response = {
        "trace_id": trace_id,
        "status": "success" if failed_mcp == 0 else "partial_failure",
        "ism": state.get("ism", {}),
        "plan": state.get("plan", []),
        "flow_json": state.get("final_flow_json", "{}"),
        "mcp_execution": {
            "total_payloads": len(mcp_payloads),
            "successful_executions": successful_mcp,
            "failed_executions": failed_mcp,
            "success_rate": f"{successful_mcp/len(mcp_payloads)*100:.1f}%" if len(mcp_payloads) > 0 else "0%",
            "results": mcp_results
        },
        "mcp_statistics": {
            "total_graphs": mcp_stats.get("total_graphs", 0),
            "total_executions": mcp_stats.get("total_executions", 0),
            "overall_success_rate": mcp_stats.get("success_rate", "0%")
        }
    }

    # 写入 state - 只写允许的字段
    result_state = state.copy()
    result_state["response"] = response

    logger.end(trace_id, step_name, "响应结果整理完成",
              extra={
                  "ism_interfaces_count": len(response["ism"].get("interfaces", [])),
                  "plan_count": len(response["plan"]),
                  "mcp_payloads_count": len(mcp_payloads),
                  "mcp_successful": successful_mcp,
                  "mcp_failed": failed_mcp,
                  "response_size": len(str(response))
              })

    return result_state