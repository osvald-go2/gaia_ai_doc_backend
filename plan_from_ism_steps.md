# `plan_from_ism` 的详细步骤（工程落地版）

> 目标：把 **已通过 NVSME 的 ISM**（规范化/校验/稳定ID 后）**编译**为 **Gaia 合规图**（一接口一张：`nodes`+`edges`），或与旧图对比生成 **最小 Patch**，供 MCP 以 **JSON 字符串** 保存/更新。

---

## 0) 输入 / 输出

- **输入**：`ism`  
  - 结构：`{ doc_meta, interfaces:[{ id,name,type, dimensions[], metrics[] }], __diag__ }`
  - 字段已具备：`name / expression / data_type / required / __key__`
- **（可选）输入**：`old_graphs_by_iface`（用于 update 模式；`{iface_id: graph}`）
- **输出（create）**：`graphs: [{ interface_id, interface_name, nodes, edges }]`
- **输出（update）**：`patches: [{ interface_id, patch:{ add_nodes, remove_nodes, add_edges, remove_edges, update_nodes } }]`

---

## 1) 顶层流程

```
for iface in ism.interfaces:
  plan = compile_interface(iface)                 # 1. 组件选择与字段编译
  graph = assemble_graph(plan)                    # 2. 生成 nodes/edges
  ensure_gaia_constraints(graph)                  # 3. 本地静态校验
  if mode == "create" or not old_graphs_by_iface:
      emit graph
  else:
      old = old_graphs_by_iface[iface.id]
      patch = diff_graph(old, graph)              # 4. 最小变更
      emit patch
```

---

## 2) 组件选择策略（最小可用链）

> **一图一接口**；默认只有 **SQL 节点**；如需参数改写/连接，再串 `rewrite` / `join`。

- **必选**：`lowcode.sql_raw`（SQL 原始节点）
  - `configs.engine`：默认 `"doris"`（或从 `doc_meta`/环境配置注入）
  - `configs.psm`：默认 `"var:CLUSTER_DSN"`（占位/环境变量）
  - `configs.reqBody`：由字段集合生成最小 `SELECT`（见 §4）
- **可选**：`native.rewrite_by_exp-1`
  - 若接口需要“把上游 query 参数转换为内部变量/表达式”，填 `configs.expression`
- **可选**：`native.join`
  - 多表/多来源融合场景：配置 `configs.relations[]`（`left/right/method/fields[]`）

> MVP 建议：**先只落 SQL 节点**（保证可跑），其它两类以开关控制，后续增量引入。

---

## 3) 字段编译（ISM → fieldList）

- **维度** → `analysisType="dimension"`
- **指标** → `analysisType="measure"`
- **title** = `name`（保留原始显示名）
- **dataIndex** = `expression`（英文占位/标识）
- **expression** = `expression`（与 dataIndex 一致；后续再由 RAG/规则替换为真实函数）
- **type**：按**Gaia 枚举**映射（见下）

### 3.1 类型映射（锁定）
把抽象类型映射为 Gaia 允许的 5 种：
- 小数/比例/金额：`float64`
- 整数：`int64`
- 日期/时间：`string`（必要时另加 `dateFormat` 等扩展）
- 数组：`list`
- JSON 对象：`map`
- 其余：`string`

```python
def map_gaia_type(dt: str) -> str:
    dt = (dt or "").lower()
    if dt in {"number","float","double","decimal"}: return "float64"
    if dt in {"int","integer","long"}:              return "int64"
    if dt in {"date","datetime","timestamp"}:       return "string"
    if dt in {"array","list"}:                      return "list"
    if dt in {"object","json","map"}:               return "map"
    if dt in {"string","int64","float64","list","map"}: return dt
    return "string"
```

---

## 4) SQL 生成（`configs.reqBody` 最小模板）

> 先生成**可运行的最小 SQL**（不依赖真实口径），后续再通过规则/RAG逐步“实化”。

- **字段集合**：`SELECT {all dataIndex}`  
- **最小体**：`"SELECT {cols} FROM tab WHERE 1=1"`（`tab` 为占位表）
- **可选扩展**：  
  - 趋势接口若有时间维度（如 `day`）：附加 `ORDER BY day`  
  - 可注入 `/* TODO: replace with real source */` 注释，方便后续 patch

