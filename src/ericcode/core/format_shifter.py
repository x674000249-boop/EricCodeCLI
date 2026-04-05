"""
EricCode Format Shifter

智能格式转换工具

功能：
- 支持多种格式间的相互转换
- 理解用户意图进行智能转换
- 支持从文件或标准输入读取内容
- 支持输出到文件或标准输出
- 支持常见格式：JSON、CSV、Markdown、YAML、XML等
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from ..providers.base import (
    GenerationOptions,
    Message,
    MessageRole,
    ModelResponse,
)
from ..providers.router import get_model_router

logger = logging.getLogger(__name__)


@dataclass
class FormatResult:
    """格式转换结果"""
    converted_text: str  # 转换后的文本
    input_format: str  # 输入格式
    output_format: str  # 输出格式
    success: bool  # 是否成功
    error_message: Optional[str] = None  # 错误信息


class FormatShifter:
    """
    格式转换工具
    
    智能地将一种格式转换为另一种格式
    """
    
    def __init__(self):
        self._router = get_model_router()
    
    def detect_format(self, text: str) -> str:
        """
        自动检测文本格式
        
        Args:
            text: 要检测的文本
            
        Returns:
            检测到的格式
        """
        text = text.strip()
        
        # 检测JSON
        if text.startswith("{") and text.endswith("}"):
            try:
                json.loads(text)
                return "json"
            except:
                pass
        
        # 检测YAML
        if text.startswith("---") or re.match(r"^\w+:\s", text, re.MULTILINE):
            try:
                yaml.safe_load(text)
                return "yaml"
            except:
                pass
        
        # 检测CSV
        if "\n" in text:
            lines = text.split("\n")
            if len(lines) > 1:
                delimiter = ","
                if lines[0].count(",") > lines[0].count(";"):
                    delimiter = ","
                else:
                    delimiter = ";"
                
                if all(line.count(delimiter) == lines[0].count(delimiter) for line in lines if line.strip()):
                    return "csv"
        
        # 检测Markdown
        if any(pattern in text for pattern in ["# ", "## ", "### ", "```", "![", "[", "|" ]):
            return "markdown"
        
        # 默认为文本
        return "text"
    
    async def convert(self, text: str, output_format: str, input_format: Optional[str] = None) -> FormatResult:
        """
        转换文本格式
        
        Args:
            text: 要转换的文本
            output_format: 输出格式
            input_format: 输入格式，None表示自动检测
            
        Returns:
            FormatResult对象
        """
        # 检测输入格式
        if not input_format:
            input_format = self.detect_format(text)
        
        try:
            # 尝试使用内置转换器
            converted = self._convert_with_builtin(text, input_format, output_format)
            if converted:
                return FormatResult(
                    converted_text=converted,
                    input_format=input_format,
                    output_format=output_format,
                    success=True,
                )
            
            # 使用AI进行转换
            return await self._convert_with_ai(text, input_format, output_format)
            
        except Exception as e:
            logger.error(f"格式转换失败: {e}")
            return FormatResult(
                converted_text="",
                input_format=input_format,
                output_format=output_format,
                success=False,
                error_message=str(e),
            )
    
    def _convert_with_builtin(self, text: str, input_format: str, output_format: str) -> Optional[str]:
        """
        使用内置方法进行格式转换
        
        Args:
            text: 要转换的文本
            input_format: 输入格式
            output_format: 输出格式
            
        Returns:
            转换后的文本，None表示需要使用AI
        """
        # JSON <-> YAML
        if (input_format == "json" and output_format == "yaml") or (input_format == "yaml" and output_format == "json"):
            try:
                if input_format == "json":
                    data = json.loads(text)
                    return yaml.dump(data, default_flow_style=False, allow_unicode=True)
                else:
                    data = yaml.safe_load(text)
                    return json.dumps(data, indent=2, ensure_ascii=False)
            except:
                pass
        
        # JSON -> Markdown table
        if input_format == "json" and output_format == "markdown":
            try:
                data = json.loads(text)
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    # 生成Markdown表格
                    headers = list(data[0].keys())
                    table = ["| " + " | ".join(headers) + " |"]
                    table.append("| " + " | ".join(["---"] * len(headers)) + " |")
                    for item in data:
                        row = []
                        for header in headers:
                            value = item.get(header, "")
                            row.append(str(value))
                        table.append("| " + " | ".join(row) + " |")
                    return "\n".join(table)
            except:
                pass
        
        return None
    
    async def _convert_with_ai(self, text: str, input_format: str, output_format: str) -> FormatResult:
        """
        使用AI进行格式转换
        
        Args:
            text: 要转换的文本
            input_format: 输入格式
            output_format: 输出格式
            
        Returns:
            FormatResult对象
        """
        # 构建系统提示词
        system_prompt = f"""
你是一个专业的格式转换专家，擅长在各种数据格式之间进行转换。

任务：
- 将以下{input_format}格式的内容转换为{output_format}格式
- 确保转换后的格式正确无误
- 保持数据的完整性和准确性
- 不要添加任何额外的解释或说明

输入：
{text}

输出：
仅输出转换后的{output_format}格式内容，不要包含其他任何内容。
        """
        
        # 构建消息列表
        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
        ]
        
        # 调用模型
        response, _ = await self._router.route(
            messages,
            GenerationOptions(temperature=0.1, max_tokens=2000),
        )
        
        return FormatResult(
            converted_text=response.content.strip(),
            input_format=input_format,
            output_format=output_format,
            success=True,
        )
    
    async def convert_file(self, input_path: Path, output_path: Path, output_format: str, input_format: Optional[str] = None) -> FormatResult:
        """
        转换文件格式
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            output_format: 输出格式
            input_format: 输入格式，None表示自动检测
            
        Returns:
            FormatResult对象
        """
        # 读取文件
        text = input_path.read_text(encoding="utf-8")
        
        # 转换
        result = await self.convert(text, output_format, input_format)
        
        # 写入输出
        if result.success:
            output_path.write_text(result.converted_text, encoding="utf-8")
        
        return result


async def convert_text(text: str, output_format: str, input_format: Optional[str] = None) -> FormatResult:
    """
    转换文本格式的便捷函数
    
    Args:
        text: 要转换的文本
        output_format: 输出格式
        input_format: 输入格式
        
    Returns:
        FormatResult对象
    """
    shifter = FormatShifter()
    return await shifter.convert(text, output_format, input_format)


async def convert_file(input_path: str, output_path: str, output_format: str, input_format: Optional[str] = None) -> FormatResult:
    """
    转换文件格式的便捷函数
    
    Args:
        input_path: 输入文件路径
        output_path: 输出文件路径
        output_format: 输出格式
        input_format: 输入格式
        
    Returns:
        FormatResult对象
    """
    shifter = FormatShifter()
    return await shifter.convert_file(Path(input_path), Path(output_path), output_format, input_format)
