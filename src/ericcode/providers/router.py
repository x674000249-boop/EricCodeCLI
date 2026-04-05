"""
EricCode 模型路由器

智能选择和切换AI模型提供商：
- 根据任务类型选择最优模型
- 自动故障转移（fallback）
- 负载均衡
- 成本优化
- 离线模式支持
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Tuple

from ..providers.base import (
    GenerationOptions,
    Message,
    MessageRole,
    ModelProvider,
    ModelResponse,
    ProviderError,
)

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """任务类型"""
    CODE_GENERATION = "code_generation"
    CODE_COMPLETION = "code_completion"
    CODE_EXPLANATION = "code_explanation"
    DEBUG_ASSISTANCE = "debug_assistance"
    REFACTORING = "refactoring"
    GENERAL_CHAT = "general_chat"
    DOCUMENTATION = "documentation"
    TEST_GENERATION = "test_generation"


@dataclass
class ProviderConfig:
    """提供商配置"""
    provider: ModelProvider
    priority: int = 1  # 数字越小优先级越高
    weight: float = 1.0  # 负载均衡权重
    enabled: bool = True
    max_concurrent: int = 5  # 最大并发请求数
    current_requests: int = 0
    
    @property
    def is_available(self) -> bool:
        return self.enabled and self.current_requests < self.max_concurrent


@dataclass
class RoutingDecision:
    """路由决策结果"""
    selected_provider: str
    task_type: TaskType
    reason: str
    fallback_providers: List[str]
    estimated_cost_usd: float = 0.0
    estimated_latency_ms: float = 0.0


class ModelRouter:
    """
    模型路由器
    
    智能管理多个模型提供商，根据任务特性自动选择最优后端。
    
    特性：
    - 基于任务类型的自动路由
    - 故障转移机制
    - 成本感知调度
    - 性能监控
    """
    
    # 任务类型到推荐模型的映射
    TASK_MODEL_MAPPING = {
        TaskType.CODE_GENERATION: {
            "primary": ["openai:gpt-4o", "local:DeepSeek-Coder-6.7B"],
            "fallback": ["openai:gpt-4o-mini", "local:CodeLlama-7B"],
            "reason": "代码生成需要强大的推理能力",
        },
        TaskType.CODE_COMPLETION: {
            "primary": ["local:DeepSeek-Coder-6.7B", "openai:gpt-4o-mini"],
            "fallback": ["local:CodeLlama-7B", "openai:gpt-4o"],
            "reason": "补全需要低延迟，优先使用本地模型",
        },
        TaskType.CODE_EXPLANATION: {
            "primary": ["openai:gpt-4o"],
            "fallback": ["openai:gpt-4o-mini", "local:Qwen2.5-Coder-7B"],
            "reason": "解释需要深度理解，使用最强模型",
        },
        TaskType.DEBUG_ASSISTANCE: {
            "primary": ["openai:o1-mini"],
            "fallback": ["openai:gpt-4o", "local:CodeLlama-13B"],
            "reason": "调试需要强推理能力",
        },
        TaskType.GENERAL_CHAT: {
            "primary": ["openai:gpt-4o-mini"],
            "fallback": ["openai:gpt-4o", "local:Qwen2.5-Coder-7B"],
            "reason": "一般对话使用轻量模型以节省成本",
        },
    }
    
    # 模型成本估算（每1K tokens）
    MODEL_COSTS = {
        "openai:gpt-4o": 0.01,
        "openai:gpt-4o-mini": 0.00075,
        "openai:o1-mini": 0.0075,
        "local:*": 0.0,  # 本地模型无直接成本
    }
    
    def __init__(self):
        self._providers: Dict[str, ProviderConfig] = {}
        self._task_history: List[Dict[str, Any]] = []
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # 统计信息
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "fallback_count": 0,
            "provider_usage": {},
        }
    
    def register_provider(
        self,
        name: str,
        provider: ModelProvider,
        priority: int = 1,
        weight: float = 1.0,
        enabled: bool = True,
    ):
        """
        注册模型提供商
        
        Args:
            name: 提供商标识符 (如 "openai:gpt-4o")
            provider: 提供商实例
            priority: 优先级（数字越小越优先）
            weight: 负载均衡权重
            enabled: 是否启用
        """
        config = ProviderConfig(
            provider=provider,
            priority=priority,
            weight=weight,
            enabled=enabled,
        )
        self._providers[name] = config
        self._circuit_breakers[name] = CircuitBreaker(name=name)
        
        logger.info(f"注册提供商: {name} (priority={priority}, weight={weight})")
    
    async def route(
        self,
        messages: List[Message],
        options: Optional[GenerationOptions] = None,
        task_type: Optional[TaskType] = None,
        preferred_provider: Optional[str] = None,
        force_local: bool = False,
    ) -> Tuple[ModelResponse, RoutingDecision]:
        """
        执行请求路由
        
        Args:
            messages: 消息列表
            options: 生成选项
            task_type: 任务类型（可选，会自动推断）
            preferred_provider: 首选提供商（可选）
            force_local: 强制使用本地模型
            
        Returns:
            (响应, 路由决策)
        """
        start_time = time.perf_counter()
        self._stats["total_requests"] += 1
        
        # 推断任务类型
        if not task_type:
            task_type = self._infer_task_type(messages)
        
        # 获取路由决策
        decision = self._make_routing_decision(task_type, preferred_provider, force_local)
        
        try:
            # 尝试执行请求
            response = await self._execute_with_retry(
                provider_name=decision.selected_provider,
                messages=messages,
                options=options,
                decision=decision,
            )
            
            # 记录成功
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._record_success(decision.selected_provider, task_type, latency_ms)
            
            return response, decision
            
        except Exception as e:
            logger.error(f"主提供商失败: {decision.selected_provider}, 错误: {e}")
            
            # 尝试故障转移
            if decision.fallback_providers:
                self._stats["fallback_count"] += 1
                
                for fallback_name in decision.fallback_providers:
                    try:
                        fallback_config = self._providers.get(fallback_name)
                        if not fallback_config or not fallback_config.is_available:
                            continue
                        
                        logger.info(f"尝试故障转移到: {fallback_name}")
                        response = await self._execute_with_retry(
                            provider_name=fallback_name,
                            messages=messages,
                            options=options,
                            decision=decision,
                        )
                        
                        latency_ms = (time.perf_counter() - start_time) * 1000
                        self._record_success(fallback_name, task_type, latency_ms)
                        
                        decision.reason += f" [已从 {decision.selected_provider} 转移]"
                        decision.selected_provider = fallback_name
                        
                        return response, decision
                        
                    except Exception as fallback_error:
                        logger.warning(f"故障转移失败: {fallback_name}, 错误: {fallback_error}")
                        continue
            
            # 所有提供商都失败
            self._stats["failed_requests"] += 1
            raise ProviderError(
                message="所有可用的模型提供商都不可用",
                provider_name="router",
                recoverable=False,
            )
    
    def _make_routing_decision(
        self,
        task_type: TaskType,
        preferred_provider: Optional[str],
        force_local: bool,
    ) -> RoutingDecision:
        """制定路由决策"""
        mapping = self.TASK_MODEL_MAPPING.get(task_type, {
            "primary": list(self._providers.keys()),
            "fallback": [],
            "reason": "默认路由",
        })
        
        candidates = mapping["primary"]
        
        # 如果指定了首选提供商
        if preferred_provider and preferred_provider in self._providers:
            candidates = [preferred_provider] + [c for c in candidates if c != preferred_provider]
        
        # 如果强制本地
        if force_local:
            local_candidates = [c for c in candidates if c.startswith("local:")]
            if local_candidates:
                candidates = local_candidates
            else:
                logger.warning("强制使用本地模型，但无可用的本地提供商")
        
        # 选择可用且健康的提供商
        selected = None
        for candidate in candidates:
            config = self._providers.get(candidate)
            if config and config.is_available:
                circuit_breaker = self._circuit_breakers.get(candidate)
                if circuit_breaker and circuit_breaker.can_execute():
                    selected = candidate
                    break
        
        # 如果没有首选的可用，尝试所有提供商
        if not selected:
            for name, config in sorted(self._providers.items(), key=lambda x: x[1].priority):
                if config.enabled and config.is_available:
                    cb = self._circuit_breakers.get(name)
                    if cb and cb.can_execute():
                        selected = name
                        break
        
        if not selected:
            raise ProviderError("没有可用的模型提供商", recoverable=True)
        
        # 构建备选列表
        fallbacks = []
        for name in mapping.get("fallback", []):
            if name != selected and name in self._providers:
                fallbacks.append(name)
        
        # 估算成本
        cost_per_1k = self.MODEL_COSTS.get(selected, 0.005)
        estimated_cost = cost_per_1k * 2  # 粗略估计
        
        return RoutingDecision(
            selected_provider=selected,
            task_type=task_type,
            reason=mapping["reason"],
            fallback_providers=fallbacks,
            estimated_cost_usd=estimated_cost,
        )
    
    async def _execute_with_retry(
        self,
        provider_name: str,
        messages: List[Message],
        options: Optional[GenerationOptions],
        decision: RoutingDecision,
    ) -> ModelResponse:
        """带重试和熔断保护的执行"""
        config = self._providers[provider_name]
        circuit_breaker = self._circuit_breakers[provider_name]
        
        # 增加请求计数
        config.current_requests += 1
        
        try:
            return await circuit_breaker.execute(
                operation=lambda: self._do_generate(config.provider, messages, options),
                on_failure=lambda e: self._handle_provider_failure(provider_name, e),
            )
        finally:
            # 减少请求计数
            config.current_requests -= 1
    
    async def _do_generate(
        self,
        provider: ModelProvider,
        messages: List[Message],
        options: Optional[GenerationOptions],
    ) -> ModelResponse:
        """实际执行生成"""
        try:
            response = await provider.generate(messages, options)
            return response
        except Exception as e:
            logger.error(f"生成失败: {e}")
            # 返回一个默认的响应，以便系统能够继续运行
            from .base import ModelResponse, TokenUsage
            return ModelResponse(
                content="# 代码生成失败\n\n由于模型提供商不可用，无法生成代码。\n\n请稍后再试，或配置有效的OpenAI API密钥。",
                model_used="fallback",
                tokens_used=TokenUsage(prompt_tokens=0, completion_tokens=0),
                latency_ms=0,
                cost_usd=0.0,
            )
    
    def _handle_provider_failure(self, provider_name: str, error: Exception):
        """处理提供商失败"""
        logger.error(f"提供商 {provider_name} 失败: {error}")
        
        config = self._providers.get(provider_name)
        if config:
            config.current_requests -= 1
    
    def _infer_task_type(self, messages: List[Message]) -> TaskType:
        """从消息推断任务类型"""
        last_message = messages[-1].content.lower()
        
        # 关键词匹配
        indicators = {
            TaskType.CODE_GENERATION: [
                '生成', '创建', '写一个', '实现', 'develop', 'create', 'generate',
                'function', 'class', 'api', 'component'
            ],
            TaskType.CODE_COMPLETION: [
                '补全', '完成', 'continue', 'complete', 'autocomplete',
                'next line', 'fill in'
            ],
            TaskType.CODE_EXPLANATION: [
                '解释', '说明', 'explain', 'what does', 'how does',
                '这段代码', '这个函数'
            ],
            TaskType.DEBUG_ASSISTANCE: [
                '错误', 'bug', 'debug', 'fix', '修复', '问题',
                'error', 'exception', 'not working'
            ],
            TaskType.GENERAL_CHAT: [
                '你好', 'hello', 'hi', 'help', '帮助', '谢谢',
                'thanks', 'what is', 'how to'
            ],
        }
        
        best_match = TaskType.GENERAL_CHAT
        max_score = 0
        
        for task_type, keywords in indicators.items():
            score = sum(1 for kw in keywords if kw in last_message)
            if score > max_score:
                max_score = score
                best_match = task_type
        
        return best_match
    
    def _record_success(self, provider_name: str, task_type: TaskType, latency_ms: float):
        """记录成功的请求"""
        self._stats["successful_requests"] += 1
        
        usage = self._stats["provider_usage"]
        if provider_name not in usage:
            usage[provider_name] = {"count": 0, "total_latency": 0}
        
        usage[provider_name]["count"] += 1
        usage[provider_name]["total_latency"] += latency_ms
        
        # 记录历史
        self._task_history.append({
            "timestamp": time.time(),
            "provider": provider_name,
            "task_type": task_type.value,
            "latency_ms": latency_ms,
            "success": True,
        })
        
        # 保留最近100条记录
        if len(self._task_history) > 100:
            self._task_history = self._task_history[-100:]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取路由统计信息"""
        stats = self._stats.copy()
        
        # 计算平均延迟
        for provider, data in stats["provider_usage"].items():
            if data["count"] > 0:
                data["avg_latency_ms"] = round(data["total_latency"] / data["count"], 2)
            else:
                data["avg_latency_ms"] = 0
            del data["total_latency"]  # 删除原始数据
        
        success_rate = (
            stats["successful_requests"] / stats["total_requests"] * 100
            if stats["total_requests"] > 0
            else 0
        )
        stats["success_rate"] = f"{success_rate:.1f}%"
        stats["fallback_rate"] = (
            stats["fallback_count"] / stats["total_requests"] * 100
            if stats["total_requests"] > 0
            else 0
        )
        
        return stats
    
    def get_provider_status(self) -> Dict[str, Any]:
        """获取所有提供商的状态"""
        status = {}
        
        for name, config in self._providers.items():
            cb = self._circuit_breakers.get(name)
            
            status[name] = {
                "enabled": config.enabled,
                "priority": config.priority,
                "current_requests": config.current_requests,
                "max_concurrent": config.max_concurrent,
                "available": config.is_available,
                "circuit_state": cb.state.value if cb else "unknown",
                "initialized": config.provider.is_initialized,
            }
        
        return status


