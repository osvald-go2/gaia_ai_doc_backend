import json
import hashlib
from typing import Dict, Any, List, Optional

from models.state import AgentState
from utils.logger import logger


def plan_from_ism(state: AgentState) -> AgentState:
    """
    把已通过 NVSME 的 ISM（规范化/校验/稳定ID 后）编译为 Gaia 合规图
    支持两种模式：
    - create: 直接生成新的 graphs[]
    - update: 与旧图对比生成最小 patches[]

    约束：只能写：plan
    """
    trace_id = state["trace_id"]
    step_name = "plan_from_ism"
    ism = state["ism"]

    logger.start(trace_id, step_name, "开始从ISM编译Gaia合规图",
                extra={
                    "interfaces_count": len(ism.get("interfaces", [])),
                    "doc_title": ism.get("doc_meta", {}).get("title", "Unknown")
                })

    try:
        # 主要处理流程
        results = []

        for iface in ism.get("interfaces", []):
            try:
                # 1. 组件选择与字段编译
                plan = compile_interface(iface)

                # 2. 生成 nodes/edges
                graph = assemble_graph(plan, iface)

                # 3. 本地静态校验
                validation = ensure_gaia_constraints(graph)

                if not validation["ok"]:
                    results.append({
                        "interface_id": iface["id"],
                        "error": validation["errors"]
                    })
                    logger.error(trace_id, step_name, f"接口 {iface['id']} 校验失败",
                               extra={"errors": validation["errors"]})
                    continue

                # 4. 输出结果 (转换为 MCP 工具调用格式)
                graph_json = json.dumps(graph, ensure_ascii=False)
                results.append({
                    "tool": "mcp.save_graph",
                    "args": {
                        "graph_json": graph_json,
                        "interface_id": iface["id"],
                        "interface_name": iface["name"]
                    }
                })

                logger.info(trace_id, step_name, f"成功编译接口: {iface['id']}",
                          extra={
                              "interface_name": iface["name"],
                              "interface_type": iface["type"],
                              "node_count": len(graph["nodes"]),
                              "edge_count": len(graph["edges"]),
                              "field_count": len(iface.get("dimensions", [])) + len(iface.get("metrics", []))
                          })

            except Exception as e:
                logger.error(trace_id, step_name, f"编译接口 {iface.get('id', 'unknown')} 失败: {str(e)}")
                results.append({
                    "tool": "mcp.save_graph",
                    "args": {
                        "error": str(e),
                        "interface_id": iface.get("id", "unknown"),
                        "interface_name": iface.get("name", "")
                    }
                })

        # 写入 state - 将结果放入 plan 字段
        result_state = state.copy()
        result_state["plan"] = results

        logger.end(trace_id, step_name, "ISM编译完成",
                  extra={"results_count": len(results), "success_count": len([r for r in results if "error" not in r])})

        return result_state

    except Exception as e:
        logger.error(trace_id, step_name, f"计划生成失败: {str(e)}")
        # 即使失败也要返回空的 plan
        result_state = state.copy()
        result_state["plan"] = []
        return result_state


def map_gaia_type(data_type: str) -> str:
    """
    把抽象类型映射为 Gaia 允许的 5 种类型

    Args:
        data_type: 原始数据类型

    Returns:
        Gaia 标准类型: string/int64/float64/list/map
    """
    dt = (data_type or "").lower()

    # 小数/比例/金额
    if dt in {"number", "float", "double", "decimal", "real"}:
        return "float64"

    # 整数
    if dt in {"int", "integer", "long", "bigint"}:
        return "int64"

    # 日期/时间
    if dt in {"date", "datetime", "timestamp", "time"}:
        return "string"

    # 数组
    if dt in {"array", "list", "vector"}:
        return "list"

    # JSON 对象
    if dt in {"object", "json", "map", "dict"}:
        return "map"

    # 已经是标准类型
    if dt in {"string", "int64", "float64", "list", "map"}:
        return dt

    # 默认为字符串
    return "string"


def build_req_body(iface: Dict[str, Any], cols: List[str]) -> str:
    """
    生成最小可运行的 SQL 模板

    Args:
        iface: 接口信息
        cols: 字段列表

    Returns:
        SQL 语句
    """
    # 最小 SELECT 语句
    sql = f"SELECT {', '.join(cols)} FROM tab WHERE 1=1"

    # 趋势接口若有时间维度，添加排序
    if iface.get("type") == "trend_analysis" or iface.get("type") == "trend":
        time_cols = [col for col in cols if any(keyword in col.lower()
                    for keyword in ["day", "date", "time", "month", "year"])]
        if time_cols:
            sql += f" ORDER BY {time_cols[0]}"

    # 添加注释提示，方便后续替换为真实表名
    sql += " /* TODO: replace with real source table */"

    return sql


def h8(s: str) -> str:
    """
    生成8位哈希值用于稳定ID

    Args:
        s: 输入字符串

    Returns:
        8位十六进制哈希
    """
    return hashlib.sha256(s.encode()).hexdigest()[:8]


