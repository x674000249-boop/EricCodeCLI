"""
EricCode Git 集成模块

提供Git仓库交互功能：
- 获取变更状态
- 生成智能commit message
- 分析代码差异
- 分支管理辅助
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """文件信息"""
    path: str
    status: str  # A/M/D/R/U etc.
    staged: bool = False
    
    @property
    def status_display(self) -> str:
        status_map = {
            'A': '新增',
            'M': '修改',
            'D': '删除',
            'R': '重命名',
            'U': '未跟踪',
        }
        return status_map.get(self.status, self.status)


@dataclass
class CommitInfo:
    """提交信息"""
    hash: str
    author: str
    date: datetime
    message: str


@dataclass
class DiffInfo:
    """差异信息"""
    file_path: str
    additions: int
    deletions: int
    changes_preview: str  # 前几行差异预览


@dataclass
class GitStatus:
    """Git仓库状态"""
    branch: str
    is_clean: bool
    staged_files: List[FileInfo] = field(default_factory=list)
    unstaged_files: List[FileInfo] = field(default_factory=list)
    untracked_files: List[FileInfo] = field(default_factory=list)
    ahead_count: int = 0
    behind_count: int = 0
    stash_count: int = 0


class GitIntegration:
    """
    Git集成工具
    
    提供与Git仓库的交互功能，用于增强代码生成的上下文感知能力。
    """
    
    def __init__(self, repo_path: Optional[Path] = None):
        self.repo_path = repo_path or Path.cwd()
        self._validate_git_repo()
    
    def _validate_git_repo(self):
        """验证是否是Git仓库"""
        git_dir = self.repo_path / ".git"
        
        if not git_dir.exists():
            # 向上查找.git目录
            current = self.repo_path
            while current != current.parent:
                if (current / ".git").exists():
                    self.repo_path = current
                    return
                current = current.parent
            
            raise NotAGitRepositoryError(f"不是Git仓库: {self.repo_path}")
    
    def run_git_command(
        self,
        args: List[str],
        check: bool = True,
        timeout: float = 30.0,
    ) -> subprocess.CompletedProcess:
        """执行git命令"""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "LANG": "C"},  # 确保英文输出便于解析
            )
            
            if check and result.returncode != 0:
                raise GitCommandError(
                    f"Git命令失败: {' '.join(['git'] + args)}\n"
                    f"错误: {result.stderr.strip()}"
                )
            
            return result
            
        except subprocess.TimeoutExpired:
            raise GitCommandError("Git命令超时")
        except FileNotFoundError:
            raise GitCommandError("Git命令未找到，请确保已安装Git")
    
    def get_status(self) -> GitStatus:
        """获取仓库状态"""
        # 获取当前分支
        branch_result = self.run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
        branch = branch_result.stdout.strip() or "HEAD (detached)"
        
        # 获取文件状态
        status_result = self.run_git_command(["status", "--porcelain"])
        status_lines = status_result.stdout.strip().split("\n") if status_result.stdout.strip() else []
        
        staged_files = []
        unstaged_files = []
        untracked_files = []
        
        for line in status_lines:
            if not line.strip():
                continue
            
            # Git porcelain格式: XY path
            index_status = line[0]
            work_status = line[1]
            
            # 处理重命名等特殊情况
            if " -> " in line:
                file_part = line.split(" -> ")[1].strip()
            else:
                file_part = line[3:].strip()
            
            if index_status == "?" :
                untracked_files.append(FileInfo(path=file_part, status="U"))
            elif index_status != " " and index_status != "":
                staged_files.append(FileInfo(path=file_part, status=index_status, staged=True))
                if work_status != " " and work_status != "":
                    unstaged_files.append(FileInfo(path=file_part, status=work_status))
            elif work_status != " " and work_status != "":
                unstaged_files.append(FileInfo(path=file_part, status=work_status))
        
        is_clean = len(staged_files) == 0 and len(unstaged_files) == 0 and len(untracked_files) == 0
        
        # 获取ahead/behind信息
        try:
            ahead_behind = self.run_git_command(["rev-list", "--count", "--left-right", "@{u}...@"])
            parts = ahead_behind.stdout.strip().split("\t")
            ahead_count = int(parts[1]) if len(parts) > 1 else 0
            behind_count = int(parts[0]) if len(parts) > 1 else 0
        except Exception:
            ahead_count = 0
            behind_count = 0
        
        # 获取stash数量
        try:
            stash_list = self.run_git_command(["stash", "list"])
            stash_count = len([line for line in stash_list.stdout.strip().split("\n") if line])
        except Exception:
            stash_count = 0
        
        return GitStatus(
            branch=branch,
            is_clean=is_clean,
            staged_files=staged_files,
            unstaged_files=unstaged_files,
            untracked_files=untracked_files,
            ahead_count=ahead_count,
            behind_count=behind_count,
            stash_count=stash_count,
        )
    
    def get_diff_summary(self, staged_only: bool = False) -> List[DiffInfo]:
        """获取差异摘要"""
        args = ["diff", "--stat"]
        if staged_only:
            args.insert(1, "--staged")
        
        diff_stat = self.run_git_command(args)
        diffs = []
        
        for line in diff_stat.stdout.strip().split("\n"):
            if not line.strip():
                continue
            
            # 解析: file.txt | 10 +5 -3
            match = re.match(r'(.+)\s+\|\s+(\d+)\s+([+-]+)?', line)
            if match:
                file_path = match.group(1)
                total_changes = int(match.group(2))
                signs = match.group(3) or ""
                
                additions = signs.count("+")
                deletions = signs.count("-")
                
                diffs.append(DiffInfo(
                    file_path=file_path,
                    additions=additions,
                    deletions=deletions,
                    changes_preview=f"+{additions} -{deletions} ({total_changes}行变化)",
                ))
        
        return diffs
    
    def get_recent_commits(self, count: int = 5) -> List[CommitInfo]:
        """获取最近的提交记录"""
        format_str = "%H|%an|%ai|%s"
        log_result = self.run_git_command([
            "log",
            f"-n{count}",
            f"--format={format_str}"
        ])
        
        commits = []
        for line in log_result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            
            parts = line.split("|")
            if len(parts) >= 4:
                commit_info = CommitInfo(
                    hash=parts[0][:7],  # 短hash
                    author=parts[1],
                    date=datetime.strptime(parts[2], "%Y-%m-%d %H:%M:%S %z"),
                    message="|".join(parts[3:]),  # 消息可能包含|
                )
                commits.append(commit_info)
        
        return commits
    
    def generate_commit_message(
        self,
        style: str = "conventional"
    ) -> str:
        """
        自动生成commit message
        
        Args:
            style: 消息风格 ("conventional"/"descriptive"/"emoji")
        """
        status = self.get_status()
        diffs = self.get_diff_summary(staged_only=True)
        
        if not diffs and not status.unstaged_files:
            return "chore: 无变更需要提交"
        
        all_changes = status.staged_files + status.unstaged_files
        
        # 分类变更类型
        categories = {
            "feat": [],      # 新功能
            "fix": [],       # Bug修复
            "docs": [],      # 文档
            "style": [],     # 格式化
            "refactor": [],  # 重构
            "test": [],      # 测试
            "chore": [],     # 杂项
        }
        
        for file_info in all_changes:
            path_lower = file_info.path.lower()
            
            if any(x in path_lower for x in ["readme", "doc", "md"]):
                categories["docs"].append(file_info)
            elif any(x in path_lower for x in ["test_", "_test.py", "spec"]):
                categories["test"].append(file_info)
            elif any(x in path_lower for x in ["setup", "config", "ci", "dockerfile"]):
                categories["chore"].append(file_info)
            elif file_info.status == "D":
                categories["style"].append(file_info)  # 删除归为style或直接判断
            elif file_info.status == "A":
                categories["feat"].append(file_info)
            elif any(x in path_lower for x in ["fix", "bug", "patch"]):
                categories["fix"].append(file_info)
            else:
                categories["refactor"].append(file_info)
        
        # 生成消息
        if style == "conventional":
            message_parts = []
            
            for category, files in categories.items():
                if files:
                    file_names = [f.path for f in files[:3]]  # 最多显示3个文件
                    files_str = ", ".join(file_names)
                    if len(files) > 3:
                        files_str += f" 等{len(files)}个文件"
                    
                    message_parts.append(f"{category}: {files_str}")
            
            main_type = max(categories.keys(), key=lambda k: len(categories[k])) if any(categories.values()) else "chore"
            message = f"{main_type}: {message_parts[0].split(': ')[1]}" if message_parts else "update"
            
        elif style == "emoji":
            emoji_map = {
                "feat": "✨",
                "fix": "🐛",
                "docs": "📝",
                "style": "💄",
                "refactor": "♻️",
                "test": "✅",
                "chore": "🔧",
            }
            
            emojis_used = []
            for category, files in categories.items():
                if files:
                    emojis_used.append(f"{emoji_map.get(category, '')} {len(files)}个{category}相关文件")
            
            message = " | ".join(emojis_used) if emojis_used else "📦 更新"
            
        else:  # descriptive
            changed_types = [f"{f.status_display}{f.path}" for f in all_changes[:5]]
            message = f"更新: {', '.join(changed_types)}"
            if len(all_changes) > 5:
                message += f" 等{len(all_changes)}个文件"
        
        return message
    
    def get_changed_code_context(
        self,
        max_lines_per_file: int = 50,
        include_staged: bool = True,
        include_unstaged: bool = True,
    ) -> str:
        """
        获取变更代码的上下文（用于AI生成）
        
        返回格式化的文本，适合作为AI提示词的一部分。
        """
        context_parts = [f"# Git 变更上下文\n"]
        
        status = self.get_status()
        
        if include_staged and status.staged_files:
            context_parts.append("\n## 已暂存的变更\n")
            for file_info in status.staged_files[:10]:  # 限制文件数
                try:
                    diff_result = self.run_git_command([
                        "diff", "--cached", "-U3", file_info.path
                    ])
                    lines = diff_result.stdout.strip().split("\n")
                    if len(lines) > max_lines_per_file:
                        preview = "\n".join(lines[:max_lines_per_file])
                        context_parts.append(f"\n### {file_info.path} ({file_info.status_display})\n```diff\n{preview}\n... (截断)\n```\n")
                    else:
                        context_parts.append(f"\n### {file_info.path} ({file_info.status_display})\n```diff\n{diff_result.stdout}\n```\n")
                except Exception as e:
                    logger.warning(f"获取文件差异失败 {file_info.path}: {e}")
        
        if include_unstaged and status.unstaged_files:
            context_parts.append("\n## 未暂存的变更\n")
            for file_info in status.unstaged_files[:5]:
                context_parts.append(f"- {file_info.path} ({file_info.status_display})")
        
        recent_commits = self.get_recent_commits(3)
        if recent_commits:
            context_parts.append("\n## 最近提交\n")
            for commit in recent_commits:
                context_parts.append(f"- `{commit.hash}` {commit.message[:80]}")
        
        return "\n".join(context_parts)


class NotAGitRepositoryError(Exception):
    """不是Git仓库错误"""
    pass


class GitCommandError(Exception):
    """Git命令执行错误"""
    pass


# 便捷函数
def get_git_context(repo_path: Optional[Path] = None) -> Optional[str]:
    """获取Git上下文（安全调用）"""
    try:
        git = GitIntegration(repo_path)
        return git.get_changed_code_context()
    except NotAGitRepositoryError:
        return None
    except Exception as e:
        logger.debug(f"获取Git上下文失败: {e}")
        return None


def generate_smart_commit_message(repo_path: Optional[Path] = None) -> str:
    """生成智能提交消息（便捷函数）"""
    try:
        git = GitIntegration(repo_path)
        return git.generate_commit_message(style="conventional")
    except Exception as e:
        logger.warning(f"生成commit message失败: {e}")
        return "update"
