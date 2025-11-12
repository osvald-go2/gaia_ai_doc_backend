#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from nodes.fetch_feishu_doc import fetch_feishu_doc
from nodes.split_document import split_document
from nodes.understand_doc_parallel import understand_doc_parallel
from utils.logger import logger

def debug_parsing():
    """Debug the parsing process step by step"""

    # Initial state
    state = {
        "feishu_urls": ["https://ecnjtt87q4e5.feishu.cn/wiki/O2NjwrNDCiRDqMkWJyfcNwd5nXe"],
        "user_intent": "generate_crud",
        "trace_id": "debug-001"
    }

    print("=== Step 1: Fetch Feishu Doc ===")
    state = fetch_feishu_doc(state)
    docs = state.get("raw_docs", [])
    print(f"Fetched {len(docs)} documents")
    for i, doc in enumerate(docs):
        print(f"Doc {i+1}: {len(doc)} chars")
        print(f"Preview: {doc[:200]}...")

    print("\n=== Step 2: Split Document ===")
    state = split_document(state)
    chunks = state.get("doc_chunks", [])
    print(f"Split into {len(chunks)} chunks")

    grid_chunks = []
    for i, chunk in enumerate(chunks):
        has_grid = chunk.get("metadata", {}).get("has_grid", False)
        chunk_type = chunk.get("chunk_type", "unknown")
        content_preview = chunk.get("content", "")[:150]
        print(f"Chunk {i+1} [{chunk_type}] has_grid={has_grid}: {content_preview}...")
        if has_grid:
            grid_chunks.append(chunk)

    print(f"\nFound {len(grid_chunks)} grid chunks")

    # Show full content of grid chunks
    for i, chunk in enumerate(grid_chunks):
        print(f"\n--- Grid Chunk {i+1} Full Content ---")
        print(chunk.get("content", ""))

    print("\n=== Step 3: Understand Doc (Parallel) ===")
    state = understand_doc_parallel(state)

    # Check final results
    ism = state.get("ism", {})
    interfaces = ism.get("interfaces", [])
    print(f"\nFinal result: {len(interfaces)} interfaces")
    for i, interface in enumerate(interfaces):
        name = interface.get("name", "unknown")
        type_name = interface.get("type", "unknown")
        print(f"{i+1}. {name} [{type_name}]")

    # Expected vs actual
    expected = ["总筛选项", "消耗波动详情", "素材明细", "消耗趋势", "交易趋势"]
    interface_names = [iface.get("name", "") for iface in interfaces]

    print(f"\nExpected: {expected}")
    print(f"Got:      {interface_names}")

    found = []
    missing = []
    for exp in expected:
        found_any = any(exp in name or name in exp for name in interface_names)
        if found_any:
            found.append(exp)
        else:
            missing.append(exp)

    print(f"Found: {found}")
    print(f"Missing: {missing}")

    # Check statistics
    stats = ism.get("parsing_statistics", {})
    print(f"\nParsing Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    debug_parsing()