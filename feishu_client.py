"""
飞书文档客户端
实现飞书文档 URL 到 Markdown 的转换功能
"""

import re
import json
import requests
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from urllib.parse import urlparse
from feishu_auth import init_feishu_auth_from_env


@dataclass
class FeishuBlock:
    """飞书文档块数据结构"""
    block_id: str
    block_type: int
    parent_id: str
    children: List[str]
    data: Dict[str, Any]


class FeishuDocClient:
    """飞书文档客户端"""

    def __init__(self, token: Optional[str] = None):
        """
        初始化客户端

        Args:
            token: 飞书访问 token (Bearer xxx)，如果为 None 则会尝试自动获取
        """
        self.base_url = "https://open.feishu.cn/open-apis/docx/v1"
        self.auth_client = None
        self.token = token

        # 如果没有提供 token，尝试自动获取
        if not token:
            self.auth_client = init_feishu_auth_from_env()
            if self.auth_client:
                try:
                    fresh_token = self.auth_client.get_tenant_access_token()
                    self.token = f"Bearer {fresh_token}"
                except Exception as e:
                    print(f"[WARN] 自动获取访问令牌失败: {e}")
                    self.token = None
        else:
            # 确保格式正确
            if not token.startswith("Bearer "):
                self.token = f"Bearer {token}"

        self._update_headers()

    def _update_headers(self):
        """更新请求头"""
        if self.token:
            self.headers = {
                "Authorization": self.token,
                "Content-Type": "application/json"
            }
        else:
            self.headers = {
                "Content-Type": "application/json"
            }

    def _ensure_valid_token(self):
        """确保令牌有效"""
        if self.auth_client:
            try:
                fresh_token = self.auth_client.get_tenant_access_token()
                self.token = f"Bearer {fresh_token}"
                self._update_headers()
            except Exception as e:
                print(f"[WARN] 刷新访问令牌失败: {e}")
                raise Exception("无法获取有效的访问令牌")

        if not self.token:
            raise Exception("未配置有效的飞书访问令牌")

    def extract_document_id(self, feishu_url: str) -> str:
        """
        从飞书 URL 中提取文档 ID

        Args:
            feishu_url: 飞书文档 URL

        Returns:
            文档 ID
        """
        # 支持 wiki 和 docx 两种格式
        # https://xxx.feishu.cn/wiki/{doc_id}
        # https://xxx.feishu.cn/docx/{doc_id}
        pattern = r'/wiki/([^/?]+)|/docx/([^/?]+)'
        match = re.search(pattern, feishu_url)

        if match:
            return match.group(1) or match.group(2)

        raise ValueError(f"无法从 URL 中提取文档 ID: {feishu_url}")

    def fetch_blocks(self, document_id: str, page_size: int = 500) -> List[FeishuBlock]:
        """
        获取文档的所有块

        Args:
            document_id: 文档 ID
            page_size: 每页大小，默认 500

        Returns:
            文档块列表
        """
        all_blocks = []
        page_token = None

        while True:
            # 确保令牌有效
            self._ensure_valid_token()

            url = f"{self.base_url}/documents/{document_id}/blocks"
            params = {
                "document_revision_id": -1,  # 最新版本
                "page_size": page_size
            }

            if page_token:
                params["page_token"] = page_token

            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                response.raise_for_status()

                data = response.json()

                if data.get("code") != 0:
                    raise Exception(f"飞书 API 错误: {data.get('msg', 'Unknown error')}")

                items = data.get("data", {}).get("items", [])

                # 转换为 FeishuBlock 对象
                for item in items:
                    block = FeishuBlock(
                        block_id=item["block_id"],
                        block_type=item["block_type"],
                        parent_id=item.get("parent_id", ""),
                        children=item.get("children", []),
                        data=item
                    )
                    all_blocks.append(block)

                # 检查是否还有更多数据
                has_more = data.get("data", {}).get("has_more", False)
                if not has_more:
                    break

                # 获取下一页的 token
                page_token = data.get("data", {}).get("page_token")

            except requests.RequestException as e:
                raise Exception(f"请求飞书 API 失败: {str(e)}")

        return all_blocks

    def convert_block_to_text(self, block: FeishuBlock, level: int = 0) -> str:
        """
        将单个块转换为文本

        Args:
            block: 飞书块
            level: 缩进级别（用于列表）

        Returns:
            转换后的文本
        """
        block_type = block.block_type
        data = block.data

        # block_type 映射表
        if block_type == 1:
            # page / 根节点
            elements = data.get("page", {}).get("elements", [])
            return self._extract_text_from_elements(elements)

        elif block_type == 2:
            # 段落
            elements = data.get("text", {}).get("elements", [])
            return self._extract_text_from_elements(elements)

        elif block_type == 3:
            # 一级标题
            elements = data.get("heading1", {}).get("elements", [])
            text = self._extract_text_from_elements(elements)
            return f"# {text}"

        elif block_type == 4:
            # 二级标题
            elements = data.get("heading2", {}).get("elements", [])
            text = self._extract_text_from_elements(elements)
            return f"## {text}"

        elif block_type == 12:
            # 列表项
            elements = data.get("bullet", {}).get("elements", [])
            text = self._extract_text_from_elements(elements)
            indent = "  " * level
            return f"{indent}- {text}"

        elif block_type == 25:
            # grid_column 在父级grid容器中处理，这里不输出
            return ""

        else:
            # 未处理类型
            return f"[unknown_{block_type}]"

    def _extract_text_from_elements(self, elements: List[Dict]) -> str:
        """
        从元素列表中提取文本

        Args:
            elements: 元素列表

        Returns:
            提取的文本
        """
        text_parts = []

        for element in elements:
            if "text_run" in element:
                content = element["text_run"].get("content", "")
                text_parts.append(content)
            elif "mention_user" in element:
                # 用户提及，转换为 @user_id 格式
                user_id = element["mention_user"].get("user_id", "")
                text_parts.append(f"@{user_id}")
            # 忽略其他类型（图片、表格等）

        return "".join(text_parts)

    def _convert_grid_to_markdown(self, grid_block: FeishuBlock, block_dict: Dict[str, FeishuBlock]) -> str:
        """
        将grid容器转换为指定的markdown格式

        Args:
            grid_block: grid容器块
            block_dict: ID 到块的映射

        Returns:
            转换后的markdown文本
        """
        try:
            grid_columns = []

            # 获取所有grid_column子块
            for child_id in grid_block.children:
                if child_id in block_dict:
                    child_block = block_dict[child_id]
                    if child_block.block_type == 25:  # grid_column
                        column_content = self._extract_grid_column_content(child_block, block_dict)
                        if column_content:
                            grid_columns.append(column_content)

            if not grid_columns:
                return ""

            # 生成指定格式的markdown
            markdown_lines = ["```grid"]

            # 处理每个列
            for i, column in enumerate(grid_columns):
                markdown_lines.append(f"  grid_column:")

                # 合并列的所有内容
                all_content = []
                for item in column:
                    if item.get("type") == "image":
                        all_content.append(f"[{item.get('name', 'image')}]")
                    elif item.get("type") == "text":
                        all_content.extend(item.get("content", []))

                # 添加width_ratio和content
                width_ratio = column[0].get("width_ratio", 50) if column else 50
                markdown_lines.append(f"    - width_ratio:{width_ratio}")
                markdown_lines.append(f"      content:|")

                # 添加内容行（每行前面加8个空格）
                for line in all_content:
                    markdown_lines.append(f"        {line}")

            markdown_lines.append("```")

            return "\n".join(markdown_lines)

        except Exception as e:
            print(f"[WARN] 转换grid失败: {e}")
            return ""

    def _extract_grid_column_content(self, column_block: FeishuBlock, block_dict: Dict[str, FeishuBlock]) -> List[Dict]:
        """
        提取grid列的内容，按照子块顺序提取

        Args:
            column_block: grid列块
            block_dict: ID 到块的映射

        Returns:
            列内容列表
        """
        column_content = []
        text_items = []

        # 处理列的子块，按顺序处理
        for child_id in column_block.children:
            if child_id in block_dict:
                child_block = block_dict[child_id]

                # 处理图片块
                if child_block.block_type == 13:  # image block
                    # 保存之前的文本内容
                    if text_items:
                        column_content.append({
                            "type": "text",
                            "content": text_items,
                            "width_ratio": 50
                        })
                        text_items = []

                    image_info = self._extract_image_info(child_block)
                    if image_info:
                        column_content.append({
                            "type": "image",
                            "name": image_info["name"],
                            "width_ratio": 50
                        })

                # 处理文本块和列表块
                elif child_block.block_type in [1, 2, 12]:  # page, text, bullet
                    text_content = self.convert_block_to_text(child_block)
                    if text_content.strip():
                        text_items.append(text_content)

        # 保存剩余的文本内容
        if text_items:
            column_content.append({
                "type": "text",
                "content": text_items,
                "width_ratio": 50
            })

        # 处理列的直接内容
        if "grid_column" in column_block.data:
            grid_data = column_block.data["grid_column"]
            # 提取列的文本内容
            if "elements" in grid_data:
                text_content = self._extract_text_from_elements(grid_data["elements"])
                if text_content.strip():
                    column_content.append({
                        "type": "text",
                        "content": [text_content],
                        "width_ratio": 50
                    })

        return column_content

    def _extract_image_info(self, image_block: FeishuBlock) -> Optional[Dict]:
        """
        提取图片信息

        Args:
            image_block: 图片块

        Returns:
            图片信息字典
        """
        try:
            if "image" in image_block.data:
                image_data = image_block.data["image"]
                token = image_data.get("token", "")
                name = image_data.get("name", "image.png")

                if token:
                    return {
                        "token": token,
                        "name": name
                    }
        except Exception as e:
            print(f"[WARN] 提取图片信息失败: {e}")

        return None

    def build_block_tree(self, blocks: List[FeishuBlock]) -> List[FeishuBlock]:
        """
        构建块树结构

        Args:
            blocks: 所有块列表

        Returns:
            根节点列表
        """
        # 建立 ID 到块的映射
        block_dict = {block.block_id: block for block in blocks}

        # 找到根节点（parent_id 为空或 block_type 为 1）
        root_blocks = [
            block for block in blocks
            if block.parent_id == "" or block.block_type == 1
        ]

        return root_blocks

    def dfs_convert_blocks(self, blocks: List[FeishuBlock], block_dict: Dict[str, FeishuBlock],
                          level: int = 0) -> List[str]:
        """
        深度优先遍历块并转换为文本

        Args:
            blocks: 当前层级的块列表
            block_dict: ID 到块的映射
            level: 缩进级别

        Returns:
            转换后的文本行列表
        """
        lines = []

        for block in blocks:
            # 检查是否是grid容器，需要特殊处理
            if block.block_type == 24:  # grid 容器
                grid_markdown = self._convert_grid_to_markdown(block, block_dict)
                if grid_markdown:
                    lines.append(grid_markdown)
            else:
                # 转换当前块
                text = self.convert_block_to_text(block, level)
                if text:  # 只添加非空文本
                    lines.append(text)

            # 处理子块（除了grid容器，因为grid容器的子块已经在_convert_grid_to_markdown中处理了）
            if block.children and block.block_type != 24:
                child_blocks = [block_dict[child_id] for child_id in block.children
                              if child_id in block_dict]
                child_lines = self.dfs_convert_blocks(child_blocks, block_dict,
                                                    level + 1 if block.block_type == 12 else level)
                lines.extend(child_lines)

        return lines

    def convert_to_markdown(self, feishu_url: str) -> Dict[str, Any]:
        """
        将飞书文档转换为 Markdown

        Args:
            feishu_url: 飞书文档 URL

        Returns:
            包含转换结果的字典
        """
        try:
            # 1. 提取文档 ID
            document_id = self.extract_document_id(feishu_url)

            # 2. 获取所有块
            blocks = self.fetch_blocks(document_id)

            # 3. 构建块树
            root_blocks = self.build_block_tree(blocks)

            # 4. 转换为文本
            block_dict = {block.block_id: block for block in blocks}
            lines = self.dfs_convert_blocks(root_blocks, block_dict)

            # 5. 拼接最终文本
            markdown_text = "\n".join(lines)

            return {
                "markdown": markdown_text,
                "blocks": [block.data for block in blocks],
                "document_id": document_id,
                "version": "-1"
            }

        except Exception as e:
            raise Exception(f"转换飞书文档失败: {str(e)}")