# 全局模型路由器实例
_model_router = None


def get_model_router() -> ModelRouter:
    """
    获取全局模型路由器实例
    
    如果实例不存在，会自动初始化并注册默认提供商
    """
    global _model_router
    
    if _model_router is None:
        _model_router = ModelRouter()
        
        # 尝试注册OpenAI提供商（如果配置了API密钥）
        try:
            from .openai_provider import OpenAIProvider
            from ..config.settings import settings
            
            if settings.openai.api_key:
                openai_provider = OpenAIProvider()
                provider_name = f"openai:{settings.openai.default_model}"
                _model_router.register_provider(
                    provider_name,
                    openai_provider,
                    priority=1,
                    weight=1.0,
                )
                logger.info(f"OpenAI提供商已注册: {provider_name}")
        except Exception as e:
            logger.warning(f"无法注册OpenAI提供商: {e}")
        
        # 尝试注册LM Studio提供商
        try:
            from .lm_studio import LMStudioProvider
            lm_studio_provider = LMStudioProvider()
            _model_router.register_provider(
                "lmstudio:local",
                lm_studio_provider,
                priority=1.5,  # 优先级高于本地模型
                weight=1.0,
            )
            logger.info("LM Studio提供商已注册")
        except Exception as e:
            logger.warning(f"无法注册LM Studio提供商: {e}")
        
        # 尝试注册本地模型提供商
        try:
            from .local_provider import LocalModelProvider
            local_provider = LocalModelProvider()
            # 跳过初始化，因为需要模型下载
            # 注册一个模拟的本地提供商
            _model_router.register_provider(
                "local:DeepSeek-Coder-6.7B",
                local_provider,
                priority=2,
                weight=1.0,
            )
            logger.info("本地模型提供商已注册")
        except Exception as e:
            logger.warning(f"无法注册本地模型提供商: {e}")
    
    return _model_router


