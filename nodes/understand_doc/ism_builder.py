"""
ISM构建器
将接口提取结果构建为完整的ISM（Intermediate Semantic Model）结构
"""

import uuid
import json
from typing import List, Dict, Any, Optional

from .config import understand_doc_config
from utils.logger import logger


class ISMBuilder:
    """ISM构建器类"""

    def __init__(self, trace_id: str = "", step_name: str = ""):
        self.trace_id = trace_id
        self.step_name = step_name

    def merge_interfaces_to_ism(self, interfaces: List[Dict[str, Any]], doc_meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        将多个接口定义合并为完整的ISM结构
        """
        ism = {
            "doc_meta": doc_meta,
            "interfaces": [],
            "__pending__": []
        }

        # 成功解析的接口
        successful_interfaces = []

        # 失败和待处理的项
        pending_items = []

        for interface in interfaces:
            if "error" in interface:
                # 处理失败的接口
                pending_items.append(f"接口解析失败 (Block {interface.get('_block_index', 'unknown')}): {interface['error']}")
                if '_grid_content' in interface:
                    pending_items.append(f"原始内容: {interface['_grid_content'][:200]}...")
            elif not interface.get("id"):
                # 缺少必要字段的接口
                pending_items.append(f"接口缺少ID (Block {interface.get('_block_index', 'unknown')})")
                if '_grid_content' in interface:
                    pending_items.append(f"原始内容: {interface['_grid_content'][:200]}...")
            else:
                # 成功的接口，清理内部元数据
                clean_interface = {k: v for k, v in interface.items()
                                 if not k.startswith('_') and k != "error"}
                successful_interfaces.append(clean_interface)

        # 按block_index排序接口
        successful_interfaces.sort(key=lambda x: x.get('_block_index', 0))

        # 清理接口中的排序字段
        for interface in successful_interfaces:
            interface.pop('_block_index', None)

        ism["interfaces"] = successful_interfaces
        ism["__pending__"] = pending_items

        return ism

    def build_ism_from_chunk_results(self, interface_results: List[dict], doc_meta: dict, chunks: List[dict]) -> dict:
        """
        从块处理结果构建最终的ISM
        """
        logger.info(self.trace_id, self.step_name, f"构建ISM: {len(interface_results)} 个接口")

        # 首先处理数组响应，提取所有接口
        expanded_interfaces = self._expand_array_responses(interface_results)
        logger.info(self.trace_id, self.step_name, f"数组响应展开后: {len(expanded_interfaces)} 个接口")

        # 标准化接口数据并应用智能去重
        standardized_interfaces = []
        entities = []
        seen_interfaces = {}  # 用于去重的字典 {key: interface}
        similar_interfaces = {}  # 用于处理相似接口 {name_key: list_of_interfaces}

        for interface in expanded_interfaces:
            # 确保接口有必需的字段
            standardized_interface = self._standardize_interface(interface)

            # **新增：过滤无效的接口类型**
            if not self._is_valid_interface_type(standardized_interface.get("type", "")):
                logger.warn(self.trace_id, self.step_name,
                            f"跳过无效接口类型的接口: {standardized_interface.get('name', '未知')} "
                            f"[类型: {standardized_interface.get('type')}]")
                continue

            # **新增：过滤纯元数据接口（如文档头部信息）**
            if self._is_metadata_interface(standardized_interface):
                logger.info(self.trace_id, self.step_name,
                           f"跳过元数据接口: {standardized_interface.get('name', '未知')}")
                continue

            # 生成主要去重键
            interface_key = self._create_interface_key(standardized_interface)

            # 生成名称相似性键（用于处理变体）
            name_key = self._normalize_interface_name(standardized_interface.get("name", ""))

            if interface_key in seen_interfaces:
                # 精确匹配，直接合并
                existing = seen_interfaces[interface_key]
                self._merge_duplicate_interfaces(existing, standardized_interface, self.trace_id, self.step_name)

            elif name_key in similar_interfaces:
                # 名称相似但不完全相同，检查是否应该合并
                should_merge = self._should_merge_similar_interfaces(
                    similar_interfaces[name_key], standardized_interface
                )

                if should_merge:
                    # 合并到现有的相似接口
                    existing = similar_interfaces[name_key]
                    self._merge_duplicate_interfaces(existing, standardized_interface, self.trace_id, self.step_name)
                else:
                    # 不合并，添加为新接口
                    seen_interfaces[interface_key] = standardized_interface
                    standardized_interfaces.append(standardized_interface)
                    similar_interfaces[name_key] = standardized_interface

            else:
                # 新接口，添加到所有映射中
                seen_interfaces[interface_key] = standardized_interface
                standardized_interfaces.append(standardized_interface)
                similar_interfaces[name_key] = standardized_interface

        logger.info(self.trace_id, self.step_name,
                   f"去重完成: {len(expanded_interfaces)} -> {len(standardized_interfaces)} 个接口")

        # 基于去重后的接口创建实体
        entities = self._create_entities_from_interfaces(standardized_interfaces)

        # 构建最终ISM
        final_ism = self._build_final_ism(standardized_interfaces, entities, doc_meta, chunks)

        # 详细的构建完成日志
        array_responses_count = len([iface for iface in standardized_interfaces if iface.get("_array_response")])
        logger.info(self.trace_id, self.step_name,
                   f"ISM构建完成: {len(standardized_interfaces)} 个接口, {len(entities)} 个实体 "
                   f"[数组响应: {array_responses_count}, 去重前: {len(expanded_interfaces)}]")

        # 记录接口统计
        interface_types = {}
        for interface in standardized_interfaces:
            itype = interface.get("type", "unknown")
            interface_types[itype] = interface_types.get(itype, 0) + 1

        logger.info(self.trace_id, self.step_name, f"接口类型分布: {interface_types}")

        return final_ism

    def build_doc_meta(self, feishu_urls: List[str], chunks: List[dict] = None, chunk_metadata: dict = None,
                      parsing_mode: str = None, title: str = None) -> dict:
        """
        构建文档元数据
        """
        # 提取主要URL
        primary_feishu_url = feishu_urls[0] if feishu_urls else ""

        doc_meta = {
            "title": title or "解析文档",
            "url": primary_feishu_url,
            "version": "latest",
            "parsing_mode": parsing_mode or understand_doc_config.PARSING_MODE_PARALLEL
        }

        # 添加多URL信息
        if len(feishu_urls) > 1:
            doc_meta["source_urls"] = feishu_urls
            doc_meta["source_count"] = len(feishu_urls)

        # 添加块处理信息
        if chunks:
            doc_meta["total_chunks"] = len(chunks)
            doc_meta["chunks_with_grid"] = len([c for c in chunks if c.get("metadata", {}).get("has_grid", False)])

        if chunk_metadata:
            doc_meta["chunking_strategy"] = chunk_metadata.get("chunking_strategy", {})

        return doc_meta

    def generate_basic_ism(self, state: dict, combined_content: str) -> dict:
        """
        生成基础的ISM结构（当没有grid块时使用）
        """
        trace_id = state.get("trace_id", "")
        step_name = "understand_doc"
        user_intent = state.get("user_intent", "generate_crud")
        feishu_urls = state.get("feishu_urls", [])

        logger.info(trace_id, step_name, "生成基础ISM结构",
                    extra={"content_length": len(combined_content), "user_intent": user_intent})

        # 根据用户意图生成基础的实体和接口
        interfaces, entities = self._generate_basic_interfaces_and_entities(user_intent, combined_content, feishu_urls)

        # 构建基础ISM
        basic_ism = {
            "doc_meta": {
                "title": "基础生成的文档",
                "url": feishu_urls[0] if feishu_urls else "",
                "version": "latest",
                "parsing_mode": understand_doc_config.PARSING_MODE_BASIC,
                "content_length": len(combined_content)
            },
            "interfaces": interfaces,
            "entities": entities,
            "actions": [],
            "views": [],
            "__generation_method": "basic_fallback"
        }

        logger.end(trace_id, step_name, f"基础ISM生成完成: {len(interfaces)} 个接口，{len(entities)} 个实体")

        return basic_ism

    def generate_fallback_ism(self, state: dict, error_msg: str) -> dict:
        """
        生成兜底ISM（出错时使用）
        """
        feishu_urls = state.get("feishu_urls", [])

        fallback_ism = {
            "doc_meta": {
                "title": "解析失败的文档",
                "url": feishu_urls[0] if feishu_urls else "",
                "version": "latest",
                "parsing_mode": understand_doc_config.PARSING_MODE_ERROR,
                "error": error_msg
            },
            "interfaces": [],
            "entities": [],
            "actions": [],
            "views": [],
            "__pending__": [f"文档理解发生错误: {error_msg}"],
            "__key": f"error_{hash(error_msg) % 1000:03d}"
        }

        logger.error(state.get("trace_id", ""), "understand_doc", f"生成兜底ISM: {error_msg}")

        return fallback_ism

    def _expand_array_responses(self, interface_results: List[dict]) -> List[dict]:
        """
        展开数组响应，将包含多个接口的数组拆分为单独的接口

        Args:
            interface_results: 原始接口结果列表

        Returns:
            展开后的接口列表
        """
        expanded_interfaces = []

        for interface in interface_results:
            if interface.get("_array_response") and interface.get("_array_data"):
                # 处理数组响应
                array_data = interface["_array_data"]
                logger.info(self.trace_id, self.step_name, f"展开数组响应: {len(array_data)} 个接口")

                for i, array_interface in enumerate(array_data):
                    # 为数组中的每个接口创建独立的记录
                    expanded_interface = array_interface.copy()

                    # 保留原始元数据
                    expanded_interface.update({
                        "source_chunk_id": interface.get("source_chunk_id", ""),
                        "source_chunk_type": interface.get("source_chunk_type", ""),
                        "source_method": f"{interface.get('source_method', '')}_array_item_{i}",
                        "_array_response": True,
                        "_array_index": i,
                        "_original_array": interface.get("_array_data", [])
                    })

                    # 确保有唯一ID
                    if not expanded_interface.get("id"):
                        chunk_id = interface.get("source_chunk_id", "unknown")
                        expanded_interface["id"] = f"interface_{chunk_id}_array_{i}"

                    expanded_interfaces.append(expanded_interface)

                logger.info(self.trace_id, self.step_name, f"数组响应展开完成: {len(array_data)} -> {len(expanded_interfaces)}")
            else:
                # 非数组响应，直接添加
                expanded_interfaces.append(interface)

        return expanded_interfaces

    def _create_interface_key(self, interface: dict) -> str:
        """
        创建接口的唯一键，专注于功能而非实现细节

        Args:
            interface: 接口数据

        Returns:
            接口的唯一键
        """
        # 标准化接口名称
        name = interface.get("name", "").strip()

        # 接口类型标准化，使用主要功能类型
        interface_type = self._normalize_interface_type(interface.get("type", ""))

        # 对于数组响应，忽略索引，专注于功能
        # 相同名称的接口应该合并，而不是被索引区分
        normalized_name = self._normalize_interface_name(name)

        # 生成基于功能的键，忽略字段差异
        return f"{normalized_name}_{interface_type}"

    def _normalize_interface_name(self, name: str) -> str:
        """
        标准化接口名称，消除同义词和变体

        Args:
            name: 原始接口名称

        Returns:
            标准化后的名称
        """
        name_lower = name.lower().strip()

        # 接口名称标准化映射
        name_mappings = {
            # 筛选类
            "总筛选项": "total_filter",
            "筛选条件": "filter_condition",
            "查询条件": "query_condition",
            "过滤器": "filter",

            # 消耗类
            "消耗趋势": "consumption_trend",
            "消耗波动": "consumption_fluctuation",
            "消耗波动详情": "consumption_fluctuation_detail",
            "广告消耗": "ad_consumption",

            # 交易类
            "交易趋势": "transaction_trend",
            "成交趋势": "transaction_trend",
            "订单趋势": "order_trend",

            # 明细类
            "素材明细": "material_detail",
            "数据明细": "data_detail",
            "列表详情": "list_detail",

            # 通用映射
            "分析": "analysis",
            "统计": "statistics",
            "报表": "report",
            "列表": "list"
        }

        # 精确匹配
        if name_lower in name_mappings:
            return name_mappings[name_lower]

        # 模糊匹配
        for pattern, standard_name in name_mappings.items():
            if pattern in name_lower or name_lower in pattern:
                return standard_name

        # 如果没有匹配，使用清理后的名称
        return name_lower.replace(" ", "_").replace("-", "_")

    def _normalize_interface_type(self, interface_type: str) -> str:
        """
        标准化接口类型

        Args:
            interface_type: 原始接口类型

        Returns:
            标准化后的类型
        """
        type_lower = interface_type.lower().strip()

        # 类型映射
        type_mappings = {
            "filter_dimension": "filter",
            "data_display": "data",
            "trend_analysis": "trend",
            "analytics_metric": "metric",
            "export_report": "export",
            "custom_action": "action",
            "crud": "crud",
            "fallback": "fallback",
            "emergency": "emergency",
            "custom": "custom",
            "unknown": "unknown"
        }

        return type_mappings.get(type_lower, "custom")

    # ==================== 私有辅助方法 ====================

    def _standardize_interface(self, interface: dict) -> dict:
        """标准化接口数据"""
        standardized_interface = {
            "id": interface.get("id", f"{understand_doc_config.INTERFACE_ID_PREFIX}{uuid.uuid4().hex[:8]}"),
            "name": interface.get("name", "未命名接口"),
            "type": interface.get("type", "custom"),
            "description": interface.get("description", ""),
            "fields": interface.get("fields", []),
            "operations": interface.get("operations", understand_doc_config.DEFAULT_OPERATIONS.copy()),
            "source_chunk_ids": interface.get("source_chunk_ids", []),
            "source_method": interface.get("source_method", "unknown"),
            "source_chunk_id": interface.get("source_chunk_id", ""),
            "source_chunk_type": interface.get("source_chunk_type", "")
        }

        # 标准化字段
        for field in standardized_interface["fields"]:
            if "data_type" not in field:
                field["data_type"] = "string"
            if "required" not in field:
                field["required"] = False
            if "description" not in field:
                field["description"] = field.get("name", "")

        return standardized_interface

    def _merge_duplicate_interfaces(self, existing: dict, new_interface: dict, trace_id: str, step_name: str) -> None:
        """
        智能合并重复或相似的接口
        优先保留质量更高的接口信息
        """
        # 记录合并信息
        array_info = ""
        if new_interface.get("_array_response"):
            array_info = f" (数组响应, 索引: {new_interface.get('_array_index', 'unknown')})"

        logger.info(trace_id, step_name,
                   f"合并相似接口: {new_interface['name']}{array_info} "
                   f"[来源: {new_interface.get('source_method', 'unknown')}]")

        # 智能字段合并
        existing_fields = existing.get("fields", [])
        new_fields = new_interface.get("fields", [])

        # 合并并去重字段，优先保留更完整的字段信息
        merged_fields = self._merge_interface_fields(existing_fields, new_fields)
        existing["fields"] = merged_fields

        # 合并操作，确保所有必要的操作都被保留
        existing_ops = set(existing.get("operations", []))
        new_ops = set(new_interface.get("operations", []))
        existing["operations"] = list(existing_ops.union(new_ops))

        # 优先选择更好的描述（非fallback > fallback，更详细的 > 更简短的）
        existing_desc = existing.get("description", "")
        new_desc = new_interface.get("description", "")

        if self._is_better_description(new_desc, existing_desc):
            existing["description"] = new_desc
            logger.info(trace_id, step_name, f"更新接口 {new_interface['name']} 的描述")

        # 优先选择非fallback的接口类型和ID
        if not self._is_fallback_interface(existing) and self._is_fallback_interface(new_interface):
            # 现有接口更好，保持不变
            pass
        elif self._is_fallback_interface(existing) and not self._is_fallback_interface(new_interface):
            # 新接口更好，更新关键信息
            existing["id"] = new_interface.get("id", existing["id"])
            existing["type"] = new_interface.get("type", existing["type"])
            existing["name"] = new_interface.get("name", existing["name"])
            logger.info(trace_id, step_name, f"更新接口 {new_interface['name']} 的主要信息")

        # 合并源块信息
        existing_chunk_ids = existing.get("source_chunk_ids", [])
        new_chunk_ids = new_interface.get("source_chunk_ids", [])
        if new_chunk_ids:
            existing_chunk_ids.extend(new_chunk_ids)
            existing["source_chunk_ids"] = list(set(existing_chunk_ids))

        # 更新来源方法（记录多个来源）
        existing_method = existing.get("source_method", "")
        new_method = new_interface.get("source_method", "")
        if new_method and new_method != existing_method:
            # 记录多个来源方法
            if "," in existing_method:
                existing["source_method"] = f"{existing_method}, {new_method}"
            else:
                existing["source_method"] = f"{existing_method}, {new_method}"

    def _merge_interface_fields(self, existing_fields: List[dict], new_fields: List[dict]) -> List[dict]:
        """
        智能合并接口字段
        """
        field_map = {}  # {field_name_lower: best_field}

        # 首先处理现有字段
        for field in existing_fields:
            name = field.get("name", "").strip().lower()
            if name:
                field_map[name] = field

        # 处理新字段，可能覆盖或添加
        for field in new_fields:
            name = field.get("name", "").strip().lower()
            if not name:
                continue

            if name in field_map:
                # 合并字段信息，优先选择更完整的
                existing_field = field_map[name]
                field_map[name] = self._merge_single_field(existing_field, field)
            else:
                # 新字段
                field_map[name] = field

        return list(field_map.values())

    def _merge_single_field(self, existing_field: dict, new_field: dict) -> dict:
        """
        合并单个字段，选择更好的信息
        """
        merged = existing_field.copy()

        # 优先选择非空的字段信息
        for key in ["data_type", "expression", "description"]:
            existing_value = existing_field.get(key, "")
            new_value = new_field.get(key, "")

            if new_value and not existing_value:
                merged[key] = new_value
            elif new_value and len(new_value) > len(existing_value):
                merged[key] = new_value

        # 合并required状态（如果任何一个为true，则为true）
        existing_required = existing_field.get("required", False)
        new_required = new_field.get("required", False)
        merged["required"] = existing_required or new_required

        return merged

    def _is_better_description(self, new_desc: str, existing_desc: str) -> bool:
        """
        判断新描述是否更好
        """
        if not new_desc:
            return False

        if not existing_desc:
            return True

        # 优先选择非fallback描述
        if "降级" in existing_desc and "降级" not in new_desc:
            return True

        # 优先选择更详细的描述
        return len(new_desc) > len(existing_desc) * 1.2

    def _is_fallback_interface(self, interface: dict) -> bool:
        """
        判断是否为降级接口
        """
        interface_type = interface.get("type", "").lower()
        source_method = interface.get("source_method", "").lower()
        interface_id = interface.get("id", "").lower()

        return (interface_type in ["fallback", "emergency"] or
                "fallback" in source_method or
                "emergency" in source_method or
                "fallback" in interface_id or
                "emergency" in interface_id)

    def _should_merge_similar_interfaces(self, existing: dict, new_interface: dict) -> bool:
        """
        判断两个相似接口是否应该合并

        Args:
            existing: 已存在的接口
            new_interface: 新接口

        Returns:
            是否应该合并
        """
        # 如果名称完全相同，应该合并
        existing_name = existing.get("name", "").strip().lower()
        new_name = new_interface.get("name", "").strip().lower()

        if existing_name == new_name:
            return True

        # 检查是否为预期的接口变体
        expected_variants = {
            "total_filter": ["总筛选项", "筛选条件", "过滤器"],
            "consumption_trend": ["消耗趋势", "消耗波动", "消耗波动详情"],
            "transaction_trend": ["交易趋势", "成交趋势", "订单趋势"],
            "material_detail": ["素材明细", "数据明细", "列表详情"]
        }

        # 标准化两个接口的名称
        existing_normalized = self._normalize_interface_name(existing_name)
        new_normalized = self._normalize_interface_name(new_name)

        # 如果标准化后相同，应该合并
        if existing_normalized == new_normalized:
            return True

        # 检查是否属于同一变体组
        for variant_group in expected_variants.values():
            if (existing_name in variant_group or existing_normalized in variant_group) and \
               (new_name in variant_group or new_normalized in variant_group):
                return True

        # 检查接口类型相似性和字段重叠度
        if self._have_similar_functionality(existing, new_interface):
            logger.info(self.trace_id, self.step_name,
                       f"基于功能相似性合并接口: {existing_name} + {new_name}")
            return True

        return False

    def _have_similar_functionality(self, iface1: dict, iface2: dict) -> bool:
        """
        检查两个接口是否具有相似的功能

        Args:
            iface1: 接口1
            iface2: 接口2

        Returns:
            是否具有相似功能
        """
        # 检查接口类型
        type1 = self._normalize_interface_type(iface1.get("type", ""))
        type2 = self._normalize_interface_type(iface2.get("type", ""))

        # 如果类型不同，不太可能相似
        if type1 != type2:
            return False

        # 检查字段重叠度
        fields1 = {f.get("name", "").lower() for f in iface1.get("fields", []) if f.get("name")}
        fields2 = {f.get("name", "").lower() for f in iface2.get("fields", []) if f.get("name")}

        # 如果都有字段，计算重叠度
        if fields1 and fields2:
            intersection = fields1.intersection(fields2)
            union = fields1.union(fields2)
            overlap_ratio = len(intersection) / len(union) if union else 0

            # 如果字段重叠度超过50%，认为是相似功能
            if overlap_ratio > 0.5:
                logger.debug(self.trace_id, self.step_name,
                           f"字段重叠度: {overlap_ratio:.2f}, 判定为相似功能")
                return True

        # 检查名称相似性（基于关键词）
        name1 = iface1.get("name", "").lower()
        name2 = iface2.get("name", "").lower()

        # 共同关键词检查
        common_keywords = ["趋势", "分析", "统计", "明细", "列表", "筛选", "查询"]
        for keyword in common_keywords:
            if keyword in name1 and keyword in name2:
                return True

        # 模糊匹配（简单的编辑距离）
        if self._names_are_similar(name1, name2):
            return True

        return False

    def _names_are_similar(self, name1: str, name2: str) -> bool:
        """
        简单的名称相似性检查

        Args:
            name1: 名称1
            name2: 名称2

        Returns:
            是否相似
        """
        if len(name1) == 0 or len(name2) == 0:
            return False

        # 简单的相似性检查：如果一个名称包含另一个名称的大部分内容
        shorter, longer = (name1, name2) if len(name1) <= len(name2) else (name2, name1)

        # 如果短名称长度小于2，不比较
        if len(shorter) < 2:
            return False

        # 检查短名称是否在长名称中
        if shorter in longer:
            return True

        # 检查是否有超过50%的字符匹配
        common_chars = set(shorter) & set(longer)
        similarity = len(common_chars) / len(set(shorter + longer))

        return similarity > 0.5

    def _is_valid_interface_type(self, interface_type: str) -> bool:
        """
        检查接口类型是否有效

        Args:
            interface_type: 接口类型

        Returns:
            是否为有效类型
        """
        if not interface_type:
            return False

        # 使用配置中的有效类型检查
        return understand_doc_config.is_valid_interface_type(interface_type)

    def _is_metadata_interface(self, interface: dict) -> bool:
        """
        检查是否为元数据接口（文档头部、配置信息等）

        Args:
            interface: 接口数据

        Returns:
            是否为元数据接口
        """
        interface_name = interface.get("name", "").lower()
        interface_type = interface.get("type", "").lower()
        interface_id = interface.get("id", "").lower()
        description = interface.get("description", "").lower()

        # 严格的元数据接口关键词（只匹配真正的元数据概念）
        strict_metadata_keywords = [
            "文档头部", "文档信息", "元数据", "文档metadata", "document header",
            "document info", "文档overview", "文档introduction"
        ]

        # 检查是否匹配严格的元数据关键词
        for keyword in strict_metadata_keywords:
            if (keyword in interface_name or
                keyword in interface_type or
                keyword in interface_id or
                keyword in description):
                return True

        # 特殊情况：检查是否为文档相关信息（更严格的匹配）
        document_indicators = [
            "文档id", "doc_id", "source", "url", "背景", "概述", "介绍",
            "documentid", "docid", "sourceurl", "background", "overview", "introduction"
        ]

        # 只有在明确包含文档相关信息时才标记为元数据
        document_matches = 0
        for indicator in document_indicators:
            if indicator in interface_id or indicator in description:
                document_matches += 1

        # 如果有多个文档指标匹配，认为是元数据接口
        if document_matches >= 2:
            return True

        # 特殊处理：检查接口类型是否明显是元数据类型
        metadata_only_types = ["info", "metadata", "document", "header"]
        if interface_type in metadata_only_types:
            return True

        # 避免误判：如果包含明显的业务关键词，即使有"信息"、"配置"等词也不算元数据
        business_keywords = [
            "筛选", "查询", "列表", "分析", "统计", "报表", "导出", "管理",
            "明细", "详情", "趋势", "消耗", "素材", "广告", "投放", "效果"
        ]

        for keyword in business_keywords:
            if keyword in interface_name or keyword in description:
                return False

        return False

    def _create_entities_from_interfaces(self, interfaces: List[dict]) -> List[dict]:
        """基于接口创建实体"""
        entities = []
        for interface in interfaces:
            if interface["type"] == "crud" and interface["fields"]:
                entity = {
                    "id": f"{understand_doc_config.ENTITY_ID_PREFIX}{interface['id'].replace(understand_doc_config.INTERFACE_ID_PREFIX, '')}",
                    "name": interface["name"].replace("接口", "").replace("管理", "") + "表",
                    "description": f"{interface.get('description', '')}对应的数据实体",
                    "fields": interface["fields"],
                    "source_interface_id": interface["id"]
                }
                entities.append(entity)

        return entities

    def _build_final_ism(self, interfaces: List[dict], entities: List[dict], doc_meta: dict, chunks: List[dict]) -> dict:
        """构建最终的ISM结构"""
        # 计算统计信息
        stats = {
            "total_chunks": len(chunks),
            "chunks_with_grid": len([c for c in chunks if c.get("metadata", {}).get("has_grid", False)]),
            "chunks_processed": len(chunks),
            "interfaces_generated": len(interfaces),
            "entities_generated": len(entities)
        }

        final_ism = {
            "doc_meta": doc_meta,
            "interfaces": interfaces,
            "entities": entities,
            "actions": [],
            "views": [],
            "parsing_statistics": stats,
            "__processing_method": understand_doc_config.PARSING_MODE_CHUNKED,
            "__key": f"{understand_doc_config.PARSING_MODE_CHUNKED}_{hash(str(chunks)) % 10000:04d}",
            "__version": understand_doc_config.ISM_VERSION
        }

        return final_ism

    def _generate_basic_interfaces_and_entities(self, user_intent: str, combined_content: str, feishu_urls: List[str]) -> tuple:
        """根据用户意图和内容生成基础接口和实体"""
        interfaces = []
        entities = []

        if user_intent == "generate_crud" and "用户表" in combined_content:
            # 从内容中提取用户表信息
            interface = {
                "id": f"{understand_doc_config.INTERFACE_ID_PREFIX}users_crud",
                "name": "用户管理CRUD",
                "type": "crud",
                "description": "用户信息的增删改查操作",
                "target_entity": "users",
                "fields": [
                    {"name": "id", "type": "string", "required": True, "description": "用户ID，主键"},
                    {"name": "name", "type": "string", "required": False, "description": "用户姓名"},
                    {"name": "channel", "type": "string", "required": False, "description": "渠道"}
                ],
                "operations": understand_doc_config.CRUD_OPERATIONS.copy()
            }
            interfaces.append(interface)

            entity = {
                "id": f"{understand_doc_config.ENTITY_ID_PREFIX}users",
                "name": "用户表",
                "description": "系统用户信息表",
                "fields": interface["fields"]
            }
            entities.append(entity)
        else:
            # 生成通用的接口结构
            interface = {
                "id": f"{understand_doc_config.INTERFACE_ID_PREFIX}basic",
                "name": "基础接口",
                "type": "custom",
                "description": "从文档内容生成的基础接口",
                "fields": understand_doc_config.DEFAULT_FIELDS.copy(),
                "operations": understand_doc_config.DEFAULT_OPERATIONS.copy()
            }
            interfaces.append(interface)

        return interfaces, entities

    def extract_title_from_chunks(self, chunks: List[dict]) -> str:
        """从块中提取标题"""
        for chunk in chunks:
            if chunk["chunk_type"] == "header_section":
                lines = chunk["content"].split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith('# '):
                        return line[2:].strip()
        return "块并行解析文档"

    def validate_ism_structure(self, ism: dict) -> tuple[bool, List[str]]:
        """
        验证ISM结构的有效性

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # 检查必需字段
        required_fields = ["doc_meta", "interfaces"]
        for field in required_fields:
            if field not in ism:
                errors.append(f"缺少必需字段: {field}")

        # 检查doc_meta
        if "doc_meta" in ism:
            doc_meta = ism["doc_meta"]
            required_meta_fields = ["title", "url", "version", "parsing_mode"]
            for field in required_meta_fields:
                if field not in doc_meta:
                    errors.append(f"doc_meta缺少必需字段: {field}")

        # 检查接口
        if "interfaces" in ism:
            interfaces = ism["interfaces"]
            if not isinstance(interfaces, list):
                errors.append("interfaces必须是列表类型")
            else:
                for i, interface in enumerate(interfaces):
                    if not isinstance(interface, dict):
                        errors.append(f"接口[{i}]必须是字典类型")
                        continue

                    required_interface_fields = ["id", "name", "type"]
                    for field in required_interface_fields:
                        if field not in interface:
                            errors.append(f"接口[{i}]缺少必需字段: {field}")

                    # 验证接口类型
                    if "type" in interface and not understand_doc_config.is_valid_interface_type(interface["type"]):
                        errors.append(f"接口[{i}]类型无效: {interface['type']}")

        return len(errors) == 0, errors

    def optimize_ism_structure(self, ism: dict) -> dict:
        """
        优化ISM结构，去除冗余信息，压缩数据大小
        """
        optimized_ism = ism.copy()

        # 移除空的字段
        if "interfaces" in optimized_ism:
            optimized_ism["interfaces"] = [
                interface for interface in optimized_ism["interfaces"]
                if interface.get("id") and interface.get("name")
            ]

        if "entities" in optimized_ism:
            optimized_ism["entities"] = [
                entity for entity in optimized_ism["entities"]
                if entity.get("id") and entity.get("name")
            ]

        # 压割pending信息
        if "__pending__" in optimized_ism:
            pending = optimized_ism["__pending__"]
            if len(pending) > 100:  # 如果pending信息太多，进行压缩
                optimized_ism["__pending__"] = pending[:50] + [f"...省略{len(pending) - 50}条错误信息..."]

        # 添加优化标记
        optimized_ism["__optimized"] = True
        optimized_ism["__optimized_timestamp"] = json.dumps({"timestamp": "now"})  # 简化的时间戳

        return optimized_ism


def create_ism_builder(trace_id: str = "", step_name: str = "") -> ISMBuilder:
    """
    创建ISM构建器实例
    """
    return ISMBuilder(trace_id, step_name)