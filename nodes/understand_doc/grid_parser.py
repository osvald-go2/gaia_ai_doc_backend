"""
Grid块解析器
处理文档中的grid格式内容提取和解析
"""

import json
import re
from typing import List, Tuple, Optional

from .config import understand_doc_config
from utils.logger import logger


class GridParser:
    """Grid块解析器类"""

    def __init__(self, trace_id: str = "", step_name: str = ""):
        self.trace_id = trace_id
        self.step_name = step_name

    def extract_grid_blocks(self, content: str) -> List[Tuple[str, int]]:
        """
        从文档内容中提取所有的grid块，并过滤非功能内容

        Args:
            content: 文档内容

        Returns:
            List of (grid_content, start_line_number)
        """
        grid_blocks = []
        lines = content.split('\n')
        in_grid = False
        grid_start = 0
        grid_content = []

        for i, line in enumerate(lines):
            if line.strip().startswith('```grid'):
                if not in_grid:
                    in_grid = True
                    grid_start = i
                    grid_content = []
                grid_content.append(line)
            elif line.strip() == '```' and in_grid:
                grid_content.append(line)
                full_grid_content = '\n'.join(grid_content)

                # 内容过滤：跳过非功能的grid块
                if self._is_functional_grid(full_grid_content, i, lines):
                    grid_blocks.append((full_grid_content, grid_start))
                else:
                    logger.info(self.trace_id, self.step_name,
                               f"跳过非功能grid块（行{grid_start}）: {self._get_skip_reason(full_grid_content)}")

                in_grid = False
            elif in_grid:
                grid_content.append(line)

        logger.info(self.trace_id, self.step_name,
                   f"Grid块提取完成: 共找到{len(grid_blocks)}个功能相关的grid块")

        return grid_blocks

    def _is_functional_grid(self, grid_content: str, grid_line: int, all_lines: List[str]) -> bool:
        """
        判断grid块是否包含功能设计内容

        Args:
            grid_content: grid块内容
            grid_line: grid块起始行号
            all_lines: 文档所有行

        Returns:
            是否为功能相关的grid块
        """
        content_lower = grid_content.lower()

        # 绝对跳过的非功能内容关键词
        skip_keywords = [
            # 项目管理类
            "项目背景", "产品概述", "业务目标", "需求背景", "用户故事", "业务场景",
            "技术架构", "系统设计", "数据流程", "架构图", "系统图",
            "测试计划", "上线计划", "项目里程碑", "时间计划", "项目排期",
            "团队信息", "联系方式", "会议记录", "项目成员", "角色分工",

            # 文档结构类
            "目录", "索引", "版本历史", "变更记录", "文档说明", "引言",
            "术语解释", "缩略语", "参考文献", "相关文档", "附录",

            # 非功能性需求
            "性能要求", "安全要求", "可用性", "兼容性", "可维护性", "可扩展性",
            "非功能性需求", "质量属性", "技术约束", "业务约束",

            # 管理和流程
            "开发流程", "发布流程", "部署流程", "监控方案", "运维方案",
            "数据治理", "质量保证", "风险管理", "问题跟踪"
        ]

        # 检查是否包含跳过关键词
        for keyword in skip_keywords:
            if keyword in content_lower:
                return False

        # 检查上下文是否为非功能内容
        context_before = self._get_context_before_grid(grid_line, all_lines, 5)
        context_lower = context_before.lower()

        context_skip_keywords = [
            "项目背景", "产品概述", "需求背景", "技术架构", "系统设计",
            "团队介绍", "项目计划", "文档说明", "引言部分"
        ]

        for keyword in context_skip_keywords:
            if keyword in context_lower:
                return False

        # 检查是否为纯图片描述（没有字段信息）
        has_field_indicators = any(indicator in content_lower for indicator in [
            "字段", "field", "参数", "parameter", "属性", "attribute",
            "维度", "dimension", "指标", "metric", "数据", "data"
        ])

        has_function_indicators = any(indicator in content_lower for indicator in [
            "功能", "function", "接口", "interface", "查询", "query",
            "筛选", "filter", "搜索", "search", "列表", "list",
            "分析", "analysis", "统计", "statistics", "报表", "report"
        ])

        # 如果既没有字段指标也没有功能指标，很可能是非功能内容
        if not has_field_indicators and not has_function_indicators:
            # 检查是否包含功能相关的标题词汇
            functional_title_keywords = [
                "筛选", "查询", "列表", "分析", "统计", "报表", "导出", "管理", "设置", "配置"
            ]
            has_functional_title = any(keyword in content_lower for keyword in functional_title_keywords)

            # 额外检查：如果是纯图片或界面描述，跳过
            if not has_functional_title:
                return False

            # 如果有标题但没有字段，检查是否只是界面描述
            interface_keywords = ["截图", "图片", "界面", "原型", "示意图", "展示", "效果图", "界面图"]
            has_only_ui_description = any(keyword in content_lower for keyword in interface_keywords) and \
                                      not any(keyword in content_lower for keyword in ["字段", "参数", "数据"])

            if has_only_ui_description:
                return False

        return True

    def _get_context_before_grid(self, grid_line: int, all_lines: List[str], max_lines: int) -> str:
        """
        获取grid块前面的上下文内容

        Args:
            grid_line: grid块起始行号
            all_lines: 文档所有行
            max_lines: 最多获取的行数

        Returns:
            上下文内容
        """
        context_lines = []
        for i in range(max(0, grid_line - max_lines), grid_line):
            if i < len(all_lines):
                line = all_lines[i].strip()
                if line and not line.startswith('```'):
                    context_lines.append(line)

        return ' '.join(context_lines)

    def _get_skip_reason(self, grid_content: str) -> str:
        """
        获取跳过grid块的原因

        Args:
            grid_content: grid块内容

        Returns:
            跳过原因
        """
        content_lower = grid_content.lower()

        if "项目背景" in content_lower or "产品概述" in content_lower:
            return "项目背景/产品概述"
        elif "技术架构" in content_lower or "系统设计" in content_lower:
            return "技术架构/系统设计"
        elif "团队" in content_lower or "会议" in content_lower:
            return "团队/会议信息"
        elif "计划" in content_lower or "里程碑" in content_lower:
            return "项目计划/里程碑"
        elif not any(indicator in content_lower for indicator in ["字段", "功能", "接口", "数据"]):
            return "无功能/字段信息"
        else:
            return "其他非功能内容"

    def extract_context_around_grid(self, content: str, grid_start: int, context_size: Optional[int] = None) -> str:
        """
        提取grid块周围的上下文，特别关注标题信息
        优先获取grid块前面最近的标题作为上下文
        """
        if context_size is None:
            context_size = understand_doc_config.CONTEXT_SIZE

        lines = content.split('\n')

        # 分两个阶段：先找标题，再收集描述
        best_title = None
        best_title_line = -1

        # 第一阶段：向上寻找最佳标题
        for i in range(grid_start - 1, max(-1, grid_start - context_size - 1), -1):
            if i < 0:
                break

            line = lines[i].strip()

            # 最高优先级：markdown标题（## ### #）
            if line.startswith('#') or line.startswith('##') or line.startswith('###'):
                best_title = lines[i]  # 保留原始格式（包括#）
                best_title_line = i
                break  # 找到markdown标题就立即停止，这是最理想的标题

            # 次高优先级：包含明确功能关键词的短行
            elif (not best_title and
                  len(line) < understand_doc_config.MAX_TITLE_LENGTH and
                  line and
                  not line.startswith('```') and
                  not line.startswith('!') and
                  any(keyword in line for keyword in understand_doc_config.TITLE_KEYWORDS)):
                best_title = line
                best_title_line = i
                # 继续向上搜索，看是否有更好的markdown标题

            # 第三优先级：冒号结尾的标题
            elif (not best_title and
                  (line.endswith('：') or line.endswith(':')) and
                  len(line) < understand_doc_config.MAX_TITLE_LENGTH):
                best_title = line
                best_title_line = i
                # 继续向上搜索，看是否有更好的标题

        # 第二阶段：收集标题后的描述性内容（如果标题不是直接紧贴grid）
        context_lines = []

        if best_title:
            context_lines.append(best_title)

            # 在标题和grid之间收集描述性内容（最多2行）
            for i in range(best_title_line + 1, grid_start):
                if i >= len(lines):
                    break

                line = lines[i].strip()

                # 遇到新的标题、代码块、空行等就停止
                if (not line or
                    line.startswith('#') or
                    line.startswith('```') or
                    line.startswith('!') or
                    any(line.startswith(stop_word) for stop_word in understand_doc_config.CONTENT_STOP_KEYWORDS)):
                    break

                # 收集描述性内容
                if len(line) < understand_doc_config.MAX_DESCRIPTION_LENGTH:
                    context_lines.append(lines[i])

                # 最多收集2行描述
                if len(context_lines) >= understand_doc_config.MAX_CONTEXT_LINES + 1:  # 标题 + 最多2行描述
                    break

        # 第三阶段：如果没有找到标题，回退到描述性文本
        if not context_lines:
            # 收集grid前面的几行描述性文本
            for i in range(grid_start - 1, max(-1, grid_start - 5), -1):
                if i < 0:
                    break
                line = lines[i].strip()
                if line and not line.startswith('```') and not line.startswith('!'):
                    context_lines.insert(0, lines[i])
                    if len(context_lines) >= 2:
                        break

        # 最后的回退：最近的非空行
        if not context_lines:
            for i in range(grid_start - 1, max(-1, grid_start - 3), -1):
                if i < 0:
                    break
                line = lines[i].strip()
                if line and not line.startswith('```'):
                    context_lines.insert(0, lines[i])
                    break

        return '\n'.join(context_lines)

    def find_grid_position_in_document(self, grid_content: str, full_document: str) -> int:
        """
        在完整文档中找到grid块的真正起始行号
        使用更精确的匹配算法
        """
        lines = full_document.split('\n')
        grid_lines = grid_content.split('\n')

        # 提取grid块的标识内容（前几行用于匹配）
        grid_identifier_lines = []
        for line in grid_lines[:understand_doc_config.GRID_IDENTIFIER_LINES]:  # 取前5行作为标识
            if line.strip():
                grid_identifier_lines.append(line.strip())

        if not grid_identifier_lines:
            return 0

        best_match = -1
        best_match_score = 0

        # 寻找最佳匹配位置
        for i, line in enumerate(lines):
            if line.strip().startswith('```grid'):
                # 找到grid开始，计算匹配分数
                match_score = 0
                for j, identifier_line in enumerate(grid_identifier_lines):
                    if i + j < len(lines):
                        doc_line = lines[i + j].strip()
                        if doc_line == identifier_line:
                            match_score += 1
                        elif identifier_line in doc_line or doc_line in identifier_line:
                            match_score += 0.5

                # 更新最佳匹配
                if match_score > best_match_score and match_score >= len(grid_identifier_lines) * understand_doc_config.GRID_MATCH_THRESHOLD:
                    best_match = i
                    best_match_score = match_score

        # 如果找到匹配，返回最佳位置
        if best_match >= 0:
            return best_match

        # 备用方法：使用内容片段搜索
        if len(grid_lines) >= 2:
            # 使用grid内容中的独特片段进行搜索
            content_fragments = []
            for line in grid_lines[1:10]:  # 跳过```grid，取内容部分
                line = line.strip()
                if (line and len(line) > understand_doc_config.GRID_FRAGMENT_MIN_LENGTH and
                    not line.startswith('```') and not line.startswith('grid_column')):
                    content_fragments.append(line)

            for fragment in content_fragments[:understand_doc_config.GRID_CONTENT_FRAGMENTS]:  # 只用前3个片段搜索
                for i, doc_line in enumerate(lines):
                    if fragment in doc_line or doc_line in fragment:
                        # 向前查找grid开始标记
                        for j in range(max(0, i - 5), i + 1):
                            if lines[j].strip().startswith('```grid'):
                                return j
                        return i

        # 最后回退：简单字符串搜索
        if grid_content in full_document:
            before_content = full_document.split(grid_content)[0]
            return before_content.count('\n')

        return 0

    def split_document_for_parallel_processing(self, content: str, max_interfaces_per_chunk: Optional[int] = None) -> List[str]:
        """
        将文档分割成适合并行处理的块
        每个块包含多个grid块，但不超过max_interfaces_per_chunk
        """
        if max_interfaces_per_chunk is None:
            max_interfaces_per_chunk = understand_doc_config.MAX_INTERFACES_PER_CHUNK

        grid_blocks = self.extract_grid_blocks(content)

        if not grid_blocks:
            return [content]  # 如果没有grid块，返回原始内容

        chunks = []
        current_chunk_blocks = []
        current_chunk_size = 0

        for grid_content, grid_start in grid_blocks:
            if current_chunk_size >= max_interfaces_per_chunk:
                # 当前的块已满，开始新块
                if current_chunk_blocks:
                    chunk_content = '\n\n'.join(current_chunk_blocks)
                    chunks.append(chunk_content)
                current_chunk_blocks = [grid_content]
                current_chunk_size = 1
            else:
                current_chunk_blocks.append(grid_content)
                current_chunk_size += 1

        # 添加最后一个块
        if current_chunk_blocks:
            chunk_content = '\n\n'.join(current_chunk_blocks)
            chunks.append(chunk_content)

        return chunks

    def get_grid_statistics(self, content: str) -> dict:
        """
        获取文档中grid块的统计信息
        """
        grid_blocks = self.extract_grid_blocks(content)

        stats = {
            "total_grid_blocks": len(grid_blocks),
            "total_grid_content_length": sum(len(content) for content, _ in grid_blocks),
            "average_grid_length": 0,
            "grid_positions": [start for _, start in grid_blocks]
        }

        if grid_blocks:
            stats["average_grid_length"] = stats["total_grid_content_length"] // len(grid_blocks)

        return stats

    def validate_grid_content(self, grid_content: str) -> Tuple[bool, List[str]]:
        """
        验证grid块内容的有效性
        """
        errors = []

        if not grid_content.strip():
            errors.append("Grid内容为空")
            return False, errors

        if not grid_content.startswith('```grid'):
            errors.append("Grid块缺少开始标记")

        if not grid_content.rstrip().endswith('```'):
            errors.append("Grid块缺少结束标记")

        if 'grid_column:' not in grid_content:
            errors.append("Grid块缺少grid_column定义")

        # 检查是否有content内容
        if 'content:' not in grid_content:
            errors.append("Grid块缺少content内容")

        return len(errors) == 0, errors


def create_grid_parser(trace_id: str = "", step_name: str = "") -> GridParser:
    """
    创建Grid解析器实例
    """
    return GridParser(trace_id, step_name)