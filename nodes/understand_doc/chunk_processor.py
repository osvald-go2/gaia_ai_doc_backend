"""
文档块处理器
处理不同类型的文档块，包括grid块、普通块的整体理解等
"""

import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

from .config import understand_doc_config
from .interface_extractor import InterfaceExtractor
from utils.logger import logger
from deepseek_client_simple import call_deepseek_llm


class ChunkProcessor:
    """文档块处理器类"""

    def __init__(self, trace_id: str = "", step_name: str = ""):
        self.trace_id = trace_id
        self.step_name = step_name
        self.interface_extractor = InterfaceExtractor(trace_id, step_name)

    def process_grid_chunks_parallel(self, grid_chunks: List[dict]) -> List[dict]:
        """
        并行处理包含grid的块（委托给interface_extractor）
        """
        return self.interface_extractor.process_grid_chunks_parallel(grid_chunks)

    def process_other_chunks_sequential(self, other_chunks: List[dict]) -> List[dict]:
        """
        顺序处理其他非grid块，过滤非功能内容
        """
        interface_results = []

        logger.info(self.trace_id, self.step_name, f"顺序处理 {len(other_chunks)} 个普通块")

        # 预过滤：检查非grid块是否包含功能相关内容
        functional_chunks = self._filter_functional_chunks(other_chunks)

        if not functional_chunks:
            logger.info(self.trace_id, self.step_name, "未发现包含功能内容的普通块，跳过处理")
            return interface_results

        logger.info(self.trace_id, self.step_name, f"过滤后保留 {len(functional_chunks)} 个功能相关块")

        # 合并功能相关的块，进行整体理解
        combined_content = self._combine_chunks_content(functional_chunks)

        if combined_content.strip():
            interface_results = self._understand_general_content(combined_content, functional_chunks)

        logger.info(self.trace_id, self.step_name, f"普通块处理完成: {len(interface_results)} 个接口")
        return interface_results

    def process_all_chunks_for_understanding(self, chunks: List[dict]) -> List[dict]:
        """
        当没有grid块时，对所有块进行整体理解
        """
        interface_results = []

        logger.info(self.trace_id, self.step_name, f"整体理解 {len(chunks)} 个块")

        # 合并所有块内容
        combined_content = self._combine_chunks_content(chunks)

        if combined_content.strip():
            interface_results = self._understand_full_document_content(combined_content, chunks)

        return interface_results

    def process_with_chunks(self, doc_chunks: List[dict], chunk_metadata: dict) -> List[dict]:
        """
        基于文档块的并行处理模式主函数
        """
        logger.info(self.trace_id, self.step_name, f"块处理模式: {len(doc_chunks)} 个块")

        # 详细记录每个块的信息
        self._log_chunk_details(doc_chunks)

        try:
            # 1. 按优先级排序块（grid块优先）
            sorted_chunks = sorted(doc_chunks, key=lambda x: x["metadata"]["processing_priority"])

            # 2. 分类处理
            grid_chunks = [chunk for chunk in sorted_chunks if chunk["metadata"]["has_grid"]]
            non_grid_chunks = [chunk for chunk in sorted_chunks if not chunk["metadata"]["has_grid"]]

            logger.info(self.trace_id, self.step_name, f"块分类: {len(grid_chunks)} 个grid块, {len(non_grid_chunks)} 个普通块")

            interface_results = []

            if grid_chunks:
                # 并行处理grid块
                logger.info(self.trace_id, self.step_name, f"并行处理 {len(grid_chunks)} 个grid块")
                self._log_grid_chunks_info(grid_chunks)

                grid_results = self.process_grid_chunks_parallel(grid_chunks)
                interface_results.extend(grid_results)

            # 处理其他块
            if non_grid_chunks:
                logger.info(self.trace_id, self.step_name, f"处理 {len(non_grid_chunks)} 个普通块")
                other_results = self.process_other_chunks_sequential(non_grid_chunks)
                interface_results.extend(other_results)

            return interface_results

        except Exception as e:
            logger.error(self.trace_id, self.step_name, f"块处理失败: {str(e)}")
            return self._generate_fallback_interfaces(doc_chunks)

    def process_with_raw_docs(self, raw_docs: List[str], feishu_urls: List[str]) -> List[dict]:
        """
        传统文档处理模式
        """
        logger.info(self.trace_id, self.step_name, f"传统模式: {len(raw_docs)} 个文档，{sum(len(doc) for doc in raw_docs)} 字符")

        try:
            # 1. 合并多个文档内容
            combined_content = self._combine_raw_docs(raw_docs)

            # 2. 检查文档中是否有grid块
            grid_blocks = self.interface_extractor.grid_parser.extract_grid_blocks(combined_content)

            if not grid_blocks:
                logger.warning(self.trace_id, self.step_name, "文档中没有发现grid块，生成基础接口")
                return self._generate_basic_interfaces_from_content(combined_content, feishu_urls)

            logger.info(self.trace_id, self.step_name, f"发现 {len(grid_blocks)} 个grid块，开始并行处理")

            # 3. 分割文档为并行处理的块
            chunks = self.interface_extractor.grid_parser.split_document_for_parallel_processing(combined_content)

            logger.info(self.trace_id, self.step_name, f"文档分割为 {len(chunks)} 个块进行并行处理")

            # 4. 并行处理所有块
            all_interfaces = self._process_chunks_parallel(chunks, combined_content)

            logger.info(self.trace_id, self.step_name, f"所有块处理完成，共解析出 {len(all_interfaces)} 个接口")

            return all_interfaces

        except Exception as e:
            logger.error(self.trace_id, self.step_name, f"传统模式处理失败: {str(e)}")
            return self._generate_fallback_interfaces_from_raw_docs(raw_docs, feishu_urls)

    # ==================== 私有辅助方法 ====================

    def _combine_chunks_content(self, chunks: List[dict]) -> str:
        """合并块内容"""
        content_parts = []
        for i, chunk in enumerate(chunks):
            content_parts.append(understand_doc_config.CHUNK_SEPARATOR.format(i + 1, chunk['chunk_type']))
            content_parts.append(chunk["content"])
        return "\n\n".join(content_parts)

    def _combine_raw_docs(self, raw_docs: List[str]) -> str:
        """合并原始文档内容"""
        content_parts = []
        for i, doc in enumerate(raw_docs):
            content_parts.append(understand_doc_config.DOCUMENT_SEPARATOR.format(i + 1))
            content_parts.append(doc)
        return "\n\n".join(content_parts)

    def _log_chunk_details(self, chunks: List[dict]) -> None:
        """记录块详细信息"""
        for i, chunk in enumerate(chunks):
            logger.info(self.trace_id, self.step_name, f"块 {i+1}: {chunk['chunk_type']}, "
                       f"has_grid={chunk['metadata']['has_grid']}, "
                       f"len={len(chunk['content'])} 字符, "
                       f"preview: {chunk['content'][:understand_doc_config.LOG_PREVIEW_LENGTH]}...")

    def _log_grid_chunks_info(self, grid_chunks: List[dict]) -> None:
        """记录grid块信息"""
        for i, chunk in enumerate(grid_chunks):
            logger.info(self.trace_id, self.step_name, f"Grid块 {i+1}: {chunk['chunk_id']}, "
                       f"预览: {chunk['content'][:understand_doc_config.LOG_PREVIEW_LENGTH + 50]}...")

    def _filter_functional_chunks(self, chunks: List[dict]) -> List[dict]:
        """
        过滤出包含功能相关内容的块

        Args:
            chunks: 所有块列表

        Returns:
            过滤后的功能相关块列表
        """
        functional_chunks = []

        for chunk in chunks:
            content = chunk.get("content", "")
            chunk_type = chunk.get("chunk_type", "")

            # 跳过明显的非功能块类型
            if chunk_type in ["header_section", "footer_section", "metadata_section"]:
                if self._is_non_functional_content(content):
                    logger.info(self.trace_id, self.step_name,
                               f"跳过非功能块 {chunk.get('chunk_id', 'unknown')}: {chunk_type}")
                    continue

            # 检查内容是否包含功能相关关键词
            if self._contains_functional_keywords(content):
                functional_chunks.append(chunk)
            else:
                logger.info(self.trace_id, self.step_name,
                           f"跳过无功能内容的块 {chunk.get('chunk_id', 'unknown')}")

        return functional_chunks

    def _is_non_functional_content(self, content: str) -> bool:
        """
        判断内容是否为非功能内容

        Args:
            content: 块内容

        Returns:
            是否为非功能内容
        """
        content_lower = content.lower()

        # 非功能内容关键词
        non_functional_keywords = [
            # 项目背景类
            "项目背景", "产品概述", "业务目标", "需求背景", "用户故事", "业务场景",
            "技术架构", "系统设计", "数据流程", "架构图", "系统图",
            "测试计划", "上线计划", "项目里程碑", "时间计划", "项目排期",
            "团队信息", "联系方式", "会议记录", "项目成员", "角色分工",

            # 文档结构类
            "目录", "索引", "版本历史", "变更记录", "文档说明", "引言",
            "术语解释", "缩略语", "参考文献", "相关文档", "附录",

            # 管理和流程类
            "开发流程", "发布流程", "部署流程", "监控方案", "运维方案",
            "数据治理", "质量保证", "风险管理", "问题跟踪",

            # 文档信息类
            "文档id:", "来源url:", "闭环本地", "产品文档", "需求人员:",
            "meego:", "总图:", "版本:", "更新时间"
        ]

        # 检查是否包含非功能关键词
        for keyword in non_functional_keywords:
            if keyword in content_lower:
                return True

        return False

    def _contains_functional_keywords(self, content: str) -> bool:
        """
        检查内容是否包含功能相关关键词

        Args:
            content: 块内容

        Returns:
            是否包含功能关键词
        """
        content_lower = content.lower()

        # 功能相关关键词
        functional_keywords = [
            # 数据和字段类
            "字段", "field", "参数", "parameter", "属性", "attribute",
            "维度", "dimension", "指标", "metric", "数据", "data",

            # 功能和接口类
            "功能", "function", "接口", "interface", "查询", "query",
            "筛选", "filter", "搜索", "search", "列表", "list",
            "分析", "analysis", "统计", "statistics", "报表", "report",

            # 业务操作类
            "创建", "编辑", "删除", "更新", "新增", "修改", "移除",
            "提交", "审核", "审批", "处理", "执行", "操作",

            # 配置和管理类
            "设置", "配置", "权限", "管理", "控制", "规则",
            "参数", "选项", "属性", "状态", "类型",

            # 业务领域类
            "用户", "订单", "商品", "库存", "支付", "交易",
            "营销", "推广", "广告", "投放", "效果", "转化",

            # 具体的业务对象
            "公司", "门店", "素材", "创意", "活动", "促销",
            "预算", "消耗", "收入", "利润", "成本"
        ]

        # 检查是否包含功能关键词
        for keyword in functional_keywords:
            if keyword in content_lower:
                return True

        # 如果没有明确的功能关键词，但内容较长，可能包含隐藏的功能信息
        # 这里可以添加更复杂的语义分析逻辑
        return len(content.strip()) > 500  # 如果内容很长，可能包含有用信息

    def _understand_general_content(self, combined_content: str, chunks: List[dict]) -> List[dict]:
        """理解一般内容"""
        try:
            # 使用通用提示词进行文档理解
            general_prompt = f"""
你是一个文档理解专家，请分析以下文档内容，识别其中的功能需求、数据结构和业务逻辑。

文档内容：
{combined_content}

请根据内容生成：
1. 如果包含用户界面或数据表格，生成对应的接口定义
2. 如果包含数据模型，生成对应的实体定义
3. 如果包含业务流程，生成对应的操作定义

输出格式要求：
- 返回JSON格式的结果
- 包含interfaces（接口定义）、entities（实体定义）、actions（操作定义）等字段
- 每个接口要有明确的id、name、type、fields等属性
"""

            logger.info(self.trace_id, self.step_name, f"调用LLM理解普通块")

            result = call_deepseek_llm(
                system_prompt=understand_doc_config.GENERAL_SYSTEM_PROMPT,
                user_prompt=general_prompt,
                model=understand_doc_config.DEFAULT_MODEL,
                temperature=understand_doc_config.DEFAULT_TEMPERATURE,
                max_tokens=understand_doc_config.get_max_tokens_by_task("general_understanding")
            )

            # 记录LLM返回结果
            logger.info(self.trace_id, self.step_name, f"LLM返回: {result[:understand_doc_config.LOG_RESULT_PREVIEW_LENGTH]}...")

            # 解析LLM返回结果
            try:
                parsed_result = json.loads(result.strip())
                interfaces_count = len(parsed_result.get("interfaces", []))
                logger.info(self.trace_id, self.step_name, f"普通块解析成功: {interfaces_count} 个接口")

                # 转换为标准接口格式
                interface_results = []
                if "interfaces" in parsed_result:
                    for interface in parsed_result["interfaces"]:
                        interface["source_chunk_ids"] = [chunk["chunk_id"] for chunk in chunks]
                        interface["source_method"] = "sequential_understanding"
                        interface_results.append(interface)

                return interface_results

            except json.JSONDecodeError:
                logger.warn(self.trace_id, self.step_name, f"JSON解析失败，使用基础理解")
                return self._generate_basic_interfaces_from_chunks(chunks)

        except Exception as e:
            logger.error(self.trace_id, self.step_name, f"普通块LLM调用失败: {str(e)}")
            return self._generate_basic_interfaces_from_chunks(chunks)

    def _understand_full_document_content(self, combined_content: str, chunks: List[dict]) -> List[dict]:
        """理解完整文档内容"""
        try:
            # 使用针对非grid文档的提示词
            user_prompt = f"""
请分析以下文档内容，提取其中的业务需求和数据模型。

文档内容：
{combined_content}

分析要求：
1. 识别文档中的业务实体（如用户表、订单表等）
2. 识别业务操作（如增删改查、导出报表等）
3. 提取字段定义和类型信息
4. 生成对应的接口和实体定义

请返回JSON格式，包含：
- interfaces: 接口定义列表
- entities: 实体定义列表
- actions: 操作定义列表

每个接口需要包含：
- id: 唯一标识
- name: 中文名称
- type: 接口类型（crud/analytics/export等）
- fields: 字段定义列表
- operations: 支持的操作列表
"""

            logger.info(self.trace_id, self.step_name, f"调用LLM整体理解")

            result = call_deepseek_llm(
                system_prompt=understand_doc_config.BUSINESS_ANALYST_PROMPT,
                user_prompt=user_prompt,
                model=understand_doc_config.DEFAULT_MODEL,
                temperature=understand_doc_config.DEFAULT_TEMPERATURE,
                max_tokens=understand_doc_config.get_max_tokens_by_task("full_document")
            )

            # 记录LLM返回结果
            logger.info(self.trace_id, self.step_name, f"LLM返回: {result[:understand_doc_config.LOG_RESULT_PREVIEW_LENGTH]}...")

            # 解析LLM返回结果
            try:
                parsed_result = json.loads(result.strip())
                interfaces_count = len(parsed_result.get("interfaces", []))
                entities_count = len(parsed_result.get("entities", []))
                logger.info(self.trace_id, self.step_name, f"整体理解成功: {interfaces_count} 个接口，{entities_count} 个实体")

                # 处理接口定义
                interface_results = []
                if "interfaces" in parsed_result:
                    for interface in parsed_result["interfaces"]:
                        interface["source_chunk_ids"] = [chunk["chunk_id"] for chunk in chunks]
                        interface["source_method"] = "full_document_understanding"
                        interface_results.append(interface)

                return interface_results

            except json.JSONDecodeError:
                logger.warn(self.trace_id, self.step_name, f"JSON解析失败，使用基础理解")
                return self._generate_basic_interfaces_from_chunks(chunks)

        except Exception as e:
            logger.error(self.trace_id, self.step_name, f"整体理解失败: {str(e)}")
            return self._generate_basic_interfaces_from_chunks(chunks)

    def _process_chunks_parallel(self, chunks: List[str], combined_content: str) -> List[dict]:
        """并行处理文档块"""
        all_interfaces = []
        with ThreadPoolExecutor(max_workers=understand_doc_config.PARALLEL_MAX_WORKERS) as executor:
            future_to_chunk = {
                executor.submit(self.interface_extractor.parse_interfaces_chunk, chunk, i, combined_content): (chunk, i)
                for i, chunk in enumerate(chunks)
            }

            for future in as_completed(future_to_chunk):
                chunk, chunk_index = future_to_chunk[future]
                try:
                    interfaces = future.result(timeout=understand_doc_config.CHUNK_TIMEOUT)
                    all_interfaces.extend(interfaces)
                    logger.info(self.trace_id, self.step_name, f"块 {chunk_index} 处理完成，解析出 {len(interfaces)} 个接口")
                except Exception as e:
                    logger.error(self.trace_id, self.step_name, f"块 {chunk_index} 处理失败: {str(e)}")
                    # 添加失败信息到pending
                    all_interfaces.append({
                        "error": f"块处理失败: {str(e)}",
                        "_block_index": chunk_index * 100,
                        "_grid_content": chunk[:understand_doc_config.MAX_CHUNK_SIZE] + "..." if len(chunk) > understand_doc_config.MAX_CHUNK_SIZE else chunk,
                        "source_method": "parallel_processing_error"
                    })

        return all_interfaces

    def _generate_basic_interfaces_from_chunks(self, chunks: List[dict]) -> List[dict]:
        """从块生成基础接口（降级方案）"""
        # 检查是否包含用户表相关信息
        combined_content = " ".join([chunk["content"] for chunk in chunks])

        if "用户表" in combined_content or "users" in combined_content.lower():
            return [
                {
                    "id": f"{understand_doc_config.INTERFACE_ID_PREFIX}users_{uuid.uuid4().hex[:8]}",
                    "name": "用户管理接口",
                    "type": "crud",
                    "description": "用户信息的管理接口",
                    "fields": [
                        {"name": "id", "type": "string", "required": True, "description": "用户ID"},
                        {"name": "name", "type": "string", "required": False, "description": "用户姓名"},
                        {"name": "channel", "type": "string", "required": False, "description": "渠道"}
                    ],
                    "operations": understand_doc_config.CRUD_OPERATIONS.copy(),
                    "source_chunk_ids": [chunk["chunk_id"] for chunk in chunks],
                    "source_method": "basic_fallback"
                }
            ]
        else:
            return [
                {
                    "id": f"{understand_doc_config.INTERFACE_ID_PREFIX}basic_{uuid.uuid4().hex[:8]}",
                    "name": "基础接口",
                    "type": "custom",
                    "description": "从文档内容生成的基础接口",
                    "fields": understand_doc_config.DEFAULT_FIELDS.copy(),
                    "operations": understand_doc_config.DEFAULT_OPERATIONS.copy(),
                    "source_chunk_ids": [chunk["chunk_id"] for chunk in chunks],
                    "source_method": "basic_fallback"
                }
            ]

    def _generate_basic_interfaces_from_content(self, content: str, feishu_urls: List[str]) -> List[dict]:
        """从内容生成基础接口"""
        if "用户表" in content:
            return [
                {
                    "id": f"{understand_doc_config.INTERFACE_ID_PREFIX}users_{uuid.uuid4().hex[:8]}",
                    "name": "用户管理CRUD",
                    "type": "crud",
                    "description": "用户信息的增删改查操作",
                    "target_entity": "users",
                    "fields": [
                        {"name": "id", "type": "string", "required": True, "description": "用户ID，主键"},
                        {"name": "name", "type": "string", "required": False, "description": "用户姓名"},
                        {"name": "channel", "type": "string", "required": False, "description": "渠道"}
                    ],
                    "operations": understand_doc_config.CRUD_OPERATIONS.copy(),
                    "source_method": "content_based_fallback"
                }
            ]
        else:
            return [
                {
                    "id": f"{understand_doc_config.INTERFACE_ID_PREFIX}basic_{uuid.uuid4().hex[:8]}",
                    "name": "基础接口",
                    "type": "custom",
                    "description": "从文档内容生成的基础接口",
                    "fields": understand_doc_config.DEFAULT_FIELDS.copy(),
                    "operations": understand_doc_config.DEFAULT_OPERATIONS.copy(),
                    "source_method": "content_based_fallback"
                }
            ]

    def _generate_fallback_interfaces(self, doc_chunks: List[dict]) -> List[dict]:
        """生成降级接口"""
        fallback_interfaces = []
        for chunk in doc_chunks:
            fallback_interface = {
                "id": f"{understand_doc_config.INTERFACE_ID_PREFIX}fallback_{chunk.get('chunk_id', 'unknown')}",
                "name": f"降级接口_{chunk.get('chunk_type', 'unknown')}",
                "type": "fallback",
                "description": f"从{chunk.get('chunk_type', 'unknown')}类型块生成的降级接口",
                "fields": understand_doc_config.DEFAULT_FIELDS.copy(),
                "operations": understand_doc_config.DEFAULT_OPERATIONS.copy(),
                "source_chunk_id": chunk.get("chunk_id", "unknown"),
                "source_chunk_type": chunk.get("chunk_type", "unknown"),
                "source_method": "chunk_processing_fallback"
            }
            fallback_interfaces.append(fallback_interface)

        return fallback_interfaces

    def _generate_fallback_interfaces_from_raw_docs(self, raw_docs: List[str], feishu_urls: List[str]) -> List[dict]:
        """从原始文档生成降级接口"""
        combined_content = self._combine_raw_docs(raw_docs)
        return self._generate_basic_interfaces_from_content(combined_content, feishu_urls)


def create_chunk_processor(trace_id: str = "", step_name: str = "") -> ChunkProcessor:
    """
    创建文档块处理器实例
    """
    return ChunkProcessor(trace_id, step_name)