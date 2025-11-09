#!/usr/bin/env python3
"""
Debug script to test understand_doc_async function
"""

import json
import uuid
from nodes.understand_doc_async import understand_doc
from models.state import AgentState


def test_understand_doc():
    """Test understand_doc function with sample document content"""

    # Sample document content (similar to what fetch_feishu_doc would return)
    sample_content = """
# ROI分析报表需求

## 核心指标

### 1. 公司ROI分析
- **功能**: 展示各公司的ROI数据
- **维度**: 公司ID、公司名称
- **指标**: ROI、消耗、GMV

### 2. 趋势分析
- **功能**: 展示ROI随时间的变化趋势
- **维度**: 时间
- **指标**: ROI、转化率

## 接口定义

### 接口1：公司ROI查询
```
SELECT
    company_id AS 公司ID,
    company_name AS 公司名称,
    roi AS ROI,
    cost AS 消耗,
    gmv AS GMV
FROM roi_data
WHERE date = '2024-01-01'
```

### 接口2：趋势查询
```
SELECT
    date AS 时间,
    roi AS ROI,
    conversion_rate AS 转化率
FROM trend_data
WHERE company_id = '123'
```
"""

    # Create test state
    test_state: AgentState = {
        "raw_docs": [sample_content],
        "feishu_urls": ["https://feishu.cn/test/doc"],
        "trace_id": f"debug-test-{uuid.uuid4().hex[:8]}"
    }

    print("测试 understand_doc_async 函数")
    print("=" * 60)
    print(f"输入状态:")
    print(f"   raw_docs 长度: {len(test_state['raw_docs'][0])} 字符")
    print(f"   trace_id: {test_state['trace_id']}")
    print("-" * 60)

    try:
        # Call understand_doc
        print("调用 understand_doc...")
        result = understand_doc(test_state)

        print("understand_doc 执行成功!")
        print("=" * 60)

        # Check results
        ism_raw = result.get("ism_raw", {})
        print("结果分析:")
        print(f"   ism_raw 存在: {'ism_raw' in result}")
        print(f"   ism_raw 类型: {type(ism_raw)}")

        if isinstance(ism_raw, dict):
            print(f"   doc_meta 存在: {'doc_meta' in ism_raw}")
            print(f"   interfaces 存在: {'interfaces' in ism_raw}")

            if 'interfaces' in ism_raw:
                interfaces = ism_raw['interfaces']
                print(f"   接口数量: {len(interfaces)}")

                for i, interface in enumerate(interfaces):
                    print(f"   接口 {i+1}: {interface.get('name', 'N/A')} ({interface.get('type', 'N/A')})")

            if '__pending__' in ism_raw:
                pending = ism_raw['__pending__']
                print(f"   待处理项: {len(pending)}")
                if pending:
                    print("   待处理项内容:")
                    for item in pending[:3]:  # 只显示前3个
                        print(f"     - {item}")

        print("\n完整 ism_raw:")
        print(json.dumps(ism_raw, ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"understand_doc 执行失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_understand_doc()