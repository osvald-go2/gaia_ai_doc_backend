"""
normalize_and_validate_ism 节点

职责：把 understand_doc 的粗稿 ISM 处理成规范、可校验、可稳定对比的 ISM
作为编译为 GAIA 图的可靠输入。

输入：ism_raw（来自 understand_doc）
输出：ism（已规范化/校验/稳定ID） + diag（校验与修复信息）

约束：只能写：ism, diag
"""

import re
import json
from typing import Dict, List, Any, Optional
from models.state import AgentState
from utils.logger import logger


def normalize_and_validate_ism(state: AgentState) -> AgentState:
    """
    标准化和校验 ISM

    1. normalize_ism（标准化）
    2. validate_ism（结构与语义校验）
    """
    trace_id = state["trace_id"]
    step_name = "normalize_and_validate_ism"

    # 获取原始 ISM
    ism_raw = state.get("ism_raw", state.get("ism", {}))

    logger.start(trace_id, step_name, "开始标准化和校验ISM",
                extra={
                    "has_interfaces": "interfaces" in ism_raw,
                    "interfaces_count": len(ism_raw.get("interfaces", [])),
                    "has_entities": "entities" in ism_raw,
                    "entities_count": len(ism_raw.get("entities", []))
                })

    # 初始化诊断信息
    diag = {
        "fixups": [],
        "warnings": [],
        "errors": []
    }

    # 第一步：标准化
    ism, diag = normalize_ism(ism_raw, diag, trace_id, step_name)

    # 第二步：校验
    ism, diag = validate_ism(ism, diag, trace_id, step_name)

    # 写入 state - 只写允许的字段
    result_state = state.copy()
    result_state["ism"] = ism
    result_state["diag"] = diag

    logger.end(trace_id, step_name, "ISM标准化和校验完成",
              extra={
                  "final_interfaces_count": len(ism.get("interfaces", [])),
                  "fixups_count": len(diag["fixups"]),
                  "warnings_count": len(diag["warnings"]),
                  "errors_count": len(diag["errors"])
              })

    return result_state


