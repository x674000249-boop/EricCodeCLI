"""
EricCode 对话管理模块

提供交互式对话功能：
- 多轮对话上下文管理
- 会话历史保存和加载
- 对话模式切换
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """聊天消息"""
    role: str  # user/assistant/system
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatSession:
    """
    聊天会话
    
    管理多轮对话的上下文和历史记录。
    """
    session_id: str = ""
    messages: List[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, role: str, content: str, **kwargs) -> None:
        """添加消息"""
        message = ChatMessage(
            role=role,
            content=content,
            metadata=kwargs,
        )
        self.messages.append(message)
        self.last_activity = datetime.now()
    
    def get_context(self, max_messages: int = 10) -> str:
        """获取最近的对话上下文"""
        recent = self.messages[-max_messages:]
        
        context_parts = []
        for msg in recent:
            if msg.role == "user":
                context_parts.append(f"用户: {msg.content}")
            elif msg.role == "assistant":
                context_parts.append(f"助手: {msg.content}")
            else:
                context_parts.append(f"[{msg.role}]: {msg.content}")
        
        return "\n".join(context_parts)
    
    @property
    def message_count(self) -> int:
        return len(self.messages)


class ChatManager:
    """聊天管理器"""
    
    def __init__(self):
        self._sessions: Dict[str, ChatSession] = {}
        self._current_session_id: Optional[str] = None
    
    def create_session(self, session_id: Optional[str] = None) -> ChatSession:
        """创建新会话"""
        if not session_id:
            session_id = f"{int(time.time() * 1000)}"
        
        session = ChatSession(session_id=session_id)
        self._sessions[session_id] = session
        self._current_session_id = session_id
        
        logger.info(f"Created chat session: {session_id}")
        return session
    
    def get_current_session(self) -> Optional[ChatSession]:
        """获取当前会话"""
        if self._current_session_id:
            return self._sessions.get(self._current_session_id)
        return None
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """获取指定会话"""
        return self._sessions.get(session_id)
    
    def list_sessions(self) -> List[ChatSession]:
        """列出所有会话"""
        return list(self._sessions.values())
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            if self._current_session_id == session_id:
                self._current_session_id = None
            return True
        return False


# 全局聊天管理器实例
chat_manager = ChatManager()


class ChatSessionUI:
    """
    聊天会话用户界面（简化版）
    
    在终端中提供交互式对话体验。
    """
    
    def __init__(self):
        self.session: Optional[ChatSession] = None
        self._running = False
    
    def start(self) -> None:
        """启动交互式会话"""
        from rich.console import Console
        from rich.prompt import Prompt
        
        console = Console()
        
        # 创建或恢复会话
        self.session = chat_manager.create_session()
        
        console.print(f"\n[bold green]✨ 会话已创建 (ID: {self.session.session_id})[/]\n")
        
        # 添加系统欢迎消息
        welcome_msg = (
            "你好！我是 EricCode，你的AI编码助手。\n"
            "我可以帮你生成代码、解释代码、补全代码等。\n"
            "有什么我可以帮助你的吗？"
        )
        self.session.add_message("system", welcome_msg)
        console.print(f"[dim]{welcome_msg}[/]\n")
        
        self._running = True
        
        try:
            while self._running:
                try:
                    user_input = Prompt.ask(
                        "[bold cyan]你[/]",
                        console=console,
                    )
                    
                    if not user_input.strip():
                        continue
                    
                    # 处理特殊命令
                    if user_input.startswith("/"):
                        if self._handle_command(user_input, console):
                            continue
                    
                    # 添加用户消息
                    self.session.add_message("user", user_input)
                    
                    # TODO: 实际调用模型生成响应
                    response = self._generate_response(user_input)
                    
                    # 添加助手响应
                    self.session.add_message("assistant", response)
                    
                    console.print(f"\n[bold green]EricCode:[/] {response}\n")
                    
                except KeyboardInterrupt:
                    console.print("\n[yellow]按 Ctrl+C 再次退出[/]")
                    continue
                except EOFError:
                    break
                    
        finally:
            self._running = False
            console.print("\n[bold blue]👋 再见！感谢使用 EricCode！[/]\n")
    
    def _handle_command(self, command: str, console) -> bool:
        """处理特殊命令，返回True表示已处理"""
        cmd = command.lower().strip()
        
        if cmd in ["/exit", "/quit", "/q"]:
            self._running = False
            return True
        
        elif cmd == "/clear":
            if self.session:
                self.session.messages.clear()
                console.print("[yellow]🗑️ 对话历史已清除[/]\n")
            return True
        
        elif cmd == "/help":
            help_text = """
[bold]可用命令:[/]
  /exit, /quit, /q  - 退出对话
  /clear           - 清除对话历史
  /help            - 显示此帮助信息
  /info            - 显示当前会话信息
  /history         - 显示对话历史
"""
            console.print(help_text)
            return True
        
        elif cmd == "/info":
            if self.session:
                console.print(Panel(
                    f"[bold]会话ID:[/] {self.session.session_id}\n"
                    f"[bold]消息数:[/] {self.session.message_count}\n"
                    f"[bold]创建时间:[/] {self.session.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
                    title="📊 会话信息",
                ))
            return True
        
        elif cmd == "/history":
            if self.session and self.session.messages:
                console.print("\n[bold]📜 对话历史:[/]\n")
                for i, msg in enumerate(self.session.messages[-20:], 1):  # 最近20条
                    role_icon = "👤" if msg.role == "user" else "🤖"
                    preview = msg.content[:80] + ("..." if len(msg.content) > 80 else "")
                    console.print(f"  {i}. {role_icon} [{msg.role}] {preview}\n")
            else:
                console.print("[dim]暂无对话历史[/]\n")
            return True
        
        else:
            console.print(f"[red]未知命令: {command}[/] 输入 /help 查看可用命令\n")
            return True
        
        return False
    
    def _generate_response(self, user_input: str) -> str:
        """
        生成助手响应（占位实现）
        
        TODO: 集成实际的模型调用
        """
        # 简单的关键词匹配响应
        responses = {
            "你好": "你好！很高兴见到你。有什么编程问题需要我帮忙吗？",
            "hi": "Hi there! How can I help you with your coding today?",
            "帮助": "我可以帮你：\n• 生成代码\n• 解释代码\n• 补全代码\n• 回答技术问题\n\n请告诉我你需要什么帮助！",
            "功能": "EricCode 的主要功能包括：\n1. ✨ 代码生成 - 用自然语言描述需求\n2. 💡 代码补全 - 智能建议\n3. 📖 代码解释 - 深入理解代码\n4. 💬 对话交流 - 多轮对话",
        }
        
        # 简单匹配
        for keyword, response in responses.items():
            if keyword in user_input.lower():
                return response
        
        # 默认响应
        return (
            "我收到了你的请求。目前这是一个演示版本，完整的AI响应功能正在开发中。\n"
            "你可以尝试使用 `ericcode generate` 命令来体验代码生成功能。"
        )


def start_chat():
    """启动聊天会话的便捷函数"""
    ui = ChatSessionUI()
    ui.start()