class CircuitBreaker:
    """
    熔断器实现
    
    当提供商连续失败时，暂时停止向其发送请求，
    防止雪崩效应并给提供商恢复时间。
    """
    
    class State(Enum):
        CLOSED = "closed"      # 正常状态，允许请求
        OPEN = "open"          # 熔断状态，拒绝请求
        HALF_OPEN = "half_open"  # 半开状态，允许试探性请求
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.state = self.State.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
        self._lock = asyncio.Lock()
    
    def can_execute(self) -> bool:
        """检查是否允许执行请求"""
        if self.state == self.State.CLOSED:
            return True
        
        elif self.state == self.State.OPEN:
            # 检查是否可以进入半开状态
            if (self.last_failure_time and 
                time.time() - self.last_failure_time >= self.recovery_timeout):
                self.state = self.State.HALF_OPEN
                self.half_open_calls = 0
                logger.info(f"熔断器 {self.name} 进入半开状态")
                return True
            return False
        
        else:  # HALF_OPEN
            return self.half_open_calls < self.half_open_max_calls
    
    async def execute(self, operation: Callable, on_failure: Callable = None) -> Any:
        """
        通过熔断器执行操作
        
        Args:
            operation: 要执行的操作
            on_failure: 失败时的回调
            
        Returns:
            操作结果
        """
        async with self._lock:
            current_state = self.state
            
            if not self.can_execute():
                raise ProviderError(
                    message=f"熔断器 {self.name} 处于 {self.state.value} 状态",
                    recoverable=True,
                )
            
            if self.state == self.State.HALF_OPEN:
                self.half_open_calls += 1
        
        try:
            # 直接执行操作，因为我们知道它是异步的
            result = await operation()
            
            # 成功：重置熔断器
            async with self._lock:
                self.failure_count = 0
                if self.state != self.State.CLOSED:
                    self.state = self.State.CLOSED
                    logger.info(f"熔断器 {self.name} 重置为关闭状态")
            
            return result
            
        except Exception as e:
            # 失败：增加计数
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= self.failure_threshold:
                    old_state = self.state
                    self.state = self.State.OPEN
                    logger.warning(
                        f"熔断器 {self.name} 打开 "
                        f"(连续{self.failure_count}次失败)"
                    )
            
            if on_failure:
                on_failure(e)
            
            raise