```python
def build_req_body(iface, cols):
    sql = f"SELECT {', '.join(cols)} FROM tab WHERE 1=1"
    if iface["type"] == "trend" and any(c in cols for c in ("day","date")):
        sql += " ORDER BY day"
    return sql
```

---

## 5) 节点与边的装配

### 5.1 节点 ID（稳定可复现）
- `n_sql_{h8(iface.id + 'sql')}`
- `n_rewrite_{h8(iface.id + 'rewrite')}`
- `n_join_{h8(iface.id + 'join')}`

```python
import hashlib
def h8(s:str)->str: return hashlib.sha256(s.encode()).hexdigest()[:8]
```

### 5.2 SQL 节点结构
```json
{
  "id": "n_sql_xxx",
  "componentId": "lowcode.sql_raw",
  "componentType": 2,
  "name": "SQL组件",
  "type": "lowcode",
  "configs": { "engine":"doris", "psm":"var:CLUSTER_DSN", "reqBody":"SELECT ..."},
  "fieldList": [
    { "analysisType":"dimension", "title":"公司ID", "type":"string",  "dataIndex":"companyId", "expression":"companyId" },
    { "analysisType":"measure",   "title":"消耗",   "type":"float64", "dataIndex":"cost",      "expression":"cost" }
  ]
}
```

### 5.3 边（从左到右）
- 仅 SQL 时：`edges=[]`
- 存在改写：`n_sql → n_rewrite`
- 存在 JOIN：`n_left → n_join`、`n_right → n_join`（多输入）

---

## 6) 本地静态校验（Gaia 断言门）

> 编译后，**提交前**必须通过以下断言：

1. 顶层存在 `nodes`、`edges`；**无环**；边引用节点存在  
2. **至少一个 SQL 节点**；且 `configs.engine/psm/reqBody` 非空  
3. `fieldList[*]`：  
   - `analysisType ∈ {"measure","dimension"}`
   - `type ∈ {"string","int64","float64","list","map"}`
   - 存在 `dataIndex/expression/title`
4. 有 JOIN 时：`relations[].left/right/method/fields[{left,right}]` 完整

> 失败则返回 `errors[]`，不进入保存/更新。

---

## 7) create vs update（与旧图对比）

### 7.1 create 模式
- 直接输出 `graphs[]`，由上游 `mcp.save_graph(json.dumps(graph))` 保存

### 7.2 update 模式（最小补丁）
- 基于**稳定 ID**与字段 `__key__` 做差分
- **节点差异**：
  - 新增：`add_nodes`
  - 删除：`remove_nodes`（匹配 id）
  - 更新：`update_nodes`（如 `configs.reqBody` 变化、`fieldList` 变化）
- **边差异**：按 `source/target` 对比出 `add_edges/remove_edges`

```python
def diff_graph(old: dict, new: dict) -> dict:
    # 1) nodes: by id
    old_map = {n["id"]:n for n in old["nodes"]}
    new_map = {n["id"]:n for n in new["nodes"]}
    add_nodes = [n for i,n in new_map.items() if i not in old_map]
    remove_nodes = [n for i,n in old_map.items() if i not in new_map]
    update_nodes = []
    for i,n in new_map.items():
        if i in old_map and json.dumps(old_map[i], sort_keys=True) != json.dumps(n, sort_keys=True):
            # 可细化到只更新变化字段
            update_nodes.append(n)

    # 2) edges: as tuples
    to_tuples = lambda es: {(e["source"], e["target"]) for e in es}
    add_edges = [{"source":s,"target":t} for (s,t) in to_tuples(new["edges"]) - to_tuples(old["edges"])]
    remove_edges = [{"source":s,"target":t} for (s,t) in to_tuples(old["edges"]) - to_tuples(new["edges"])]

    return {"add_nodes":add_nodes,"remove_nodes":remove_nodes,"add_edges":add_edges,"remove_edges":remove_edges,"update_nodes":update_nodes}
```

---

## 8) 代码骨架（可直接放入工程）

