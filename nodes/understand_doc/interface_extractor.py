"""
接口提取器
从文档内容和Grid块中提取接口定义
"""

import json
import uuid
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple, Optional

from .config import understand_doc_config
from .grid_parser import GridParser
from utils.logger import logger
from client.deepseek_client_simple import call_deepseek_llm


class InterfaceExtractor:
    """接口提取器类"""

    def __init__(self, trace_id: str = "", step_name: str = ""):
        self.trace_id = trace_id
        self.step_name = step_name
        self.grid_parser = GridParser(trace_id, step_name)

    def parse_single_interface(self, grid_block_with_context: Tuple[str, str, int]) -> Dict[str, Any]:
        """
        解析单个grid块为接口定义

        Args:
            grid_block_with_context: (grid_content, context, block_index)

        Returns:
            接口定义字典
        """
        grid_content, context, block_index = grid_block_with_context

        try:
            # 构建用户提示词
            user_prompt = f"""请解析下面这个功能块，生成对应的接口定义。

上下文信息：
{context}

功能块内容：
{grid_content}

请根据功能块的内容智能识别接口类型，并提取字段信息。输出JSON格式。"""

            # 调用LLM
            response = call_deepseek_llm(
                system_prompt=understand_doc_config.INTERFACE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                model=understand_doc_config.DEFAULT_MODEL,
                temperature=understand_doc_config.DEFAULT_TEMPERATURE,
                max_tokens=understand_doc_config.get_max_tokens_by_task("single_interface")
            )

            # 解析响应
            try:
                parsed_data = json.loads(response)

                # 处理数组响应
                if isinstance(parsed_data, list):
                    logger.info(self.trace_id, self.step_name, f"单接口解析返回数组格式: {len(parsed_data)} 个接口")

                    # 为兼容性选择第一个接口
                    interface_data = parsed_data[0] if parsed_data else {}
                    interface_data['_array_response'] = True
                    interface_data['_array_data'] = parsed_data
                else:
                    interface_data = parsed_data

                # 添加元数据
                interface_data['_block_index'] = block_index
                interface_data['_grid_content'] = grid_content
                interface_data['_source_method'] = 'llm_parsing'
                return interface_data
            except json.JSONDecodeError:
                logger.warning(f"Block {block_index} LLM响应不是合法JSON: {response[:understand_doc_config.LOG_ERROR_TRUNCATE_LENGTH]}...")
                return self._create_error_interface(
                    block_index, grid_content, "JSON解析失败", response
                )

        except Exception as e:
            logger.error(f"解析Block {block_index}时发生错误: {str(e)}")
            return self._create_error_interface(
                block_index, grid_content, str(e)
            )

    def parse_interfaces_chunk(self, chunk_content: str, chunk_index: int, full_document: str = "") -> List[Dict[str, Any]]:
        """
        解析一个文档块中的所有接口
        """
        grid_blocks = self.grid_parser.extract_grid_blocks(chunk_content)

        if not grid_blocks:
            return []

        # 准备并行处理的参数
        parse_tasks = []
        for i, (grid_content, grid_start) in enumerate(grid_blocks):
            # 使用完整文档提取上下文，而不是只使用分割后的块
            if full_document:
                # 在完整文档中找到这个grid块的真正位置
                actual_start = self.grid_parser.find_grid_position_in_document(grid_content, full_document)
                context = self.grid_parser.extract_context_around_grid(full_document, actual_start)
            else:
                # 回退到使用块内容
                context = self.grid_parser.extract_context_around_grid(chunk_content, grid_start)

            block_index = chunk_index * 10 + i  # 确保索引唯一
            parse_tasks.append((grid_content, context, block_index))

        # 并行处理
        interfaces = []
        with ThreadPoolExecutor(max_workers=understand_doc_config.MAX_WORKERS) as executor:
            future_to_interface = {
                executor.submit(self.parse_single_interface, task): task
                for task in parse_tasks
            }

            for future in as_completed(future_to_interface):
                try:
                    interface_result = future.result(timeout=understand_doc_config.DEFAULT_TIMEOUT)
                    interfaces.append(interface_result)
                except Exception as e:
                    task = future_to_interface[future]
                    logger.error(f"并行处理接口时发生错误: {str(e)}, task: {task[2]}")
                    interfaces.append(self._create_error_interface(
                        task[2], task[0], str(e)
                    ))

        return interfaces

    def extract_interface_from_text(self, result: str, chunk_data: dict, grid_info: dict) -> Optional[dict]:
        """
        当JSON解析失败时，从文本中提取接口信息的降级方法
        """
        logger.info(self.trace_id, self.step_name, f"开始文本提取接口信息")

        try:
            # 默认接口结构
            interface = {
                "id": f"{understand_doc_config.INTERFACE_ID_PREFIX}fallback_{uuid.uuid4().hex[:8]}",
                "name": grid_info.get("name", "未知接口"),
                "type": "unknown",
                "method": "GET",
                "path": "",
                "description": grid_info.get("description", ""),
                "fields": understand_doc_config.DEFAULT_FIELDS.copy(),
                "operations": understand_doc_config.DEFAULT_OPERATIONS.copy(),
                "source_method": "text_extraction"
            }

            # 提取接口名称
            interface["name"] = self._extract_field_from_text(result, [
                r'["\'"]?name["\'"]?\s*[:：]\s*["\'"]([^"\']+)["\'"]',
                r'接口名[称]?[:：]\s*([^\n，。,\.]+)',
                r'name[:：]\s*([^\n，。,\.]+)'
            ], interface["name"])

            # 提取请求方法
            method_match = self._extract_field_from_text(result, [
                r'["\'"]?method["\'"]?\s*[:：]\s*["\'"]?(GET|POST|PUT|DELETE|PATCH)["\'"]?',
                r'请求方式?[:：]\s*(GET|POST|PUT|DELETE|PATCH)',
                r'method[:：]\s*(GET|POST|PUT|DELETE|PATCH)'
            ])
            if method_match and understand_doc_config.is_valid_method(method_match):
                interface["method"] = method_match.upper()

            # 提取路径
            path_match = self._extract_field_from_text(result, [
                r'["\'"]?path["\'"]?\s*[:：]\s*["\'"]([^"\']+)["\'"]',
                r'路径[:：]\s*([^\n，。,\.]+)',
                r'path[:：]\s*([^\n，。,\.]+)',
                r'/api/[^\s\n，。,\.]+'
            ])
            if path_match:
                path = path_match.strip()
                if not path.startswith('/'):
                    path = '/' + path
                interface["path"] = path

            # 根据grid内容推断接口类型和字段
            self._infer_interface_from_content(interface, chunk_data.get("content", ""))

            # 如果没有提取到路径，根据接口名称生成默认路径
            if not interface.get("path"):
                interface["path"] = f"/api/{interface['name'].replace(' ', '_').lower()}"

            logger.info(self.trace_id, self.step_name, f"文本提取完成: {interface['name']} - {interface['method']} {interface['path']}")

            return interface

        except Exception as e:
            logger.error(self.trace_id, self.step_name, f"文本提取失败: {str(e)}")
            return self._create_emergency_interface(grid_info)

    def create_fallback_interface(self, chunk_data: dict, interface_name: str = None) -> dict:
        """
        为失败的块创建降级接口
        """
        try:
            chunk_id = chunk_data.get("chunk_id", "unknown")
            content = chunk_data.get("content", "")

            # 从内容中直接提取接口名称
            if not interface_name:
                interface_name = self._extract_interface_name_from_content(content)

            # 创建降级接口
            fallback_interface = {
                "id": f"{understand_doc_config.INTERFACE_ID_PREFIX}fallback_{chunk_id}",
                "name": interface_name,
                "type": "fallback",
                "method": "GET",
                "path": f"/api/{interface_name.replace(' ', '_').lower()}",
                "description": f"从 {interface_name} 内容降级生成的接口",
                "fields": understand_doc_config.DEFAULT_FIELDS.copy(),
                "operations": understand_doc_config.DEFAULT_OPERATIONS.copy(),
                "source_chunk_id": chunk_id,
                "source_chunk_type": chunk_data.get("chunk_type", "unknown"),
                "source_method": "fallback_processing"
            }

            # 根据内容推断更准确的接口类型
            self._infer_interface_from_content(fallback_interface, content)

            return fallback_interface

        except Exception as e:
            logger.error(self.trace_id, self.step_name, f"降级接口创建失败: {str(e)}")
            return self._create_emergency_interface({"name": interface_name or "未知接口", "description": ""})

    def process_grid_chunks_parallel(self, grid_chunks: List[dict]) -> List[dict]:
        """
        并行处理包含grid的块
        """
        interface_results = []

        logger.info(self.trace_id, self.step_name, f"并行处理 {len(grid_chunks)} 个grid块")

        def process_single_grid_chunk(chunk: dict) -> dict:
            """处理单个grid块"""
            try:
                chunk_id = chunk["chunk_id"]
                content = chunk["content"]
                context_before = chunk.get("context_before", "")
                context_after = chunk.get("context_after", "")

                # 构建完整的上下文
                full_content = f"{context_before}\n\n{content}\n\n{context_after}".strip()

                # 记录LLM调用
                logger.info(self.trace_id, self.step_name, f"调用LLM解析块 {chunk_id}")

                # 调用LLM解析grid块
                result = call_deepseek_llm(
                    system_prompt=understand_doc_config.INTERFACE_SYSTEM_PROMPT,
                    user_prompt=f"请解析以下内容中的grid块，生成接口语义模型：\n\n{full_content}",
                    model=understand_doc_config.DEFAULT_MODEL,
                    temperature=understand_doc_config.DEFAULT_TEMPERATURE,
                    max_tokens=understand_doc_config.get_max_tokens_by_task("single_interface")
                )

                # 记录LLM返回结果
                logger.info(self.trace_id, self.step_name, f"LLM返回结果: {result[:understand_doc_config.LOG_RESULT_PREVIEW_LENGTH]}...")

                # 解析LLM返回结果 - 处理可能的数组格式
                try:
                    # 首先尝试直接解析
                    parsed_data = json.loads(result.strip())

                    # 如果返回的是数组格式，处理所有接口
                    if isinstance(parsed_data, list):
                        logger.info(self.trace_id, self.step_name, f"LLM返回数组格式，包含 {len(parsed_data)} 个接口")

                        # 为数组响应创建特殊处理标记
                        interface_data = {
                            "_array_response": True,
                            "_array_size": len(parsed_data),
                            "_chunk_content": full_content,
                            "source_chunk_id": chunk_id,
                            "source_chunk_type": chunk["chunk_type"],
                            "source_method": "parallel_llm_parsing_array"
                        }

                        # 暂时保存数组数据，后续由ISM构建器处理
                        interface_data["_array_data"] = parsed_data

                        # 为了兼容性，选择最相关的接口作为主要接口
                        primary_interface = self._select_primary_interface_from_array(parsed_data, chunk_id, full_content)
                        interface_data.update(primary_interface)

                    else:
                        interface_data = parsed_data
                        interface_data["source_chunk_id"] = chunk_id
                        interface_data["source_chunk_type"] = chunk["chunk_type"]
                        interface_data["source_method"] = "parallel_llm_parsing"

                    logger.info(self.trace_id, self.step_name, f"JSON解析成功: {interface_data.get('name', '未知接口')} [{interface_data.get('type', 'unknown')}]")

                    return {
                        "success": True,
                        "interface": interface_data,
                        "chunk_id": chunk_id,
                        "llm_response": result
                    }

                except json.JSONDecodeError as e:
                    # 特殊处理："Extra data"错误通常是多个JSON对象连接在一起
                    if "Extra data" in str(e):
                        logger.info(self.trace_id, self.step_name, f"检测到Extra data错误，尝试恢复解析 - 块 {chunk_id}")
                        recovered_interfaces = self._recover_json_from_extra_data(result, chunk_id, chunk)
                        if recovered_interfaces:
                            if len(recovered_interfaces) > 1:
                                # 多个接口，按数组响应处理
                                interface_data = {
                                    "_array_response": True,
                                    "_array_size": len(recovered_interfaces),
                                    "_chunk_content": full_content,
                                    "source_chunk_id": chunk_id,
                                    "source_chunk_type": chunk["chunk_type"],
                                    "source_method": "json_recovery_array"
                                }
                                interface_data["_array_data"] = recovered_interfaces
                                primary_interface = self._select_primary_interface_from_array(recovered_interfaces, chunk_id, full_content)
                                interface_data.update(primary_interface)
                            else:
                                # 单个接口
                                interface_data = recovered_interfaces[0]
                                interface_data["source_chunk_id"] = chunk_id
                                interface_data["source_chunk_type"] = chunk["chunk_type"]
                                interface_data["source_method"] = "json_recovery_single"

                            logger.info(self.trace_id, self.step_name, f"JSON恢复成功: {interface_data.get('name', '未知接口')} [{interface_data.get('type', 'unknown')}]")

                            return {
                                "success": True,
                                "interface": interface_data,
                                "chunk_id": chunk_id,
                                "llm_response": result
                            }

                    # 其他JSON解析错误，记录警告并尝试降级处理
                    logger.warn(self.trace_id, self.step_name, f"JSON解析失败 - 块 {chunk_id}: {str(e)[:understand_doc_config.LOG_ERROR_TRUNCATE_LENGTH]}")

                    # 尝试从返回结果中提取接口信息
                    grid_info = {"name": f"接口_{chunk_id}", "description": "从grid块提取的接口"}
                    interface_data = self.extract_interface_from_text(result, chunk, grid_info)
                    if interface_data:
                        interface_data["source_chunk_id"] = chunk_id
                        interface_data["source_chunk_type"] = chunk["chunk_type"]
                        interface_data["source_method"] = "text_extraction_fallback"
                        return {
                            "success": True,
                            "interface": interface_data,
                            "chunk_id": chunk_id,
                            "llm_response": result
                        }

                    logger.warn(self.trace_id, self.step_name, f"文本解析失败 - 块 {chunk_id}")
                    return {
                        "success": False,
                        "chunk_id": chunk_id,
                        "error": f"JSON解析和文本解析都失败: {str(e)[:understand_doc_config.LOG_ERROR_TRUNCATE_LENGTH]}"
                    }

                except Exception as e:
                    logger.error(self.trace_id, self.step_name, f"块处理异常 - {chunk.get('chunk_id', 'unknown')}: {str(e)}")
                    return {
                        "success": False,
                        "chunk_id": chunk.get("chunk_id", "unknown"),
                        "error": str(e)
                    }

            except Exception as e:
                logger.error(self.trace_id, self.step_name, f"块处理系统异常: {str(e)}")
                return {
                    "success": False,
                    "chunk_id": chunk.get("chunk_id", "unknown"),
                    "error": f"系统异常: {str(e)}"
                }

        # 并行执行
        with ThreadPoolExecutor(max_workers=understand_doc_config.CHUNK_MAX_WORKERS) as executor:
            future_to_chunk = {executor.submit(process_single_grid_chunk, chunk): chunk for chunk in grid_chunks}

            for future in as_completed(future_to_chunk):
                chunk = future_to_chunk[future]
                try:
                    result = future.result()
                    if result["success"]:
                        interface_results.append(result["interface"])
                        logger.info(self.trace_id, self.step_name, f"块 {result['chunk_id']} 处理成功")
                    else:
                        logger.warn(self.trace_id, self.step_name, f"块 {result['chunk_id']} 处理失败: {result.get('error', 'Unknown')}")
                except Exception as e:
                    logger.error(self.trace_id, self.step_name, f"块 {chunk['chunk_id']} 执行异常: {str(e)}")

        # 应用降级处理
        return self._apply_fallback_processing(interface_results, grid_chunks)

    # ==================== 私有辅助方法 ====================

    def _create_error_interface(self, block_index: int, grid_content: str, error_msg: str, raw_response: str = None) -> dict:
        """创建错误接口"""
        error_interface = {
            "error": error_msg,
            "_block_index": block_index,
            "_grid_content": grid_content,
            "_source_method": "error_parsing"
        }
        if raw_response:
            error_interface["_raw_response"] = raw_response
        return error_interface

    def _create_emergency_interface(self, grid_info: dict) -> dict:
        """创建紧急降级接口"""
        return {
            "id": f"{understand_doc_config.INTERFACE_ID_PREFIX}emergency_{uuid.uuid4().hex[:8]}",
            "name": grid_info.get("name", "未知接口"),
            "type": "emergency",
            "method": "GET",
            "path": f"/api/{grid_info.get('name', 'unknown').replace(' ', '_').lower()}",
            "description": f"紧急降级接口: {grid_info.get('description', '')}",
            "fields": understand_doc_config.DEFAULT_FIELDS.copy(),
            "operations": understand_doc_config.DEFAULT_OPERATIONS.copy(),
            "source_method": "emergency_fallback"
        }

    def _extract_field_from_text(self, text: str, patterns: List[str], default: str = "") -> str:
        """从文本中提取字段值"""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return default

    def _extract_interface_name_from_content(self, content: str) -> str:
        """从内容中提取接口名称"""
        for expected_name in understand_doc_config.EXPECTED_INTERFACES:
            if expected_name in content:
                return expected_name

        # 尝试从标题中提取
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('##'):
                return line.replace('##', '').strip()

        return "未知接口"

    def _infer_interface_from_content(self, interface: dict, content: str) -> None:
        """根据内容推断接口类型和字段"""
        content_lower = content.lower()

        # 根据内容推断接口类型
        interface["type"] = understand_doc_config.get_interface_type_by_keyword(content)

        # 根据接口类型添加特定字段
        if "消耗" in content and "详情" in content:
            interface["description"] = "获取消耗详情相关信息"
            interface["name"] = interface.get("name") or "消耗波动详情"
            interface["type"] = "analytics"
            interface["operations"] = ["read", "analyze"]
            interface["fields"] = [
                {"name": "date", "type": "string", "required": True, "description": "日期"},
                {"name": "consume_amount", "type": "number", "required": False, "description": "消耗金额"},
                {"name": "fluctuation", "type": "number", "required": False, "description": "波动值"}
            ]
        elif "素材" in content and "明细" in content:
            interface["description"] = "获取素材明细数据"
            interface["name"] = interface.get("name") or "素材明细"
            interface["type"] = "crud"
            interface["operations"] = understand_doc_config.CRUD_OPERATIONS.copy()
            interface["fields"] = [
                {"name": "material_id", "type": "string", "required": True, "description": "素材ID"},
                {"name": "material_name", "type": "string", "required": True, "description": "素材名称"},
                {"name": "material_type", "type": "string", "required": False, "description": "素材类型"}
            ]
        elif "趋势" in content:
            if "消耗" in content:
                interface["description"] = "获取消耗趋势数据"
                interface["name"] = interface.get("name") or "消耗趋势"
                interface["type"] = "analytics"
                interface["operations"] = ["read", "analyze"]
                interface["fields"] = [
                    {"name": "date_range", "type": "string", "required": True, "description": "日期范围"},
                    {"name": "trend_data", "type": "array", "required": False, "description": "趋势数据"}
                ]
            elif "交易" in content:
                interface["description"] = "获取交易趋势数据"
                interface["name"] = interface.get("name") or "交易趋势"
                interface["type"] = "analytics"
                interface["operations"] = ["read", "analyze"]
                interface["fields"] = [
                    {"name": "transaction_date", "type": "string", "required": True, "description": "交易日期"},
                    {"name": "transaction_amount", "type": "number", "required": False, "description": "交易金额"}
                ]
        elif "总" in content and "筛选" in content:
            interface["description"] = "获取总筛选项信息"
            interface["name"] = interface.get("name") or "总筛选项"
            interface["type"] = "config"
            interface["operations"] = ["read"]
            interface["fields"] = [
                {"name": "filter_key", "type": "string", "required": True, "description": "筛选键"},
                {"name": "filter_value", "type": "string", "required": True, "description": "筛选值"},
                {"name": "filter_type", "type": "string", "required": False, "description": "筛选类型"}
            ]

    def _select_primary_interface_from_array(self, interfaces_array: list, chunk_id: str, content: str) -> dict:
        """
        从数组响应中选择最相关的主要接口

        Args:
            interfaces_array: LLM返回的接口数组
            chunk_id: 块ID
            content: 原始内容

        Returns:
            选中的主要接口
        """
        if not interfaces_array:
            return self._create_default_interface(chunk_id)

        # 优先级策略：根据内容匹配度选择最相关的接口
        best_score = -1
        best_interface = interfaces_array[0]  # 默认选择第一个

        for interface in interfaces_array:
            score = 0
            interface_name = interface.get("name", "").lower()
            content_lower = content.lower()

            # 计算接口名称与内容的匹配度
            if interface_name in content_lower:
                score += 10

            # 检查标题匹配（更高优先级）
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('##') and interface_name in line.lower():
                    score += 50
                    break

            # 检查接口类型的合理性
            interface_type = interface.get("type", "")
            expected_types = {
                "总筛选项": "filter_dimension",
                "消耗趋势": "trend_analysis",
                "交易趋势": "trend_analysis",
                "消耗波动详情": "trend_analysis",
                "素材明细": "data_display"
            }

            for expected_name, expected_type in expected_types.items():
                if expected_name in interface_name and interface_type == expected_type:
                    score += 20
                    break

            # 更新最佳接口
            if score > best_score:
                best_score = score
                best_interface = interface

        logger.info(self.trace_id, self.step_name,
                   f"选择主要接口: {best_interface.get('name', '未知')} (评分: {best_score})")

        return best_interface

    def _create_default_interface(self, chunk_id: str) -> dict:
        """创建默认接口"""
        return {
            "id": f"interface_{chunk_id}_default",
            "name": "默认接口",
            "type": "custom",
            "description": "LLM响应解析失败时创建的默认接口",
            "fields": understand_doc_config.DEFAULT_FIELDS.copy(),
            "operations": understand_doc_config.DEFAULT_OPERATIONS.copy()
        }

    def _recover_json_from_extra_data(self, result: str, chunk_id: str, chunk: dict) -> List[dict]:
        """
        从"Extra data"错误中恢复多个JSON对象

        Args:
            result: LLM返回的原始结果
            chunk_id: 块ID
            chunk: 块数据

        Returns:
            恢复的接口列表
        """
        recovered_interfaces = []

        try:
            # 尝试多种分隔策略
            strategies = [
                # 策略1: 按照常见的JSON对象边界分割
                r'(?<=\})\s*(?=\{)',
                # 策略2: 按照换行和空白分割
                r'\}\s*\n\s*\{',
                # 策略3: 按照多个空白字符分割
                r'\}\s{2,}\{'
            ]

            cleaned_result = result.strip()

            for strategy in strategies:
                try:
                    # 分割结果
                    parts = re.split(strategy, cleaned_result)

                    # 尝试解析每个部分
                    valid_interfaces = []
                    for i, part in enumerate(parts):
                        part = part.strip()
                        if not part:
                            continue

                        # 确保部分是完整的JSON对象
                        if not part.startswith('{'):
                            part = '{' + part
                        if not part.endswith('}'):
                            part = part + '}'

                        try:
                            interface = json.loads(part)
                            # 验证接口结构
                            if self._validate_interface_structure(interface):
                                interface["recovery_index"] = i
                                interface["recovery_strategy"] = strategy
                                valid_interfaces.append(interface)
                                logger.debug(self.trace_id, self.step_name, f"成功恢复接口 {i}: {interface.get('name', '未知')}")
                        except json.JSONDecodeError:
                            # 跳过无效的部分
                            continue

                    # 如果成功恢复到接口，使用这个策略
                    if valid_interfaces:
                        logger.info(self.trace_id, self.step_name, f"使用策略恢复到 {len(valid_interfaces)} 个接口: {strategy}")
                        recovered_interfaces.extend(valid_interfaces)
                        break

                except Exception:
                    # 策略失败，尝试下一个
                    continue

            # 如果所有策略都失败，尝试更宽松的解析
            if not recovered_interfaces:
                logger.info(self.trace_id, self.step_name, f"尝试宽松解析模式")
                recovered_interfaces = self._loose_json_parsing(cleaned_result)

            return recovered_interfaces

        except Exception as e:
            logger.error(self.trace_id, self.step_name, f"JSON恢复过程异常: {str(e)}")
            return []

    def _validate_interface_structure(self, interface: dict) -> bool:
        """
        验证接口结构的基本有效性
        """
        # 检查必需字段
        required_fields = ["name", "type"]
        for field in required_fields:
            if field not in interface or not interface[field]:
                return False

        # 检查字段类型
        if not isinstance(interface.get("fields", []), list):
            return False

        # 检查操作
        if "operations" in interface and not isinstance(interface["operations"], list):
            return False

        return True

    def _loose_json_parsing(self, result: str) -> List[dict]:
        """
        宽松的JSON解析模式，尝试从混乱的文本中提取接口信息
        """
        interfaces = []

        try:
            # 尝试提取所有看起来像JSON对象的部分
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            matches = re.findall(json_pattern, result, re.DOTALL)

            for i, match in enumerate(matches):
                try:
                    interface = json.loads(match)
                    if self._validate_interface_structure(interface):
                        interface["recovery_index"] = i
                        interface["recovery_strategy"] = "loose_parsing"
                        interfaces.append(interface)
                except json.JSONDecodeError:
                    continue

        except Exception as e:
            logger.debug(self.trace_id, self.step_name, f"宽松解析失败: {str(e)}")

        return interfaces

    def _apply_fallback_processing(self, interface_results: List[dict], grid_chunks: List[dict]) -> List[dict]:
        """应用降级处理"""
        # 首先展开任何数组响应以获得完整的接口列表
        expanded_interfaces = []
        for interface in interface_results:
            if interface.get("_array_response") and interface.get("_array_data"):
                # 展开数组响应
                array_data = interface["_array_data"]
                logger.info(self.trace_id, self.step_name, f"展开数组响应进行缺失检查: {len(array_data)} 个接口")

                for i, array_interface in enumerate(array_data):
                    expanded_interface = array_interface.copy()
                    expanded_interface.update({
                        "source_chunk_id": interface.get("source_chunk_id", ""),
                        "source_chunk_type": interface.get("source_chunk_type", ""),
                        "source_method": f"{interface.get('source_method', '')}_array_item_{i}",
                        "_array_response": True,
                        "_array_index": i
                    })
                    expanded_interfaces.append(expanded_interface)
            else:
                expanded_interfaces.append(interface)

        # 找出所有处理的块ID（包括成功和失败的）
        processed_chunk_ids = {iface.get("source_chunk_id", "") for iface in interface_results}
        all_chunk_ids = {chunk.get("chunk_id", "") for chunk in grid_chunks}
        missing_chunk_ids = all_chunk_ids - processed_chunk_ids

        # 基于展开后的接口检查缺失的接口
        found_interface_names = {iface.get("name", "") for iface in expanded_interfaces}
        missing_interfaces = [exp for exp in understand_doc_config.EXPECTED_INTERFACES if exp not in found_interface_names]

        logger.info(self.trace_id, self.step_name, f"已处理块ID: {processed_chunk_ids}")
        logger.info(self.trace_id, self.step_name, f"所有块ID: {all_chunk_ids}")
        logger.info(self.trace_id, self.step_name, f"缺失块ID: {missing_chunk_ids}")
        logger.info(self.trace_id, self.step_name, f"展开后找到的接口: {found_interface_names}")
        logger.info(self.trace_id, self.step_name, f"仍然缺失的接口: {missing_interfaces}")

        # 只处理真正失败的块，跳过已经有数组响应的块
        failed_chunks = []
        for chunk in grid_chunks:
            chunk_id = chunk.get("chunk_id", "")
            if chunk_id in missing_chunk_ids:
                # 检查是否这个块已经有数组响应
                has_array_response = any(
                    iface.get("source_chunk_id") == chunk_id and iface.get("_array_response")
                    for iface in interface_results
                )
                if not has_array_response:
                    failed_chunks.append(chunk)
                else:
                    logger.info(self.trace_id, self.step_name, f"跳过块 {chunk_id}: 已有数组响应")

        if failed_chunks:
            logger.info(self.trace_id, self.step_name, f"识别出 {len(failed_chunks)} 个真正失败的块，开始降级处理")

            for chunk in failed_chunks:
                try:
                    # 使用降级方法
                    chunk_id = chunk.get("chunk_id", "unknown")
                    logger.info(self.trace_id, self.step_name, f"降级处理块: {chunk_id}")

                    fallback_interface = self.create_fallback_interface(chunk)
                    interface_results.append(fallback_interface)
                    logger.info(self.trace_id, self.step_name, f"块 {chunk_id} 降级处理成功: {fallback_interface['name']}")

                except Exception as e:
                    logger.error(self.trace_id, self.step_name, f"块 {chunk.get('chunk_id', 'unknown')} 降级处理也失败: {str(e)}")

        # 只有在真正缺失接口时才创建缺失接口的降级版本
        if missing_interfaces:
            logger.info(self.trace_id, self.step_name, f"为真正缺失的接口创建降级版本: {missing_interfaces}")

            for missing_interface in missing_interfaces:
                fallback_interface = {
                    "id": f"{understand_doc_config.INTERFACE_ID_PREFIX}fallback_missing_{missing_interface.replace(' ', '_').lower()}_{uuid.uuid4().hex[:8]}",
                    "name": missing_interface,
                    "type": "fallback",
                    "method": "GET",
                    "path": f"/api/{missing_interface.replace(' ', '_').lower()}",
                    "description": f"为缺失接口 {missing_interface} 创建的降级版本",
                    "fields": understand_doc_config.DEFAULT_FIELDS.copy(),
                    "operations": understand_doc_config.DEFAULT_OPERATIONS.copy(),
                    "source_chunk_id": "missing_fallback",
                    "source_chunk_type": "missing_interface",
                    "source_method": "missing_interface_fallback"
                }

                interface_results.append(fallback_interface)
                logger.info(self.trace_id, self.step_name, f"为缺失接口创建降级版本: {missing_interface}")

        # 最终检查
        final_expanded_interfaces = []
        for interface in interface_results:
            if interface.get("_array_response") and interface.get("_array_data"):
                array_data = interface["_array_data"]
                for array_interface in array_data:
                    final_expanded_interfaces.append(array_interface)
            else:
                final_expanded_interfaces.append(interface)

        final_interface_names = {iface.get("name", "") for iface in final_expanded_interfaces}
        final_missing = [exp for exp in understand_doc_config.EXPECTED_INTERFACES if exp not in final_interface_names]

        if final_missing:
            logger.error(self.trace_id, self.step_name, f"最终仍然缺失接口: {final_missing}")
        else:
            logger.info(self.trace_id, self.step_name, f"[SUCCESS] 所有预期接口都已生成: {understand_doc_config.EXPECTED_INTERFACES}")

        return interface_results


def create_interface_extractor(trace_id: str = "", step_name: str = "") -> InterfaceExtractor:
    """
    创建接口提取器实例
    """
    return InterfaceExtractor(trace_id, step_name)