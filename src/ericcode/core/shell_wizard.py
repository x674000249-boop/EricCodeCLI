"""
EricCode Shell Wizard

将自然语言描述转换为可执行的Shell命令

功能：
- 支持bash、zsh、PowerShell等多种shell
- 智能识别用户意图
- 生成安全的Shell命令
- 支持管道和重定向
- 提供命令解释
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..providers.base import (
    GenerationOptions,
    Message,
    MessageRole,
    ModelResponse,
)
from ..providers.router import get_model_router

logger = logging.getLogger(__name__)


@dataclass
class ShellCommand:
    """Shell命令结果"""
    command: str  # 生成的命令
    explanation: str  # 命令解释
    shell_type: str  # shell类型 (bash/zsh/powershell)
    confidence: float  # 置信度
    is_safe: bool  # 是否安全
    alternatives: List[str] = field(default_factory=list)  # 备选命令


class ShellWizard:
    """
    Shell命令生成器
    
    将自然语言描述转换为可执行的Shell命令
    """
    
    def __init__(self):
        self._router = get_model_router()
    
    async def generate_command(
        self,
        prompt: str,
        shell_type: str = "bash",
        explain: bool = True,
        safe_mode: bool = True,
    ) -> ShellCommand:
        """
        生成Shell命令
        
        Args:
            prompt: 自然语言描述
            shell_type: shell类型 (bash/zsh/powershell)
            explain: 是否生成命令解释
            safe_mode: 是否启用安全检查
            
        Returns:
            ShellCommand对象
        """
        # 构建系统提示词
        system_prompt = self._build_system_prompt(shell_type, safe_mode)
        
        # 构建用户消息
        user_message = f"将以下自然语言描述转换为{shell_type}命令：\n\n{prompt}"
        
        # 构建消息列表
        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=user_message),
        ]
        
        # 调用模型
        response, _ = await self._router.route(
            messages,
            GenerationOptions(temperature=0.3, max_tokens=1000),
        )
        
        # 解析响应
        return self._parse_response(response, shell_type, safe_mode)
    
    def _build_system_prompt(self, shell_type: str, safe_mode: bool) -> str:
        """构建系统提示词"""
        safe_mode_prompt = "\n\n安全要求：\n- 不要生成删除文件的命令（如rm -rf）\n- 不要生成修改系统配置的命令\n- 不要生成需要sudo权限的命令\n- 确保命令不会对系统造成损害"""
        
        return f"""
你是一个专业的Shell命令专家，擅长将自然语言描述转换为准确、高效的{shell_type}命令。

任务：
- 将用户的自然语言描述转换为单个、可执行的{shell_type}命令
- 命令应该简洁明了，直接解决用户的问题
- 如果需要解释，使用注释形式

输出格式：
命令

# 解释（可选）

示例：
查找当前目录下所有.txt文件

find . -name "*.txt"

# 查找当前目录及其子目录中的所有txt文件
        """ + (safe_mode_prompt if safe_mode else "")
    
    def _parse_response(self, response: ModelResponse, shell_type: str, safe_mode: bool) -> ShellCommand:
        """解析模型响应"""
        content = response.content.strip()
        
        # 分离命令和解释
        if "#" in content:
            parts = content.split("#", 1)
            command = parts[0].strip()
            explanation = "#" + parts[1].strip()
        else:
            command = content
            explanation = ""
        
        # 提取命令（去除可能的代码块标记）
        if command.startswith("```"):
            lines = command.split("\n")
            # 移除代码块标记
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            command = "\n".join(lines).strip()
        
        # 安全检查
        is_safe = self._check_safety(command) if safe_mode else True
        
        return ShellCommand(
            command=command,
            explanation=explanation,
            shell_type=shell_type,
            confidence=0.9,  # 暂时固定置信度
            is_safe=is_safe,
        )
    
    def _check_safety(self, command: str) -> bool:
        """检查命令安全性"""
        dangerous_patterns = [
            "rm -rf",
            "sudo ",
            "> /etc/",
            ">> /etc/",
            "format ",
            "mkfs.",
            "dd if=",
        ]
        
        for pattern in dangerous_patterns:
            if pattern in command.lower():
                return False
        
        return True


def generate_shell_command(
    prompt: str,
    shell_type: str = "bash",
    explain: bool = True,
    safe_mode: bool = True,
) -> ShellCommand:
    """
    生成Shell命令的便捷函数
    
    Args:
        prompt: 自然语言描述
        shell_type: shell类型
        explain: 是否生成解释
        safe_mode: 是否启用安全检查
        
    Returns:
        ShellCommand对象
    """
    import asyncio
    wizard = ShellWizard()
    return asyncio.run(wizard.generate_command(prompt, shell_type, explain, safe_mode))
