# `apply_flow_patch` 设计说明（MVP → 扩展）

> 目标：把**最小补丁**安全地应用到现有 Gaia 图（`nodes`+`edges`），保持 **一图一接口 / 无环 / 字段与类型合规**，并产出可直接提交给 MCP 的 **JSON 字符串**。  
> 原则：**强约束用程序校验**（8 条硬规则），**弱约束交给 LLM Linter** 产出可选 Patch。

---

## 1. 函数签名与返回

```python
def apply_flow_patch(
    old_graph: dict,
    patch: dict,
    *,
    dry_run: bool = True,
    validate: bool = True,
    version: str | None = None,
) -> dict:
    """
    返回:
      {
        "ok": bool,
        "graph_new": dict,                # 应用后的完整图（dry_run=True 也返回模拟结果）
        "mcp_payload": str | None,        # ok 且 dry_run=False 时提供；字符串化 JSON
        "errors": list[dict],             # {path, reason}
        "warnings": list[str],            # 非致命提示
        "diff_applied": dict              # 服务器可选回显（过滤后的补丁）
      }
    """
```

- `dry_run=True`：仅模拟补丁应用，便于前端预览与回显。  
- `validate=True`：应用后执行**最小硬校验**（见 §5）。  
- `version`：保留用于乐观锁（扩展）。

---

## 2. Patch 结构（最小变更集）

```jsonc
{
  "add_nodes":    [{ /* 完整节点 */ }],
  "remove_nodes": [{ "id": "n_xxx" }],
  "update_nodes": [{
    "id": "n_xxx",
    "set": { "name": "新名称", "componentId": "lowcode.sql_raw" },     # 顶层浅 set
    "configs_patch": { "set": { "reqBody": "SELECT ..." }, "unset": ["psm"] },
    "fieldList_patch": {
      "add":    [{ "analysisType":"measure","title":"消耗","type":"float64","dataIndex":"cost","expression":"cost" }],
      "remove": [{ "dataIndex": "companyId" }],                        # 用 dataIndex 或 __key__ 定位
      "update": [{ "where":{"dataIndex":"day"}, "set":{"title":"天"}}] # 局部 set
    }
  }],
  "add_edges":    [{ "source":"n_a", "target":"n_b" }],
  "remove_edges": [{ "source":"n_a", "target":"n_b" }]
}
```

> 说明：**不强制同时提供所有键**；空或缺省键视为无操作。`update_nodes` 支持**浅层 set** 与 **configs/fieldList 的细粒度 patch**。

---

## 3. 应用顺序与幂等策略

1) **预检查**：`patch` 结构、必填键、ID/引用格式是否合理。  
2) **复制旧图**：`graph = deepcopy(old_graph)`。  
3) **删除**：先 `remove_edges` 再 `remove_nodes`（避免悬挂）。  
4) **新增**：`add_nodes` → `add_edges`。  
5) **更新**：处理 `update_nodes`：
   - `set`：节点顶层浅合并（覆盖原值）；
   - `configs_patch`：`set/unset` 键；
   - `fieldList_patch`：按 `dataIndex`（或 `__key__`）定位 `add/remove/update`；
6) **去重**：节点按 `id` 去重；边按 `(source,target)` 去重；  
7) **校验**（可选）：通过**最小硬校验**（§5）；  
8) **序列化**：`dry_run=False` 时，返回 `mcp_payload = json.dumps({"nodes":..., "edges":...})`。

**幂等策略**：  
- `add_nodes`：已存在且内容相同 → 跳过并写 warning；内容不同 → 记 error（避免静默覆盖）。  
- `add_edges`：重复边忽略；引用不存在节点 → 记 error。  
- `remove_*`：不存在则写 warning。  
- `update_nodes`：找不到 `id` → 记 error；`fieldList_patch` 未命中 → warning。

---

## 4. 冲突与回退

- **节点 ID 冲突**（新增与已有不一致）：报错并停止；不自动改 ID。  
- **边引用不存在节点**：报错；不落入图。  
- **校验失败**：`ok=False`，保留 `graph_new` 供 UI 高亮；`dry_run=False` 也不生成 `mcp_payload`。  
- **事务控制（可选）**：`abort_on_first_error=True` 时遇错回滚到旧图。

---

## 5. 最小硬校验（8 条）

1. `nodes`、`edges` 存在且为数组；节点 `id` 唯一；  
2. 边引用的 `source/target` 必须存在；  
3. **无环**（拓扑排序检测）；  
4. 至少一个 **SQL 节点**：`componentId="lowcode.sql_raw"`；  
5. SQL 节点 `configs.engine/psm/reqBody` 非空；  
6. `fieldList[*]`（若存在）：  
   - `analysisType ∈ {"measure","dimension"}`；  
   - `type ∈ {"string","int64","float64","list","map"}`；  
   - 含 `dataIndex/expression/title`；  
