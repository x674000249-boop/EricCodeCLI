"""
EricCode 模型提供商抽象层

定义统一的AI模型接口，支持：
- 多种后端（OpenAI、本地模型、未来扩展）
- 同步和异步调用
- 流式响应
- 统一的错误处理
- Token计数和成本追踪
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Type, Union


class MessageRole(str, Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """
    对话消息
    
    Attributes:
        role: 消息角色（系统/用户/助手/工具）
        content: 消息内容（文本或内容列表）
        name: 发送者名称（可选）
        metadata: 附加元数据
    """
    role: MessageRole
    content: Union[str, List[Dict[str, Any]]]
    name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result: Dict[str, Any] = {"role": self.role.value, "content": self.content}
        if self.name:
            result["name"] = self.name
        return result


@dataclass
class GenerationOptions:
    """
    生成选项
    
    Attributes:
        temperature: 随机性控制 (0.0-2.0)，越高越随机
        max_tokens: 最大生成的token数
        top_p: 核采样参数 (0.0-1.0)
        stop_sequences: 停止序列列表
        presence_penalty: 存在惩罚 (-2.0到2.0)
        frequency_penalty: 频率惩罚 (-2.0到2.0)
        seed: 随机种子（用于可复现性）
    """
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 1.0
    stop_sequences: Optional[List[str]] = None
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    seed: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，过滤None值"""
        result = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
        }
        
        if self.stop_sequences:
            result["stop"] = self.stop_sequences
        if self.presence_penalty != 0.0:
            result["presence_penalty"] = self.presence_penalty
        if self.frequency_penalty != 0.0:
            result["frequency_penalty"] = self.frequency_penalty
        if self.seed is not None:
            result["seed"] = self.seed
            
        return result


@dataclass
class TokenUsage:
    """
    Token使用统计
    
    Attributes:
        prompt_tokens: 输入提示的token数
        completion_tokens: 生成的token数
        total_tokens: 总token数
    """
    prompt_tokens: int = 0
    completion_tokens: int = 0
    
    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "prompt": self.prompt_tokens,
            "completion": self.completion_tokens,
            "total": self.total_tokens,
        }


@dataclass
class ModelResponse:
    """
    模型响应
    
    Attributes:
        content: 生成的文本内容
        model_used: 实际使用的模型名称
        tokens_used: Token使用统计
        finish_reason: 完成原因（stop/length/content_filter等）
        latency_ms: 响应延迟（毫秒）
        cost_usd: 成本估算（美元）
        raw_response: 原始API响应（可选）
    """
    content: str
    model_used: str
    tokens_used: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str = "stop"
    latency_ms: int = 0
    cost_usd: float = 0.0
    raw_response: Optional[Dict[str, Any]] = None
    
    @property
    def is_complete(self) -> bool:
        """检查是否正常完成"""
        return self.finish_reason == "stop"
    
    @property
    def is_truncated(self) -> bool:
        """检查是否因长度限制被截断"""
        return self.finish_reason == "length"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "model": self.model_used,
            "tokens": self.tokens_used.to_dict(),
            "finish_reason": self.finish_reason,
            "latency_ms": self.latency_ms,
            "cost_usd": round(self.cost_usd, 6),
        }


@dataclass
class StreamChunk:
    """
    流式响应块
    
    Attributes:
        content: 本次生成的内容片段
        is_final: 是否为最后一个块
        delta_tokens: 新增token数估计
        cumulative_tokens: 累计token数
    """
    content: str
    is_final: bool = False
    delta_tokens: int = 1
    cumulative_tokens: int = 0