```python
# plan_from_ism.py
import json

def compile_interface(iface: dict) -> dict:
    dims = iface.get("dimensions", [])
    mets = iface.get("metrics", [])
    # 1) fieldList
    fl = []
    for d in dims:
        fl.append({
          "analysisType":"dimension",
          "title": d["name"],
          "type": map_gaia_type(d.get("data_type")),
          "dataIndex": d["expression"],
          "expression": d["expression"]
        })
    for m in mets:
        fl.append({
          "analysisType":"measure",
          "title": m["name"],
          "type": map_gaia_type(m.get("data_type")),
          "dataIndex": m["expression"],
          "expression": m["expression"]
        })
    # 2) SQL node
    sql_id = f"n_sql_{h8(iface['id'] + '_sql')}"
    cols = [f["dataIndex"] for f in fl]
    reqBody = build_req_body(iface, cols)
    sql_node = {
      "id": sql_id,
      "componentId":"lowcode.sql_raw",
      "componentType":2,
      "name":"SQL组件",
      "type":"lowcode",
      "configs":{"engine":"doris","psm":"var:CLUSTER_DSN","reqBody": reqBody},
      "fieldList": fl
    }
    # 3) edges (MVP: 只有 SQL)
    return {"nodes":[sql_node], "edges":[]}

def assemble_graph(plan: dict, iface: dict) -> dict:
    return {
      "interface_id": iface["id"],
      "interface_name": iface["name"],
      "nodes": plan["nodes"],
      "edges": plan["edges"]
    }

def ensure_gaia_constraints(graph: dict) -> dict:
    # 略：按 §6 断言；返回 {ok,errors}
    return {"ok": True, "errors": []}

def plan_from_ism(ism: dict, *, mode="create", old_graphs_by_iface=None) -> dict:
    results = []
    for iface in ism["interfaces"]:
        plan = compile_interface(iface)
        graph = assemble_graph(plan, iface)
        v = ensure_gaia_constraints(graph)
        if not v["ok"]:
            results.append({"interface_id": iface["id"], "error": v["errors"]})
            continue
        if mode == "create" or not old_graphs_by_iface or iface["id"] not in old_graphs_by_iface:
            results.append({"interface_id": iface["id"], "graph": graph})
        else:
            patch = diff_graph(old_graphs_by_iface[iface["id"]], graph)
            results.append({"interface_id": iface["id"], "patch": patch})
    return results
```

---

## 9) 验收用例（以“消耗趋势”接口为例）

- **输入 ISM**：`dimensions=[{name:"天", expression:"day", data_type:"date"}]`；`metrics=[{name:"消耗", expression:"cost", data_type:"number"}]`
- **输出 Graph**：包含 1 个 SQL 节点；`fieldList` 中 `"天"→type:"string"`、`"消耗"→"float64"`；`reqBody` 为最小 SELECT。
- **本地校验通过**；**MCP 入参**为 `json.dumps(graph)` 字符串，保存成功返回 `graph_id`。

---

## 10) 日志与可观测（建议字段）

- `step`: compile_interface / assemble_graph / ensure_gaia / diff_graph
- `iface_id/name/type`
- `field_counts`: `{dimensions, metrics, total}`
- `node_count/edge_count`
- `payload_bytes`
- `duration_ms`
- `status`: ok / fail（附 `errors[]`）

---

## 11) 常见边界与兜底

- **无字段**：直接报错（至少一维一指标，或按接口语义要求）  
- **时间维度缺失（趋势）**：报错并提示补 `day/date`  
- **类型未知**：映射为 `string` 并记录 warning  
- **旧图缺失（update 模式）**：自动降级为 `create`  
- **JOIN 需要多输入**：暂不生成，提示“待补 relations”；或置空 JOIN 节点并标注占位 configs

---

### 总结
`plan_from_ism` = **组件选择（SQL 起步） + 字段编译（fieldList） + SQL 生成（最小模板） + 图装配 + 合规校验 +（可选）最小 Patch**。  
按此步骤，你可以稳定地把 ISM 编译为 **Gaia 合规图** 并经 MCP 落库；后续再逐步把 `reqBody/joins/rewrite` 从占位演进为真实实现。