7. JOIN 节点（若出现）：`relations[].left/right/method/fields[{left,right}]` 完整；  
8.（可选）边集合去重，节点结构为 `dict`。

> 其余“风格/建议”交给 LLM Linter，产出可选 Patch，再次通过本硬校验。

---

## 6. 参考实现（可直接落代码）

```python
import copy, json

GAIA_TYPES = {"string","int64","float64","list","map"}

def _edge_key(e): return (e["source"], e["target"])

def _topo_ok(nodes, edges):
    g = {n["id"]: [] for n in nodes}
    for e in edges: g[e["source"]].append(e["target"])
    indeg = {k:0 for k in g}
    for s in g:
        for t in g[s]: indeg[t]+=1
    q=[k for k,v in indeg.items() if v==0]
    seen=0
    while q:
        k=q.pop()
        seen+=1
        for t in g[k]:
            indeg[t]-=1
            if indeg[t]==0: q.append(t)
    return seen==len(g)

def _find_node(nodes, nid):
    for i,n in enumerate(nodes):
        if n["id"]==nid: return i
    return -1

def _find_field_idx(fieldList, where:dict):
    key = where.get("dataIndex") or where.get("__key__")
    if not key: return -1
    for i,f in enumerate(fieldList or []):
        if f.get("dataIndex")==key or f.get("__key__")==key: return i
    return -1

def validate_graph_simple(graph: dict) -> dict:
    errors, warns = [], []
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    # 1. 基础结构
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return {"ok": False, "errors":[{"path":"", "reason":"nodes/edges must be arrays"}], "warnings": []}
    ids = [n.get("id") for n in nodes if isinstance(n, dict)]
    if len(ids) != len(set(ids)):
        errors.append({"path":"nodes", "reason":"duplicated node id"})
    idset = set(ids)
    # 2. 引用与 DAG
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s not in idset or t not in idset:
            errors.append({"path":f"edges[{s}->{t}]", "reason":"dangling edge"})
    if not _topo_ok(nodes, edges):
        errors.append({"path":"edges", "reason":"cycle detected"})
    # 3. SQL 节点
    sqls = [n for n in nodes if n.get("componentId")=="lowcode.sql_raw"]
    if not sqls:
        errors.append({"path":"nodes", "reason":"no SQL node found"})
    for n in sqls:
        cfg = n.get("configs") or {}
        for k in ("engine","psm","reqBody"):
            if not cfg.get(k):
                errors.append({"path":f"nodes[{n['id']}].configs.{k}", "reason":"required"})
    # 4. 字段
    for n in nodes:
        for f in (n.get("fieldList") or []):
            if f.get("analysisType") not in {"measure","dimension"}:
                errors.append({"path":f"nodes[{n['id']}].fieldList[{f.get('dataIndex')}].analysisType","reason":"invalid"})
            if f.get("type") not in GAIA_TYPES:
                errors.append({"path":f"nodes[{n['id']}].fieldList[{f.get('dataIndex')}].type","reason":"invalid"})
            for k in ("dataIndex","expression","title"):
                if not f.get(k):
                    errors.append({"path":f"nodes[{n['id']}].fieldList[{f.get('dataIndex')}].{k}","reason":"required"})
    return {"ok": len(errors)==0, "errors": errors, "warnings": warns}

def apply_flow_patch(old_graph, patch, *, dry_run=True, validate=True, version=None):
    errors, warnings = [], []
    g = copy.deepcopy(old_graph)
    nodes = g.get("nodes",[]); edges = g.get("edges",[])
    idset = {n["id"] for n in nodes}

    # 1) remove edges
    for e in (patch.get("remove_edges") or []):
        edges[:] = [x for x in edges if not (_edge_key(x)==_edge_key(e))]

    # 2) remove nodes (and dangling edges)
    for rm in (patch.get("remove_nodes") or []):
        idx = _find_node(nodes, rm["id"])
        if idx>=0:
            del nodes[idx]
            edges[:] = [e for e in edges if e["source"]!=rm["id"] and e["target"]!=rm["id"]]
            idset.discard(rm["id"])
        else:
            warnings.append(f"remove_nodes: node {rm['id']} not found")

    # 3) add nodes
    for n in (patch.get("add_nodes") or []):
        if n["id"] in idset:
            exist = nodes[_find_node(nodes,n["id"])]
            if json.dumps(exist,sort_keys=True)!=json.dumps(n,sort_keys=True):
                errors.append({"path":f"nodes[{n['id']}]", "reason":"id conflict"})
            else:
                warnings.append(f"add_nodes: node {n['id']} already exists (identical)")
            continue
        nodes.append(n); idset.add(n["id"])

    # 4) add edges
    edge_set = {_edge_key(e) for e in edges}
    for e in (patch.get("add_edges") or []):
        if e["source"] not in idset or e["target"] not in idset:
            errors.append({"path":f"edges[{e}]", "reason":"dangling edge"})
            continue
        k=_edge_key(e)
        if k not in edge_set:
            edges.append({"source":e["source"],"target":e["target"]})
            edge_set.add(k)

    # 5) update nodes
    for up in (patch.get("update_nodes") or []):
        idx = _find_node(nodes, up["id"])
        if idx<0:
            errors.append({"path":f"update_nodes[{up['id']}]", "reason":"node not found"})
            continue
        node = nodes[idx] = copy.deepcopy(nodes[idx])
        # 5.1 shallow set
        for k,v in (up.get("set") or {}).items():
            node[k]=v
        # 5.2 configs patch
        if "configs_patch" in up:
            node.setdefault("configs",{})
            cp = up["configs_patch"] or {}
            for k,v in (cp.get("set") or {}).items():
                node["configs"][k]=v
            for k in (cp.get("unset") or []):
                if k in node["configs"]: del node["configs"][k]
        # 5.3 fieldList patch
        if "fieldList_patch" in up:
            node.setdefault("fieldList",[])
            flp = up["fieldList_patch"] or {}
            # add
            for f in (flp.get("add") or []):
                where = {"dataIndex": f.get("dataIndex") or f.get("__key__")}
                i = _find_field_idx(node["fieldList"], where)
                if i>=0:
                    node["fieldList"][i].update(f)
                    warnings.append(f"fieldList.add->replace {where}")
                else:
                    node["fieldList"].append(f)
            # remove
            for where in (flp.get("remove") or []):
                i = _find_field_idx(node["fieldList"], where)
                if i>=0: node["fieldList"].pop(i)
                else: warnings.append(f"fieldList.remove miss {where}")
            # update
            for upd in (flp.get("update") or []):
                where = upd.get("where") or {}
                i = _find_field_idx(node["fieldList"], where)
                if i>=0:
                    node["fieldList"][i].update(upd.get("set") or {})
                else:
                    warnings.append(f"fieldList.update miss {where}")

    # 6) 去重边
    unique = {}
    for e in edges:
        unique[_edge_key(e)] = e
    g["edges"] = list(unique.values())

    # 7) 校验
    if validate:
        v = validate_graph_simple(g)
        if not v["ok"]:
            errors.extend(v["errors"])

    ok = len(errors)==0
    payload = None
    if ok and not dry_run:
        payload = json.dumps({"nodes": g["nodes"], "edges": g["edges"]}, ensure_ascii=False)

    return {
        "ok": ok,
        "graph_new": g,
        "mcp_payload": payload,
        "errors": errors,
        "warnings": warnings,
        "diff_applied": {k: v for k,v in patch.items() if v}
    }
```
---

