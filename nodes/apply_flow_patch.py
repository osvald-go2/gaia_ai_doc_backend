import copy
import json
from typing import Dict, Any, List, Optional, Tuple

from models.state import AgentState
from utils.logger import logger

# Gaia 允许的类型
GAIA_TYPES = {"string", "int64", "float64", "list", "map"}


def _edge_key(edge: Dict[str, Any]) -> Tuple[str, str]:
    """生成边的唯一键"""
    return (edge["source"], edge["target"])


def _topo_sort_ok(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> bool:
    """检查图是否有环（拓扑排序）"""
    if not nodes:
        return True

    # 构建邻接表
    graph = {node["id"]: [] for node in nodes}
    in_degree = {node["id"]: 0 for node in nodes}

    for edge in edges:
        source, target = edge["source"], edge["target"]
        if source in graph and target in graph:
            graph[source].append(target)
            in_degree[target] += 1

    # 拓扑排序
    queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
    visited_count = 0

    while queue:
        current = queue.pop()
        visited_count += 1

        for neighbor in graph[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return visited_count == len(nodes)


def _find_node_index(nodes: List[Dict[str, Any]], node_id: str) -> int:
    """在节点列表中查找指定ID的节点索引"""
    for i, node in enumerate(nodes):
        if node.get("id") == node_id:
            return i
    return -1


def _find_field_index(field_list: List[Dict[str, Any]], where: Dict[str, Any]) -> int:
    """在字段列表中查找字段索引"""
    key = where.get("dataIndex") or where.get("__key__")
    if not key:
        return -1

    for i, field in enumerate(field_list or []):
        if field.get("dataIndex") == key or field.get("__key__") == key:
            return i
    return -1


def validate_graph_simple(graph: Dict[str, Any]) -> Dict[str, Any]:
    """
    图结构最小硬校验（8条规则）

    Returns:
        {"ok": bool, "errors": List[Dict], "warnings": List[str]}
    """
    errors = []
    warnings = []

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # 1. 基础结构检查
    if not isinstance(nodes, list) or not isinstance(edges, list):
        errors.append({"path": "", "reason": "nodes/edges must be arrays"})
        return {"ok": False, "errors": errors, "warnings": warnings}

    # 节点ID唯一性检查
    node_ids = []
    for node in nodes:
        if isinstance(node, dict) and "id" in node:
            node_ids.append(node["id"])

    if len(node_ids) != len(set(node_ids)):
        errors.append({"path": "nodes", "reason": "duplicated node id"})

    node_id_set = set(node_ids)

    # 2. 边引用检查
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source not in node_id_set or target not in node_id_set:
            errors.append({"path": f"edges[{source}->{target}]", "reason": "dangling edge"})

    # 3. 无环检查
    if not _topo_sort_ok(nodes, edges):
        errors.append({"path": "edges", "reason": "cycle detected"})

    # 4. 至少一个SQL节点
    sql_nodes = [node for node in nodes if node.get("componentId") == "lowcode.sql_raw"]
    if not sql_nodes:
        errors.append({"path": "nodes", "reason": "no SQL node found"})

    # 5. SQL节点配置检查
    for node in sql_nodes:
        configs = node.get("configs") or {}
        for required_key in ("engine", "psm", "reqBody"):
            if not configs.get(required_key):
                errors.append({
                    "path": f"nodes[{node['id']}].configs.{required_key}",
                    "reason": "required field missing"
                })

    # 6. 字段列表检查
    for node in nodes:
        field_list = node.get("fieldList", [])
        for field in field_list:
            field_path = f"nodes[{node['id']}].fieldList[{field.get('dataIndex', 'unknown')}]"

            # analysisType 检查
            analysis_type = field.get("analysisType")
            if analysis_type not in {"measure", "dimension"}:
                errors.append({"path": f"{field_path}.analysisType", "reason": "invalid analysisType"})

            # type 检查
            field_type = field.get("type")
            if field_type not in GAIA_TYPES:
                errors.append({"path": f"{field_path}.type", "reason": "invalid field type"})

            # 必需字段检查
            for required_field in ("dataIndex", "expression", "title"):
                if not field.get(required_field):
                    errors.append({"path": f"{field_path}.{required_field}", "reason": "required field missing"})

    # 7. JOIN节点检查（如果存在）
    join_nodes = [node for node in nodes if node.get("componentId") == "native.join"]
    for node in join_nodes:
        relations = node.get("configs", {}).get("relations", [])
        for i, relation in enumerate(relations):
            relation_path = f"nodes[{node['id']}].configs.relations[{i}]"
            for required_key in ("left", "right", "method", "fields"):
                if required_key not in relation:
                    errors.append({"path": f"{relation_path}.{required_key}", "reason": "required field missing"})

    # 8. 边去重检查
    edge_keys = [_edge_key(edge) for edge in edges]
    if len(edge_keys) != len(set(edge_keys)):
        warnings.append("duplicate edges found")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def apply_flow_patch_core(
    old_graph: Dict[str, Any],
    patch: Dict[str, Any],
    *,
    dry_run: bool = True,
    validate: bool = True,
    version: Optional[str] = None
) -> Dict[str, Any]:
    """
    核心补丁应用函数

    Args:
        old_graph: 原始图结构
        patch: 补丁结构
        dry_run: 是否为试运行
        validate: 是否进行验证
        version: 版本号（乐观锁用）

    Returns:
        {
            "ok": bool,
            "graph_new": dict,                # 应用后的完整图
            "mcp_payload": str | None,        # MCP载荷
            "errors": list[dict],             # 错误列表
            "warnings": list[str],            # 警告列表
            "diff_applied": dict              # 实际应用的补丁
        }
    """
    errors = []
    warnings = []

    # 深拷贝原图
    new_graph = copy.deepcopy(old_graph)
    nodes = new_graph.get("nodes", [])
    edges = new_graph.get("edges", [])

    node_id_set = {node.get("id") for node in nodes if isinstance(node, dict)}

    # 1. 删除边
    for edge_to_remove in (patch.get("remove_edges") or []):
        edges[:] = [
            edge for edge in edges
            if _edge_key(edge) != _edge_key(edge_to_remove)
        ]

    # 2. 删除节点（及相关边）
    for node_remove in (patch.get("remove_nodes") or []):
        node_id = node_remove.get("id")
        if not node_id:
            continue

        node_index = _find_node_index(nodes, node_id)
        if node_index >= 0:
            del nodes[node_index]
            # 删除相关边
            edges[:] = [
                edge for edge in edges
                if edge.get("source") != node_id and edge.get("target") != node_id
            ]
            node_id_set.discard(node_id)
        else:
            warnings.append(f"remove_nodes: node {node_id} not found")

    # 3. 添加节点
    for node_to_add in (patch.get("add_nodes") or []):
        node_id = node_to_add.get("id")
        if not node_id:
            continue

        if node_id in node_id_set:
            existing_node = nodes[_find_node_index(nodes, node_id)]
            if json.dumps(existing_node, sort_keys=True) != json.dumps(node_to_add, sort_keys=True):
                errors.append({"path": f"nodes[{node_id}]", "reason": "id conflict with different content"})
            else:
                warnings.append(f"add_nodes: node {node_id} already exists (identical)")
            continue

        nodes.append(node_to_add)
        node_id_set.add(node_id)

    # 4. 添加边
    edge_key_set = {_edge_key(edge) for edge in edges}
    for edge_to_add in (patch.get("add_edges") or []):
        source = edge_to_add.get("source")
        target = edge_to_add.get("target")

        if source not in node_id_set or target not in node_id_set:
            errors.append({"path": f"edges[{source}->{target}]", "reason": "dangling edge"})
            continue

        edge_key = _edge_key(edge_to_add)
        if edge_key not in edge_key_set:
            edges.append({"source": source, "target": target})
            edge_key_set.add(edge_key)

    # 5. 更新节点
    for node_update in (patch.get("update_nodes") or []):
        node_id = node_update.get("id")
        if not node_id:
            continue

        node_index = _find_node_index(nodes, node_id)
        if node_index < 0:
            errors.append({"path": f"update_nodes[{node_id}]", "reason": "node not found"})
            continue

        # 深拷贝节点以避免修改原引用
        node = copy.deepcopy(nodes[node_index])
        nodes[node_index] = node

        # 5.1 浅层更新
        for key, value in (node_update.get("set") or {}).items():
            node[key] = value

        # 5.2 configs更新
        if "configs_patch" in node_update:
            configs_patch = node_update["configs_patch"] or {}
            node.setdefault("configs", {})

            # set操作
            for key, value in (configs_patch.get("set") or {}).items():
                node["configs"][key] = value

            # unset操作
            for key in (configs_patch.get("unset") or []):
                node["configs"].pop(key, None)

        # 5.3 fieldList更新
        if "fieldList_patch" in node_update:
            field_patch = node_update["fieldList_patch"] or {}
            node.setdefault("fieldList", [])

            # 添加字段
            for field_to_add in (field_patch.get("add") or []):
                where = {"dataIndex": field_to_add.get("dataIndex") or field_to_add.get("__key__")}
                field_index = _find_field_index(node["fieldList"], where)

                if field_index >= 0:
                    node["fieldList"][field_index].update(field_to_add)
                    warnings.append(f"fieldList.add->replace {where}")
                else:
                    node["fieldList"].append(field_to_add)

            # 删除字段
            for where in (field_patch.get("remove") or []):
                field_index = _find_field_index(node["fieldList"], where)
                if field_index >= 0:
                    node["fieldList"].pop(field_index)
                else:
                    warnings.append(f"fieldList.remove miss {where}")

            # 更新字段
            for field_update in (field_patch.get("update") or []):
                where_condition = field_update.get("where") or {}
                field_index = _find_field_index(node["fieldList"], where_condition)

                if field_index >= 0:
                    node["fieldList"][field_index].update(field_update.get("set") or {})
                else:
                    warnings.append(f"fieldList.update miss {where_condition}")

    # 6. 去重边
    unique_edges = {}
    for edge in edges:
        edge_key = _edge_key(edge)
        unique_edges[edge_key] = edge
    new_graph["edges"] = list(unique_edges.values())

    # 7. 验证
    if validate:
        validation_result = validate_graph_simple(new_graph)
        if not validation_result["ok"]:
            errors.extend(validation_result["errors"])
        warnings.extend(validation_result["warnings"])

    # 8. 生成结果
    ok = len(errors) == 0
    mcp_payload = None

    if ok and not dry_run:
        mcp_payload = json.dumps({
            "nodes": new_graph.get("nodes", []),
            "edges": new_graph.get("edges", [])
        }, ensure_ascii=False)

    # 过滤实际应用的补丁
    diff_applied = {k: v for k, v in patch.items() if v}

    return {
        "ok": ok,
        "graph_new": new_graph,
        "mcp_payload": mcp_payload,
        "errors": errors,
        "warnings": warnings,
        "diff_applied": diff_applied
    }


def apply_flow_patch(state: AgentState) -> AgentState:
    """
    工作流节点：应用流程补丁，输出MCP载荷数组

    处理逻辑：
    1. 从plan中提取经过plan_from_ism校验的图数据
    2. 对每个图进行最终验证确保完全合规
    3. 输出mcp_payloads数组，每个元素可直接提交给MCP
    """
    trace_id = state["trace_id"]
    step_name = "apply_flow_patch"
    plan = state["plan"]

    logger.start(trace_id, step_name, "开始处理MCP载荷",
                extra={"plan_count": len(plan)})

    try:
        mcp_payloads = []
        processed_count = 0
        failed_count = 0

        for i, plan_item in enumerate(plan):
            if "tool" in plan_item and plan_item["tool"] == "mcp.save_graph":
                args = plan_item.get("args", {})
                graph_json_str = args.get("graph_json", "")
                interface_id = args.get("interface_id", f"interface_{i}")
                interface_name = args.get("interface_name", "Unknown")

                if not graph_json_str:
                    logger.error(trace_id, step_name,
                               f"接口 {interface_id} 缺少图数据",
                               extra={"interface_id": interface_id, "interface_name": interface_name})
                    failed_count += 1
                    continue

                try:
                    # 解析图数据
                    graph_data = json.loads(graph_json_str)

                    # 最终验证图结构
                    validation_result = validate_graph_simple(graph_data)

                    if not validation_result["ok"]:
                        logger.error(trace_id, step_name,
                                   f"接口 {interface_id} 图验证失败",
                                   extra={
                                       "interface_id": interface_id,
                                       "interface_name": interface_name,
                                       "errors": validation_result["errors"]
                                   })
                        failed_count += 1
                        continue

                    # 验证通过，添加到MCP载荷
                    mcp_payload = {
                        "tool": "mcp.save_graph",
                        "args": {
                            "graph_json": json.dumps(graph_data, ensure_ascii=False),
                            "interface_id": interface_id,
                            "interface_name": interface_name,
                            "validation_passed": True
                        }
                    }
                    mcp_payloads.append(mcp_payload)
                    processed_count += 1

                    logger.info(trace_id, step_name,
                              f"接口 {interface_name} 处理成功",
                              extra={
                                  "interface_id": interface_id,
                                  "node_count": len(graph_data.get("nodes", [])),
                                  "edge_count": len(graph_data.get("edges", [])),
                                  "field_count": sum(len(node.get("fieldList", [])) for node in graph_data.get("nodes", []))
                              })

                except json.JSONDecodeError as e:
                    logger.error(trace_id, step_name,
                               f"接口 {interface_id} JSON解析失败: {str(e)}",
                               extra={"interface_id": interface_id, "interface_name": interface_name})
                    failed_count += 1

            elif "error" in plan_item:
                # 记录在plan_from_ism阶段失败的项
                interface_id = plan_item.get("interface_id", "unknown")
                error_msg = plan_item.get("error", "Unknown error")
                interface_name = plan_item.get("interface_name", "Unknown")

                logger.error(trace_id, step_name,
                           f"接口 {interface_name} 在之前阶段失败: {error_msg}",
                           extra={"interface_id": interface_id, "error": error_msg})
                failed_count += 1

        # 写入state
        result_state = state.copy()
        result_state["mcp_payloads"] = mcp_payloads

        # 为了向后兼容，也生成一个简单的final_flow_json
        summary_info = {
            "processed_interfaces": processed_count,
            "failed_interfaces": failed_count,
            "total_payloads": len(mcp_payloads),
            "mcp_tool": "mcp.save_graph",
            "validation_status": "passed" if failed_count == 0 else "partial_failure"
        }
        result_state["final_flow_json"] = json.dumps(summary_info, ensure_ascii=False, indent=2)

        logger.end(trace_id, step_name, "MCP载荷处理完成",
                  extra={
                      "processed_count": processed_count,
                      "failed_count": failed_count,
                      "mcp_payloads_count": len(mcp_payloads),
                      "success_rate": f"{processed_count/(processed_count+failed_count)*100:.1f}%" if (processed_count+failed_count) > 0 else "0%"
                  })

        return result_state

    except Exception as e:
        logger.error(trace_id, step_name, f"MCP载荷处理失败: {str(e)}")

        # 即使失败也要返回空的结果
        result_state = state.copy()
        result_state["mcp_payloads"] = []
        result_state["final_flow_json"] = json.dumps({
            "processed_interfaces": 0,
            "failed_interfaces": 0,
            "total_payloads": 0,
            "error": str(e)
        }, ensure_ascii=False, indent=2)
        return result_state