"""
EricCode Git Smart Commit

自动分析git diff生成符合Conventional Commits规范的提交信息

功能：
- 分析代码变更内容
- 识别变更类型（feat, fix, docs, style, refactor, test, chore）
- 生成符合Conventional Commits规范的提交信息
- 支持自定义提交范围
- 支持与git commit命令集成
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..providers.base import (
    GenerationOptions,
    Message,
    MessageRole,
    ModelResponse,
)
from ..providers.router import get_model_router

logger = logging.getLogger(__name__)


@dataclass
class CommitInfo:
    """提交信息"""
    type: str  # 提交类型 (feat, fix, docs, style, refactor, test, chore)
    scope: Optional[str]  # 作用域
    subject: str  # 主题
    body: Optional[str]  # 正文
    footer: Optional[str]  # 页脚
    breaking_change: bool  # 是否有破坏性变更


class GitSmartCommit:
    """
    智能Git提交信息生成器
    
    分析git diff并生成符合Conventional Commits规范的提交信息
    """
    
    def __init__(self, repo_path: Optional[Path] = None):
        self._repo_path = repo_path or Path.cwd()
        self._router = get_model_router()
    
    def get_git_diff(self, range_: Optional[str] = None) -> str:
        """
        获取git diff输出
        
        Args:
            range_: 提交范围，例如 "HEAD~1..HEAD" 或 None（表示未暂存的变更）
            
        Returns:
            git diff的输出
        """
        try:
            if range_:
                cmd = ["git", "diff", range_]
            else:
                cmd = ["git", "diff", "--cached"]
            
            result = subprocess.run(
                cmd,
                cwd=str(self._repo_path),
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"获取git diff失败: {e}")
            return ""
    
    async def generate_commit_message(self, diff: str) -> CommitInfo:
        """
        基于git diff生成提交信息
        
        Args:
            diff: git diff的输出
            
        Returns:
            CommitInfo对象
        """
        # 构建系统提示词
        system_prompt = self._build_system_prompt()
        
        # 构建用户消息
        user_message = f"基于以下git diff生成符合Conventional Commits规范的提交信息：\n\n{diff}"
        
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
        return self._parse_response(response.content)
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """
你是一个专业的Git提交信息生成专家，精通Conventional Commits规范。

任务：
- 分析git diff内容
- 识别变更类型（feat, fix, docs, style, refactor, test, chore）
- 生成符合Conventional Commits规范的提交信息

Conventional Commits格式：
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]

类型说明：
- feat: 新功能
- fix: 修复bug
- docs: 文档变更
- style: 代码风格变更（不影响功能）
- refactor: 代码重构
- test: 测试相关
- chore: 构建过程或辅助工具的变更

输出格式：
类型: <type>
作用域: <scope>（可选）
主题: <subject>
正文: <body>（可选）
页脚: <footer>（可选）
破坏性变更: <true/false>
        """
    
    def _parse_response(self, content: str) -> CommitInfo:
        """
        解析模型响应
        
        Args:
            content: 模型的响应内容
            
        Returns:
            CommitInfo对象
        """
        lines = content.strip().split("\n")
        
        commit_info = CommitInfo(
            type="feat",
            scope=None,
            subject="",
            body=None,
            footer=None,
            breaking_change=False,
        )
        
        for line in lines:
            if line.startswith("类型:"):
                commit_info.type = line.split(":", 1)[1].strip()
            elif line.startswith("作用域:"):
                scope = line.split(":", 1)[1].strip()
                if scope and scope != "None":
                    commit_info.scope = scope
            elif line.startswith("主题:"):
                commit_info.subject = line.split(":", 1)[1].strip()
            elif line.startswith("正文:"):
                body = line.split(":", 1)[1].strip()
                if body and body != "None":
                    commit_info.body = body
            elif line.startswith("页脚:"):
                footer = line.split(":", 1)[1].strip()
                if footer and footer != "None":
                    commit_info.footer = footer
            elif line.startswith("破坏性变更:"):
                breaking_change = line.split(":", 1)[1].strip().lower()
                commit_info.breaking_change = breaking_change in ["true", "yes", "y"]
        
        return commit_info
    
    def format_commit_message(self, commit_info: CommitInfo) -> str:
        """
        格式化提交信息
        
        Args:
            commit_info: CommitInfo对象
            
        Returns:
            格式化的提交信息字符串
        """
        parts = []
        
        # 类型和作用域
        if commit_info.scope:
            parts.append(f"{commit_info.type}({commit_info.scope}): {commit_info.subject}")
        else:
            parts.append(f"{commit_info.type}: {commit_info.subject}")
        
        # 正文
        if commit_info.body:
            parts.append("")
            parts.append(commit_info.body)
        
        # 页脚
        if commit_info.footer:
            parts.append("")
            parts.append(commit_info.footer)
        
        # 破坏性变更
        if commit_info.breaking_change:
            parts.append("")
            parts.append("BREAKING CHANGE: 此变更包含破坏性修改")
        
        return "\n".join(parts)
    
    async def generate_and_commit(self, message: Optional[str] = None, range_: Optional[str] = None) -> bool:
        """
        生成提交信息并执行git commit
        
        Args:
            message: 可选的提交信息前缀
            range_: 提交范围
            
        Returns:
            是否成功提交
        """
        # 获取git diff
        diff = self.get_git_diff(range_)
        if not diff:
            logger.error("没有找到变更内容")
            return False
        
        # 生成提交信息
        commit_info = await self.generate_commit_message(diff)
        
        # 格式化提交信息
        commit_message = self.format_commit_message(commit_info)
        
        # 如果提供了消息前缀，添加到主题前
        if message:
            commit_message = commit_message.replace(": ", f": {message}: ", 1)
        
        # 执行git commit
        try:
            result = subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=str(self._repo_path),
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"提交成功: {commit_info.type}: {commit_info.subject}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"提交失败: {e}")
            return False


async def generate_commit_message(repo_path: Optional[str] = None, range_: Optional[str] = None) -> str:
    """
    生成Git提交信息的便捷函数
    
    Args:
        repo_path: 仓库路径
        range_: 提交范围
        
    Returns:
        格式化的提交信息
    """
    commit_generator = GitSmartCommit(Path(repo_path) if repo_path else None)
    diff = commit_generator.get_git_diff(range_)
    if not diff:
        return "chore: 无变更内容"
    
    commit_info = await commit_generator.generate_commit_message(diff)
    return commit_generator.format_commit_message(commit_info)


def commit(message: Optional[str] = None, repo_path: Optional[str] = None, range_: Optional[str] = None) -> bool:
    """
    生成并执行Git提交的便捷函数
    
    Args:
        message: 可选的提交信息前缀
        repo_path: 仓库路径
        range_: 提交范围
        
    Returns:
        是否成功提交
    """
    import asyncio
    commit_generator = GitSmartCommit(Path(repo_path) if repo_path else None)
    return asyncio.run(commit_generator.generate_and_commit(message, range_))