## 7. 使用范式

**1) 预演（不落库）**
```python
res = apply_flow_patch(old_graph, patch, dry_run=True)
if not res["ok"]:
    print("Errors:", res["errors"])
    # 返回给前端高亮
```

**2) 真正应用 + MCP 提交**
```python
res = apply_flow_patch(old_graph, patch, dry_run=False)
if res["ok"]:
    mcp.update_graph(graph_id, res["mcp_payload"])  # 以 JSON 字符串传入 MCP
```

---

## 8. 日志与指标（建议）

- `step`: remove_edges / remove_nodes / add_nodes / add_edges / update_nodes / validate  
- `counts`: `{"nodes_old":N1,"nodes_new":N2,"edges_old":E1,"edges_new":E2}`  
- `patch_counts`: 各类操作命中/跳过/冲突数量  
- `payload_bytes`, `duration_ms`  
- `status`: ok / fail（附 errors）

---

## 9. 扩展建议

- **版本并发**：核对 `old_graph.version`，失败则回滚（乐观锁）。  
- **Schema 感知**：结合 `gaia.get_components()` 做更强的节点/字段 schema 校验。  
- **Patch 合并**：多补丁合并与重排，保证拓扑一致。  
- **错误自修复**：引入 LLM Linter 生成 `update_nodes` 细粒度修复建议，再过硬校验。

---

### 一句话总结
`apply_flow_patch` = **幂等的结构化补丁应用器 + Gaia 断言门 + MCP 字符串化出口**。  
它让你能**安全地对图做增量修改**，遵守 GAIA/MCP 的工程约束，还能平滑引入 LLM 的“软优化”。
