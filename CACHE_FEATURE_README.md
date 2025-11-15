# 文档缓存功能说明

## 功能概述

新增的本地缓存功能可以显著提升文档处理的性能，通过缓存文档内容的hash值，避免重复调用大模型处理相同的文档。

## 核心特性

### 1. 智能文档缓存
- **基于内容hash**：使用SHA256算法生成文档内容的唯一hash值
- **多文档支持**：支持同时缓存多个文档的组合结果
- **用户意图区分**：相同文档但不同用户意图会分别缓存
- **自动过期管理**：支持设置缓存TTL，自动清理过期缓存

### 2. 缓存层级
- **文档级缓存**：缓存完整的文档处理结果（ISM、计划、工作流等）
- **LLM结果缓存**：缓存单个LLM调用结果（已存在）
- **内存+文件**：双重缓存机制，重启后缓存仍可用

### 3. 性能优化
- **跳过耗时步骤**：缓存命中时直接跳过文档理解、ISM生成、计划编译等步骤
- **处理时间统计**：记录并显示节省的处理时间
- **命中率统计**：提供详细的缓存命中率和性能统计

## 文件结构

```
gaia_ai_doc_backend/
├── utils/
│   └── document_cache.py              # 文档缓存核心实现
├── nodes/
│   └── cache_aware_workflow.py        # 缓存感知工作流节点
├── test_document_cache.py             # 缓存功能测试脚本
├── .env.example.cache                 # 缓存配置示例
└── CACHE_FEATURE_README.md           # 本说明文档
```

## 使用方法

### 1. 环境配置

复制配置文件并根据需要修改：
```bash
cp .env.example.cache .env
```

主要配置项：
```env
# 启用文档缓存功能
ENABLE_DOC_CACHE=true

# 缓存目录
DOC_CACHE_DIR=./cache

# 缓存过期时间（秒）
DOC_CACHE_TTL=86400  # 24小时
```

### 2. 运行应用

启用缓存：
```bash
# 使用缓存感知工作流（默认）
uv run python app.py

# 或显式启用
ENABLE_DOC_CACHE=true uv run python app.py
```

禁用缓存：
```bash
ENABLE_DOC_CACHE=false uv run python app.py
```

### 3. 测试缓存功能

运行专门的缓存测试：
```bash
uv run python test_document_cache.py
```

## 工作流程

### 缓存感知工作流流程：
```
1. cache_aware_entry        - 准备处理，记录开始时间
2. fetch_feishu_doc         - 获取文档内容（必须执行）
3. cache_aware_post_fetch   - 检查缓存，决定是否跳过后续处理
   ├─ 缓存命中 → cache_aware_skip_to_finalize → END
   └─ 缓存未命中 → 继续正常处理流程
4. split_document           - 文档切分
5. understand_doc           - 文档理解（LLM调用）
6. normalize_and_validate_ism - ISM规范化
7. plan_from_ism           - 生成执行计划
8. apply_flow_patch        - 生成工作流
9. cache_aware_finalize    - 存储结果到缓存
```

### 缓存键生成策略：
```python
# 缓存键 = SHA256(标准化文档内容 + 用户意图)
hash_input = combined_content + f"\nINTENT:{user_intent}"
doc_hash = hashlib.sha256(normalized_content.encode('utf-8')).hexdigest()
```

## 性能数据

### 缓存命中时的性能提升：
- **跳过步骤**：文档切分、文档理解、ISM生成、计划编译、工作流生成
- **节省时间**：根据文档复杂度，通常可节省50-90%的处理时间
- **减少LLM调用**：避免重复的大模型API调用

### 示例测试结果：
```
第一次运行（缓存未命中）：
- 文档获取: 120ms
- 文档理解: 2500ms
- ISM生成: 800ms
- 计划编译: 600ms
- 工作流生成: 400ms
- 总计: ~4420ms

第二次运行（缓存命中）：
- 文档获取: 120ms
- 缓存检索: 5ms
- 跳转到结果: 10ms
- 总计: ~135ms

性能提升: 约97%时间节省
```

## 监控和统计

### 获取缓存统计信息：
```python
from utils.document_cache import get_document_cache

cache = get_document_cache()
stats = cache.get_stats()
print(f"总条目数: {stats['total_entries']}")
print(f"命中率: {stats['avg_hits_per_entry']}")
print(f"节省时间: {stats['total_processing_time_saved_seconds']}秒")
print(f"缓存大小: {stats['cache_file_size_mb']}MB")
```

### 查看最近的缓存条目：
```python
entries = cache.list_entries(limit=10)
for entry in entries:
    print(f"{entry['doc_hash']} - {entry['user_intent']} - 命中{entry['hit_count']}次")
```

## 缓存管理

### 手动清理缓存：
```python
from utils.document_cache import get_document_cache

cache = get_document_cache()

# 清理过期缓存
cleaned_count = cache.cleanup_expired()

# 清空所有缓存
cache.clear()
```

### 缓存文件位置：
- 默认目录：`./cache/document_cache.json`
- 文件格式：JSON，包含版本信息、元数据和缓存条目

## 故障排除

### 常见问题：

1. **缓存未命中**
   - 检查文档内容是否完全相同（包括空白字符）
   - 确认用户意图是否一致
   - 验证缓存是否已过期

2. **缓存文件损坏**
   - 删除缓存文件：`rm ./cache/document_cache.json`
   - 重新运行应用自动重建

3. **内存占用过高**
   - 调整TTL设置：`DOC_CACHE_TTL=3600`（1小时）
   - 定期清理过期缓存

### 调试模式：
```bash
# 启用详细日志
LOG_LEVEL=DEBUG uv run python app.py
```

## 最佳实践

1. **合理设置TTL**：根据文档更新频率调整缓存过期时间
2. **监控缓存大小**：定期检查缓存文件大小，避免占用过多磁盘空间
3. **批量处理**：对于批量文档处理，缓存效果更明显
4. **测试验证**：重要部署前先测试缓存命中率和性能提升

## 技术细节

### 缓存条目结构：
```python
@dataclass
class DocumentCacheEntry:
    doc_hash: str                    # 文档内容hash
    feishu_urls: List[str]          # 原始URL列表
    user_intent: str                # 用户意图
    ism_result: Dict[str, Any]      # ISM分析结果
    plan_result: List[dict]         # 执行计划结果
    final_flow_json: str            # 最终工作流JSON
    mcp_payloads: List[dict]        # MCP载荷
    final_response: Dict[str, Any]  # 最终响应
    timestamp: float                # 缓存时间
    hit_count: int                  # 命中次数
    doc_preview: str                # 文档预览
    processing_time_ms: float       # 原处理时间
```

### 原子性保证：
- 使用临时文件+重命名确保缓存写入的原子性
- 避免并发写入导致的数据损坏

### 容错设计：
- 缓存失败不影响正常处理流程
- 支持降级到无缓存模式运行