class ModelProvider(abc.ABC):
    """
    AI模型提供商抽象基类
    
    所有具体的模型实现（OpenAI、本地模型等）都必须继承此类并实现所有抽象方法。
    
    使用示例::
    
        class MyProvider(ModelProvider):
            async def initialize(self, config):
                # 初始化连接和资源
                ...
            
            async def generate(self, messages, options):
                # 实现文本生成逻辑
                ...
            
            # ... 其他方法
    """
    
    def __init__(self):
        self._initialized = False
        self._config: Dict[str, Any] = {}
    
    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """返回提供商的唯一标识符"""
        pass
    
    @property
    @abc.abstractmethod
    def supported_models(self) -> List[str]:
        """返回支持的模型列表"""
        pass
    
    @property
    @abc.abstractmethod
    def max_context_length(self) -> int:
        """返回最大上下文长度（token数）"""
        pass
    
    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized
    
    @abc.abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """
        初始化提供商
        
        Args:
            config: 配置字典，包含API密钥、端点URL等
            
        Returns:
            初始化是否成功
        """
        pass
    
    @abc.abstractmethod
    async def generate(
        self,
        messages: List[Message],
        options: Optional[GenerationOptions] = None
    ) -> ModelResponse:
        """
        生成文本响应
        
        Args:
            messages: 消息历史列表
            options: 生成选项（温度、最大token数等）
            
        Returns:
            包含生成内容和元数据的ModelResponse对象
        """
        pass
    
    @abc.abstractmethod
    async def generate_stream(
        self,
        messages: List[Message],
        options: Optional[GenerationOptions] = None
    ) -> AsyncIterator[StreamChunk]:
        """
        流式生成文本
        
        Args:
            messages: 消息历史列表
            options: 生成选项
            
        Yields:
            StreamChunk对象，包含增量内容
        """
        pass
    
    @abc.abstractmethod
    async def get_token_count(self, text: str) -> int:
        """
        计算文本的token数量
        
        Args:
            text: 要计算的文本
            
        Returns:
            token数量估算值
        """
        pass
    
    @abc.abstractmethod
    async def health_check(self) -> bool:
        """
        健康检查
        
        Returns:
            提供商是否可用
        """
        pass
    
    @abc.abstractmethod
    async def cleanup(self) -> None:
        """清理资源（关闭连接、释放内存等）"""
        pass
    
    async def count_messages_tokens(self, messages: List[Message]) -> int:
        """计算消息列表的总token数"""
        total = 0
        for msg in messages:
            if isinstance(msg.content, str):
                total += await self.get_token_count(msg.content)
            elif isinstance(msg.content, list):
                for part in msg.content:
                    if isinstance(part, dict) and "text" in part:
                        total += await self.get_token_count(part["text"])
        return total
    
    def validate_messages(self, messages: List[Message]) -> bool:
        """验证消息格式是否正确"""
        if not messages:
            return False
        
        # 第一个消息应该是系统或用户消息
        first_role = messages[0].role
        if first_role not in [MessageRole.SYSTEM, MessageRole.USER]:
            return False
        
        # 检查消息交替模式（简化版）
        for i, msg in enumerate(messages[1:], 1):
            if msg.role == MessageRole.TOOL:
                continue  # 工具消息可以出现在任何位置
            if msg.role == MessageRole.SYSTEM and i > 0:
                return False  # 系统消息只能在开头
        
        return True
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        if not self._initialized:
            raise RuntimeError("Provider must be initialized before use")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.cleanup()
    
    def __repr__(self) -> str:
        status = "✓ initialized" if self._initialized else "✗ not initialized"
        return f"<{self.__class__.__name__} ({self.provider_name}) [{status}]>"


class ProviderError(Exception):
    """模型提供商基础异常"""
    
    def __init__(
        self,
        message: str,
        provider_name: str = "",
        error_code: str = "",
        recoverable: bool = True,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.provider_name = provider_name
        self.error_code = error_code
        self.recoverable = recoverable
        self.original_error = original_error


class AuthenticationError(ProviderError):
    """认证失败错误"""
    def __init__(self, message: str = "认证失败", **kwargs):
        super().__init__(message, error_code="AUTH_ERROR", recoverable=False, **kwargs)


class RateLimitError(ProviderError):
    """速率限制错误"""
    def __init__(self, message: str = "请求过于频繁", retry_after: float = 60.0, **kwargs):
        super().__init__(message, error_code="RATE_LIMITED", recoverable=True, **kwargs)
        self.retry_after = retry_after


class ModelOverloadedError(ProviderError):
    """模型过载错误"""
    def __init__(self, message: str = "服务过载", **kwargs):
        super().__init__(message, error_code="OVERLOADED", recoverable=True, **kwargs)


class ContextLengthExceededError(ProviderError):
    """上下文长度超限错误"""
    def __init__(self, current_length: int, max_length: int, **kwargs):
        message = f"上下文长度 {current_length} 超过限制 {max_length}"
        super().__init__(message, error_code="CONTEXT_TOO_LONG", recoverable=False, **kwargs)
        self.current_length = current_length
        self.max_length = max_length


class InvalidRequestError(ProviderError):
    """无效请求错误"""
    def __init__(self, message: str = "无效请求", **kwargs):
        super().__init__(message, error_code="INVALID_REQUEST", recoverable=False, **kwargs)


class ProviderUnavailableError(ProviderError):
    """提供商不可用错误"""
    def __init__(self, message: str = "服务不可用", **kwargs):
        super().__init__(message, error_code="UNAVAILABLE", recoverable=True, **kwargs)
