# LLM 性能优化方案（高优先级版）

> 目标：把单次 30s 降到 6–10s 的“工程向”优化，**不改业务语义**。先做高优项，其他优化放入后续排期。

---

## 总体策略（高优先）
1. **拆小 + 并发**：按“产品设计”4 个小节并发调用 LLM（墙钟时间≈单段耗时）。
2. **只喂右列**：仅发送 ```grid``` 的右列 `content: |` 文本；左列图片占位/原型等直接丢弃。
3. **强结构输出**：要求 `JSON` 输出（`response_format={"type":"json_object"}`），减少“讲故事”。
4. **限制输出**：`temperature=0`、`max_tokens≤512`、删冗余上下文，缩短生成时间。
5. **本地规则预清洗**：正则/规则提纯维度/指标行，LLM 只做“归类+占位表达式”补齐。

> 先实现以上 5 点；流式早停/缓存/模型路由等列入下一阶段。

---

## 开发清单（按优先级落地）

### 1) 拆小 + 并发
- **做法**：`markdown_to_sections` 切出 4 段（总筛选项/消耗波动详情/素材明细/消耗趋势），用 `asyncio.gather` 并发请求。
- **验收**：日志记录每段耗时及总耗时，墙钟时间明显下降。

```python
# sections: Dict[title, grid_block_markdown]
async def infer_interfaces_concurrently(sections: dict[str, str]) -> list[dict]:
    tasks = [infer_one_section(title, block) for title, block in sections.items()]
    return await asyncio.gather(*tasks)
```

