"""
Mock MCP 客户端
模拟真实的 MCP (Model Context Protocol) 服务，用于创建和更新图结构
"""

import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from utils.logger import logger


class MockMCPClient:
    """Mock MCP 客户端，模拟图结构的创建和更新操作"""

    def __init__(self):
        # 模拟存储
        self.graphs = {}  # graph_id -> graph_data
        self.interface_graphs = {}  # interface_id -> graph_id
        self.executions = []  # 执行历史记录

    def save_graph(self, graph_json: str, interface_id: str, interface_name: str) -> Dict[str, Any]:
        """
        保存图结构（创建或更新）

        Args:
            graph_json: 图结构的JSON字符串
            interface_id: 接口ID
            interface_name: 接口名称

        Returns:
            执行结果
        """
        try:
            # 解析图数据
            graph_data = json.loads(graph_json)

            # 生成或获取graph_id
            graph_id = self.interface_graphs.get(interface_id)
            is_update = graph_id is not None

            if not is_update:
                # 创建新的图
                graph_id = f"graph_{uuid.uuid4().hex[:8]}"
                self.interface_graphs[interface_id] = graph_id

                # 添加创建时间
                graph_data["created_at"] = datetime.utcnow().isoformat()
                graph_data["created_by"] = "ai-agent-mvp"

                logger.info("mcp_client", "create_graph",
                          f"创建新图: {interface_name}",
                          extra={
                              "graph_id": graph_id,
                              "interface_id": interface_id,
                              "node_count": len(graph_data.get("nodes", [])),
                              "edge_count": len(graph_data.get("edges", []))
                          })
            else:
                # 更新现有图
                old_graph = self.graphs.get(graph_id, {})

                # 保留创建信息
                graph_data["created_at"] = old_graph.get("created_at", datetime.utcnow().isoformat())
                graph_data["created_by"] = old_graph.get("created_by", "ai-agent-mvp")

                logger.info("mcp_client", "update_graph",
                          f"更新现有图: {interface_name}",
                          extra={
                              "graph_id": graph_id,
                              "interface_id": interface_id,
                              "old_nodes": len(old_graph.get("nodes", [])),
                              "new_nodes": len(graph_data.get("nodes", []))
                          })

            # 添加更新信息
            graph_data["updated_at"] = datetime.utcnow().isoformat()
            graph_data["updated_by"] = "ai-agent-mvp"
            graph_data["graph_id"] = graph_id
            graph_data["interface_id"] = interface_id
            graph_data["interface_name"] = interface_name

            # 存储图数据
            self.graphs[graph_id] = graph_data

            # 记录执行历史
            execution = {
                "execution_id": f"exec_{uuid.uuid4().hex[:8]}",
                "graph_id": graph_id,
                "interface_id": interface_id,
                "interface_name": interface_name,
                "action": "update" if is_update else "create",
                "timestamp": datetime.utcnow().isoformat(),
                "node_count": len(graph_data.get("nodes", [])),
                "edge_count": len(graph_data.get("edges", [])),
                "field_count": sum(len(node.get("fieldList", [])) for node in graph_data.get("nodes", [])),
                "status": "success"
            }
            self.executions.append(execution)

            # 返回成功结果
            return {
                "success": True,
                "graph_id": graph_id,
                "action": "update" if is_update else "create",
                "interface_id": interface_id,
                "interface_name": interface_name,
                "execution_id": execution["execution_id"],
                "message": f"图{'更新' if is_update else '创建'}成功",
                "metadata": {
                    "node_count": len(graph_data.get("nodes", [])),
                    "edge_count": len(graph_data.get("edges", [])),
                    "field_count": sum(len(node.get("fieldList", [])) for node in graph_data.get("nodes", []))
                }
            }

        except json.JSONDecodeError as e:
            error_msg = f"图JSON解析失败: {str(e)}"
            logger.error("mcp_client", "save_graph", error_msg,
                        extra={"interface_id": interface_id, "error": str(e)})

            # 记录失败执行
            execution = {
                "execution_id": f"exec_{uuid.uuid4().hex[:8]}",
                "interface_id": interface_id,
                "action": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "status": "failed",
                "error": error_msg
            }
            self.executions.append(execution)

            return {
                "success": False,
                "interface_id": interface_id,
                "execution_id": execution["execution_id"],
                "error": error_msg
            }

        except Exception as e:
            error_msg = f"保存图时发生未知错误: {str(e)}"
            logger.error("mcp_client", "save_graph", error_msg,
                        extra={"interface_id": interface_id, "error": str(e)})

            return {
                "success": False,
                "interface_id": interface_id,
                "error": error_msg
            }

    def get_graph(self, graph_id: str) -> Optional[Dict[str, Any]]:
        """获取图数据"""
        return self.graphs.get(graph_id)

    def get_graph_by_interface(self, interface_id: str) -> Optional[Dict[str, Any]]:
        """根据接口ID获取图数据"""
        graph_id = self.interface_graphs.get(interface_id)
        if graph_id:
            return self.graphs.get(graph_id)
        return None

    def list_graphs(self) -> List[Dict[str, Any]]:
        """列出所有图的基本信息"""
        result = []
        for graph_id, graph_data in self.graphs.items():
            result.append({
                "graph_id": graph_id,
                "interface_id": graph_data.get("interface_id"),
                "interface_name": graph_data.get("interface_name"),
                "created_at": graph_data.get("created_at"),
                "updated_at": graph_data.get("updated_at"),
                "node_count": len(graph_data.get("nodes", [])),
                "edge_count": len(graph_data.get("edges", []))
            })
        return result

    def get_execution_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取执行历史"""
        return self.executions[-limit:] if limit > 0 else self.executions

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_graphs = len(self.graphs)
        total_executions = len(self.executions)
        successful_executions = len([e for e in self.executions if e.get("status") == "success"])
        failed_executions = total_executions - successful_executions

        total_nodes = sum(len(g.get("nodes", [])) for g in self.graphs.values())
        total_edges = sum(len(g.get("edges", [])) for g in self.graphs.values())
        total_fields = sum(sum(len(node.get("fieldList", [])) for node in g.get("nodes", []))
                          for g in self.graphs.values())

        return {
            "total_graphs": total_graphs,
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate": f"{successful_executions/total_executions*100:.1f}%" if total_executions > 0 else "0%",
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "total_fields": total_fields
        }


# 全局Mock MCP客户端实例
mock_mcp_client = MockMCPClient()


def save_graph(graph_json: str, interface_id: str, interface_name: str) -> Dict[str, Any]:
    """
    MCP save_graph 工具的Mock实现

    Args:
        graph_json: 图结构的JSON字符串
        interface_id: 接口ID
        interface_name: 接口名称

    Returns:
        执行结果
    """
    return mock_mcp_client.save_graph(graph_json, interface_id, interface_name)


def get_mcp_statistics() -> Dict[str, Any]:
    """获取MCP统计信息"""
    return mock_mcp_client.get_statistics()


def list_mcp_graphs() -> List[Dict[str, Any]]:
    """列出所有MCP图"""
    return mock_mcp_client.list_graphs()