def feishu_url_to_markdown(feishu_url: str, feishu_token: Optional[str] = None) -> Dict[str, Any]:
    """
    便捷函数：将飞书文档 URL 转换为 Markdown

    Args:
        feishu_url: 飞书文档 URL
        feishu_token: 飞书访问 token (可选，如果为 None 则会尝试自动获取)

    Returns:
        转换结果字典
    """
    client = FeishuDocClient(feishu_token)
    return client.convert_to_markdown(feishu_url)


def create_feishu_client() -> FeishuDocClient:
    """
    创建飞书客户端，自动处理认证

    Returns:
        飞书文档客户端实例
    """
    return FeishuDocClient()


if __name__ == "__main__":
    # 测试代码
    import os

    # 示例用法
    feishu_url = "https://ecnjtt87q4e5.feishu.cn/wiki/O2NjwrNDCiRDqMkWJyfcNwd5nXe"
    feishu_token = "Bearer t-g104b1kTQ2ZXVHTAV55U7FO4NOBHLO7DSFP6SII6e"

    try:
        result = feishu_url_to_markdown(feishu_url, feishu_token)
        print("转换成功:")
        print(result["markdown"])
        print(f"总共处理了 {len(result['blocks'])} 个块")
    except Exception as e:
        print(f"转换失败: {e}")