def compile_interface(iface: Dict[str, Any]) -> Dict[str, Any]:
    """
    编译单个接口为计划

    Args:
        iface: 接口信息

    Returns:
        包含 nodes 和 edges 的计划
    """
    dims = iface.get("dimensions", [])
    mets = iface.get("metrics", [])

    # 1) 编译 fieldList
    field_list = []

    # 处理维度字段
    for dim in dims:
        field_list.append({
            "analysisType": "dimension",
            "title": dim.get("name", dim.get("dataIndex", "")),
            "type": map_gaia_type(dim.get("data_type", "string")),
            "dataIndex": dim.get("expression", dim.get("dataIndex", "")),
            "expression": dim.get("expression", dim.get("dataIndex", "")),
            # 基础字段
            "calType": "normal",
            "dataPath": "",
            "dateFormat": "",
            "extra": "",
            "help": "",
            "id": "",
            "nuwaAppId": 0,
            "nuwaAppIds": "",
            "nuwaId": 0,
            "nuwaUuid": 0,
            "partitionFieldFlag": False,
            "partitionFormat": "",
            "showType": "default",
            "source": ""
        })

    # 处理指标字段
    for met in mets:
        field_list.append({
            "analysisType": "measure",
            "title": met.get("name", met.get("dataIndex", "")),
            "type": map_gaia_type(met.get("data_type", "number")),
            "dataIndex": met.get("expression", met.get("dataIndex", "")),
            "expression": met.get("expression", met.get("dataIndex", "")),
            # 基础字段
            "calType": "normal",
            "dataPath": "",
            "dateFormat": "",
            "extra": "",
            "help": "",
            "id": "",
            "nuwaAppId": 0,
            "nuwaAppIds": "",
            "nuwaId": 0,
            "nuwaUuid": 0,
            "partitionFieldFlag": False,
            "partitionFormat": "",
            "showType": "default",
            "source": ""
        })

    # 2) 生成 SQL 节点
    sql_id = f"n_sql_{h8(iface['id'] + '_sql')}"
    cols = [field["dataIndex"] for field in field_list]
    req_body = build_req_body(iface, cols)

    sql_node = {
        "id": sql_id,
        "componentId": "lowcode.sql_raw",
        "componentType": 2,
        "name": f"SQL-{iface['name']}",
        "type": "lowcode",
        "configs": {
            "engine": "doris",
            "psm": "var:CLUSTER_DSN",
            "reqBody": req_body,
            "lang": "",
            "retryConfig": {},
            "version": "v1.0"
        },
        "fieldFromList": [],
        "fieldList": field_list
    }

    # 3) 边装配 (MVP: 只有 SQL 节点，暂时无边)
    return {
        "nodes": [sql_node],
        "edges": []
    }


def assemble_graph(plan: Dict[str, Any], iface: Dict[str, Any]) -> Dict[str, Any]:
    """
    装配最终图结构

    Args:
        plan: 计划（包含 nodes/edges）
        iface: 接口信息

    Returns:
        完整的图结构
    """
    return {
        "interface_id": iface["id"],
        "interface_name": iface["name"],
        "nodes": plan["nodes"],
        "edges": plan["edges"]
    }


def ensure_gaia_constraints(graph: Dict[str, Any]) -> Dict[str, Any]:
    """
    本地静态校验（Gaia 断言门）

    Args:
        graph: 图结构

    Returns:
        校验结果 {ok: bool, errors: List[str]}
    """
    errors = []

    # 1. 顶层结构检查
    if "nodes" not in graph or "edges" not in graph:
        errors.append("缺少 nodes 或 edges 字段")
        return {"ok": False, "errors": errors}

    nodes = graph["nodes"]
    edges = graph["edges"]

    # 2. 至少一个 SQL 节点
    sql_nodes = [n for n in nodes if n.get("componentId") == "lowcode.sql_raw"]
    if not sql_nodes:
        errors.append("至少需要一个 SQL 节点")

    # 3. SQL 节点配置检查
    for node in sql_nodes:
        configs = node.get("configs", {})
        if not configs.get("engine"):
            errors.append(f"SQL 节点 {node['id']} 缺少 engine 配置")
        if not configs.get("psm"):
            errors.append(f"SQL 节点 {node['id']} 缺少 psm 配置")
        if not configs.get("reqBody"):
            errors.append(f"SQL 节点 {node['id']} 缺少 reqBody 配置")

        # 检查 fieldList
        field_list = node.get("fieldList", [])
        for i, field in enumerate(field_list):
            if not isinstance(field, dict):
                errors.append(f"SQL 节点 {node['id']} fieldList[{i}] 不是对象")
                continue

            # analysisType 检查
            analysis_type = field.get("analysisType")
            if analysis_type not in {"measure", "dimension"}:
                errors.append(f"SQL 节点 {node['id']} fieldList[{i}] analysisType 无效: {analysis_type}")

            # type 检查
            field_type = field.get("type")
            if field_type not in {"string", "int64", "float64", "list", "map"}:
                errors.append(f"SQL 节点 {node['id']} fieldList[{i}] type 无效: {field_type}")

            # 必需字段检查
            required_fields = ["title", "dataIndex", "expression"]
            for req_field in required_fields:
                if not field.get(req_field):
                    errors.append(f"SQL 节点 {node['id']} fieldList[{i}] 缺少必需字段: {req_field}")

    # 4. 边引用检查
    node_ids = {n["id"] for n in nodes}
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source not in node_ids:
            errors.append(f"边引用了不存在的源节点: {source}")
        if target not in node_ids:
            errors.append(f"边引用了不存在的目标节点: {target}")

    # 5. 环路检查（简单版本，防止自环）
    for edge in edges:
        if edge.get("source") == edge.get("target"):
            errors.append(f"存在自环边: {edge.get('source')}")

    return {
        "ok": len(errors) == 0,
        "errors": errors
    }