def normalize_ism(ism_raw: Dict[str, Any], diag: Dict[str, Any], trace_id: str, step_name: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """
    标准化 ISM

    - 补齐字段：expression, data_type, required
    - 清洗：去掉空行、URL、参考口径、图片占位，去重
    - 生成 stable IDs
    """
    ism = ism_raw.copy()

    # 处理新版本 interfaces 结构
    if "interfaces" in ism:
        normalized_interfaces = []

        for interface in ism.get("interfaces", []):
            # 标准化基础字段
            norm_interface = normalize_interface_fields(interface, diag, trace_id, step_name)

            # 标准化 dimensions 和 metrics
            if "dimensions" in norm_interface:
                norm_interface["dimensions"] = normalize_fields_list(
                    norm_interface["dimensions"], "dimension", diag, trace_id, step_name
                )

            if "metrics" in norm_interface:
                norm_interface["metrics"] = normalize_fields_list(
                    norm_interface["metrics"], "metric", diag, trace_id, step_name
                )

            # 生成稳定 ID
            if not norm_interface.get("id"):
                norm_interface["id"] = generate_stable_id(norm_interface.get("name", ""))
                diag["fixups"].append(f"为接口 '{norm_interface['name']}' 生成稳定ID: {norm_interface['id']}")

            normalized_interfaces.append(norm_interface)

        ism["interfaces"] = normalized_interfaces
        logger.info(trace_id, step_name, f"标准化了 {len(normalized_interfaces)} 个接口")

    # 兼容旧版本 entities 结构
    if "entities" in ism:
        normalized_entities = []

        for entity in ism.get("entities", []):
            # 标准化实体
            norm_entity = normalize_entity_fields(entity, diag, trace_id, step_name)

            # 标准化字段
            if "fields" in norm_entity:
                norm_entity["fields"] = normalize_fields_list(
                    norm_entity["fields"], "field", diag, trace_id, step_name
                )

            # 生成稳定 ID
            if not norm_entity.get("id"):
                norm_entity["id"] = generate_stable_id(norm_entity.get("name", ""))
                diag["fixups"].append(f"为实体 '{norm_entity['name']}' 生成稳定ID: {norm_entity['id']}")

            normalized_entities.append(norm_entity)

        ism["entities"] = normalized_entities
        logger.info(trace_id, step_name, f"标准化了 {len(normalized_entities)} 个实体")

    return ism, diag


def normalize_interface_fields(interface: Dict[str, Any], diag: Dict[str, Any], trace_id: str, step_name: str) -> Dict[str, Any]:
    """标准化接口基础字段"""
    norm_interface = interface.copy()

    # 确保有 name
    if not norm_interface.get("name"):
        norm_interface["name"] = "未命名接口"
        diag["fixups"].append("为无名接口设置默认名称")

    # 确保有 type
    if not norm_interface.get("type"):
        norm_interface["type"] = "data_display"  # 默认类型
        diag["fixups"].append(f"接口 '{norm_interface['name']}' 缺少type，设置为默认值 'data_display'")

    return norm_interface


def normalize_entity_fields(entity: Dict[str, Any], diag: Dict[str, Any], trace_id: str, step_name: str) -> Dict[str, Any]:
    """标准化实体基础字段"""
    norm_entity = entity.copy()

    # 确保有 name
    if not norm_entity.get("name"):
        norm_entity["name"] = "未命名实体"
        diag["fixups"].append("为无名实体设置默认名称")

    return norm_entity


def normalize_fields_list(fields: List[Dict[str, Any]], field_type: str, diag: Dict[str, Any], trace_id: str, step_name: str) -> List[Dict[str, Any]]:
    """标准化字段列表"""
    normalized_fields = []
    seen_fields = set()  # 用于去重

    for field in fields:
        if not isinstance(field, dict):
            diag["warnings"].append(f"跳过非对象字段: {field}")
            continue

        norm_field = normalize_single_field(field, field_type, diag, trace_id, step_name)

        # 去重检查（基于 name+expression）
        field_key = f"{norm_field.get('name', '')}:{norm_field.get('expression', '')}"
        if field_key in seen_fields:
            diag["fixups"].append(f"跳过重复字段: {norm_field.get('name', '')}")
            continue

        seen_fields.add(field_key)
        normalized_fields.append(norm_field)

    logger.info(trace_id, step_name, f"标准化了 {len(normalized_fields)} 个{field_type}字段")
    return normalized_fields


def normalize_single_field(field: Dict[str, Any], field_type: str, diag: Dict[str, Any], trace_id: str, step_name: str) -> Dict[str, Any]:
    """标准化单个字段"""
    norm_field = field.copy()

    # 清洗：去掉空行、URL、参考口径、图片占位
    if "name" in norm_field:
        norm_field["name"] = clean_field_name(norm_field["name"], diag)

    # 补齐 expression
    if not norm_field.get("expression") and norm_field.get("name"):
        norm_field["expression"] = name_to_expression(norm_field["name"])
        diag["fixups"].append(f"为字段 '{norm_field['name']}' 生成表达式: {norm_field['expression']}")

    # 补齐 data_type
    if not norm_field.get("data_type"):
        norm_field["data_type"] = infer_data_type(norm_field, field_type)
        diag["fixups"].append(f"为字段 '{norm_field.get('name', '')}' 推断数据类型: {norm_field['data_type']}")

    # 补齐 required
    if "required" not in norm_field:
        norm_field["required"] = infer_required(norm_field, field_type)
        if norm_field["required"]:
            diag["fixups"].append(f"字段 '{norm_field.get('name', '')}' 标记为必需")

    return norm_field


def clean_field_name(name: str, diag: Dict[str, Any]) -> str:
    """清洗字段名"""
    if not isinstance(name, str):
        return str(name)

    # 去掉 URL
    name = re.sub(r'https?://[^\s]+', '', name)

    # 去掉图片占位
    name = re.sub(r'!\[.*?\]\(.*?\)', '', name)

    # 去掉"参考口径"等无用信息
    name = re.sub(r'参考口径[:：].*$', '', name)

    # 去掉多余空格
    name = name.strip()

    return name


def name_to_expression(name: str) -> str:
    """中文名→英文占位（词典优先，slugify 兜底）"""
    # 常用字段词典映射
    field_mapping = {
        "公司ID": "companyId",
        "公司名称": "companyName",
        "公司": "company",
        "时间": "time",
        "日期": "date",
        "消耗": "cost",
        "ROI": "roi",
        "GMV": "gmv",
        "点击量": "clicks",
        "曝光量": "impressions",
        "转化率": "conversionRate",
        "收入": "revenue",
        "利润": "profit"
    }

    # 词典匹配
    if name in field_mapping:
        return field_mapping[name]

    # 拼音转换（简化版）
    import re
    # 简单的字符替换映射
    pinyin_map = {
        '公司': 'gongsi',
        '名称': 'mingcheng',
        '时间': 'shijian',
        '日期': 'riqi',
        '消耗': 'xiaohao',
        '收入': 'shouru',
        '利润': 'lirun'
    }

    result = name
    for chinese, pinyin in pinyin_map.items():
        result = result.replace(chinese, pinyin)

    # 只保留字母数字
    result = re.sub(r'[^a-zA-Z0-9]', '', result)

    return result.lower() if result else name.lower()


def infer_data_type(field: Dict[str, Any], field_type: str) -> str:
    """推断数据类型"""
    name = field.get("name", "").lower()

    # 时间相关字段
    time_keywords = ["时间", "日期", "时间戳", "time", "date"]
    if any(keyword in name for keyword in time_keywords):
        return "date"

    # 指标类型默认为数字
    if field_type == "metric":
        return "number"

    # 维度类型默认为字符串
    return "string"


def infer_required(field: Dict[str, Any], field_type: str) -> bool:
    """推断是否必需"""
    name = field.get("name", "").lower()

    # 必需关键字段
    required_keywords = ["公司", "公司id", "时间", "日期", "消耗", "company", "time", "date", "cost"]
    if any(keyword in name for keyword in required_keywords):
        return True

    # 趋势接口的时间字段必需
    # 这个判断需要接口上下文，在 validate_ism 中处理

    return False


def generate_stable_id(name: str) -> str:
    """生成稳定ID"""
    import hashlib
    # 使用名称的哈希值确保稳定性
    hash_obj = hashlib.md5(name.encode('utf-8'))
    return f"iface_{hash_obj.hexdigest()[:8]}"


def validate_ism(ism: Dict[str, Any], diag: Dict[str, Any], trace_id: str, step_name: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """
    结构与语义校验

    - 结构校验：接口含 id/name/type；dimensions[]/metrics[] 为对象数组
    - 语义校验：趋势接口存在时间维度；字段不重复等
    """
    # 结构校验
    if "interfaces" in ism:
        for interface in ism.get("interfaces", []):
            validate_interface_structure(interface, diag, trace_id, step_name)
            validate_interface_semantics(interface, diag, trace_id, step_name)

    # 兼容旧版本
    if "entities" in ism:
        for entity in ism.get("entities", []):
            validate_entity_structure(entity, diag, trace_id, step_name)

    # 添加 __key__ 用于增量更新
    ism["__key__"] = generate_content_hash(ism)

    return ism, diag


def validate_interface_structure(interface: Dict[str, Any], diag: Dict[str, Any], trace_id: str, step_name: str):
    """校验接口结构"""
    # 必需字段检查
    required_fields = ["id", "name", "type"]
    for field in required_fields:
        if not interface.get(field):
            diag["errors"].append(f"接口缺少必需字段: {field}")

    # 字段类型检查
    if "dimensions" in interface and not isinstance(interface["dimensions"], list):
        diag["errors"].append(f"接口 '{interface.get('name')}' 的 dimensions 必须是数组")

    if "metrics" in interface and not isinstance(interface["metrics"], list):
        diag["errors"].append(f"接口 '{interface.get('name')}' 的 metrics 必须是数组")


def validate_interface_semantics(interface: Dict[str, Any], diag: Dict[str, Any], trace_id: str, step_name: str):
    """校验接口语义"""
    interface_type = interface.get("type", "")
    interface_name = interface.get("name", "")

    # 趋势接口必须有时间维度
    if "trend" in interface_type.lower() and "dimensions" in interface:
        has_time_dimension = any(
            "时间" in dim.get("name", "") or "date" in dim.get("name", "").lower()
            for dim in interface["dimensions"]
        )
        if not has_time_dimension:
            diag["warnings"].append(f"趋势接口 '{interface_name}' 缺少时间维度")

    # 字段重复检查
    all_fields = []
    if "dimensions" in interface:
        all_fields.extend(interface["dimensions"])
    if "metrics" in interface:
        all_fields.extend(interface["metrics"])

    seen_names = set()
    seen_expressions = set()

    for field in all_fields:
        name = field.get("name", "")
        expression = field.get("expression", "")

        if name and name in seen_names:
            diag["warnings"].append(f"接口 '{interface_name}' 中存在重复字段名: {name}")
        seen_names.add(name)

        if expression and expression in seen_expressions:
            diag["warnings"].append(f"接口 '{interface_name}' 中存在重复表达式: {expression}")
        seen_expressions.add(expression)


def validate_entity_structure(entity: Dict[str, Any], diag: Dict[str, Any], trace_id: str, step_name: str):
    """校验实体结构"""
    # 必需字段检查
    if not entity.get("id"):
        diag["errors"].append("实体缺少必需字段: id")

    if not entity.get("name"):
        diag["errors"].append("实体缺少必需字段: name")

    # 字段类型检查
    if "fields" in entity and not isinstance(entity["fields"], list):
        diag["errors"].append(f"实体 '{entity.get('name')}' 的 fields 必须是数组")


def generate_content_hash(content: Dict[str, Any]) -> str:
    """生成内容哈希用于增量更新"""
    import hashlib
    # 排序后序列化以确保一致性
    content_str = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(content_str.encode('utf-8')).hexdigest()