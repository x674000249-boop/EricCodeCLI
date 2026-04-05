"""
EricCode OpenAI 提供商实现

封装OpenAI API的完整交互逻辑，包括：
- 同步和异步请求
- 流式响应
- 速率限制处理
- 错误重试
- Token计数和成本追踪
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Union

import httpx

from .base import (
    GenerationOptions,
    Message,
    MessageRole,
    ModelProvider,
    ModelResponse,
    ProviderError,
    RateLimitError,
    StreamChunk,
    TokenUsage,
)

logger = logging.getLogger(__name__)

# OpenAI API定价表（每1K tokens，2024年价格）
PRICING = {
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "o1-mini": {"input": 0.003, "output": 0.012},
    "o3-mini": {"input": 0.0011, "output": 0.0044},  # 预估价格
}


class OpenAIProvider(ModelProvider):
    """
    OpenAI API提供商
    
    支持GPT-4o、GPT-4o-mini、o1-mini等模型，
    提供完整的API集成包括流式响应和错误处理。
    
    使用示例::
    
        provider = OpenAIProvider()
        await provider.initialize({
            "api_key": "sk-...",
            "model": "gpt-4o"
        })
        
        response = await provider.generate([
            Message(role=MessageRole.USER, content="Hello!")
        ])
        print(response.content)
    """
    
    BASE_URL = "https://api.openai.com/v1"
    LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
    CHAT_COMPLETIONS_ENDPOINT = "/chat/completions"
    
    def __init__(self):
        super().__init__()
        self._client: Optional[httpx.AsyncClient] = None
        self._model: str = "gpt-4o"
    
    @property
    def provider_name(self) -> str:
        return "openai"
    
    @property
    def supported_models(self) -> List[str]:
        return list(PRICING.keys())
    
    @property
    def max_context_length(self) -> int:
        context_lengths = {
            "gpt-4o": 128000,
            "gpt-4o-mini": 128000,
            "gpt-4-turbo": 128000,
            "o1-mini": 128000,
            "o3-mini": 200000,
        }
        return context_lengths.get(self._model, 4096)
    
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """
        初始化OpenAI客户端
        
        Args:
            config: 配置字典，必须包含 api_key
                - api_key (str): API密钥
                - base_url (str, optional): 自定义端点
                - organization (str, optional): 组织ID
                - model (str): 默认模型
                - timeout (float): 请求超时（秒）
                - max_retries (int): 最大重试次数
        """
        required_fields = ["api_key"]
        for field in required_fields:
            if field not in config:
                raise ValueError(f"缺少必需配置项: {field}")
        
        self._config = config.copy()
        self._model = config.get("model", "gpt-4o")
        
        timeout = config.get("timeout", 30.0)
        
        # 创建HTTP客户端
        self._client = httpx.AsyncClient(
            base_url=config.get("base_url", self.BASE_URL),
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
                **({"OpenAI-Organization": config["organization"]} if config.get("organization") else {}),
            },
            timeout=httpx.Timeout(timeout, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
            follow_redirects=True,
        )
        
        # 执行健康检查
        if await self.health_check():
            self._initialized = True
            logger.info(f"✓ OpenAI provider initialized with model: {self._model}")
            return True
        else:
            logger.error("✗ OpenAI provider health check failed")
            return False
    
    async def generate(
        self,
        messages: List[Message],
        options: Optional[GenerationOptions] = None
    ) -> ModelResponse:
        """
        发送聊天完成请求
        
        Args:
            messages: 消息列表
            options: 生成选项
            
        Returns:
            ModelResponse对象
            
        Raises:
            ProviderError: API调用失败时抛出
        """
        if not self._initialized or not self._client:
            raise ProviderError("Provider not initialized", provider_name=self.provider_name)
        
        opts = options or GenerationOptions()
        max_retries = self._config.get("max_retries", 3)
        
        for attempt in range(max_retries + 1):
            try:
                start_time = time.perf_counter()
                
                # 构建请求
                payload = self._build_request_payload(messages, opts)
                
                logger.debug(f"Sending request to OpenAI (attempt {attempt + 1}/{max_retries + 1})")
                
                response = await self._client.post(
                    self.CHAT_COMPLETIONS_ENDPOINT,
                    json=payload,
                )
                
                # 处理响应
                response.raise_for_status()
                data = response.json()
                
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                
                # 解析响应
                result = self._parse_response(data, latency_ms)
                
                logger.info(
                    f"Request completed in {latency_ms}ms, "
                    f"tokens: {result.tokens_used.total_tokens}"
                )
                
                return result
                
            except httpx.HTTPStatusError as e:
                error_data = self._extract_error(e.response)
                
                if e.response.status_code == 429:
                    # 速率限制错误
                    retry_after = float(
                        error_data.get("retry_after", 60)
                        if isinstance(error_data, dict)
                        else 60
                    )
                    
                    if attempt < max_retries:
                        wait_time = min(retry_after * (2 ** attempt), 120)
                        wait_time *= (1 + random.uniform(-0.1, 0.1))  # 添加抖动
                        
                        logger.warning(
                            f"Rate limited, retrying in {wait_time:.1f}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    
                    raise RateLimitError(
                        message=f"速率限制: {error_data}",
                        retry_after=retry_after,
                        provider_name=self.provider_name,
                        original_error=e,
                    )
                
                elif e.response.status_code == 401:
                    from .base import AuthenticationError
                    raise AuthenticationError(
                        message="API密钥无效或已过期",
                        provider_name=self.provider_name,
                        original_error=e,
                    )
                
                elif e.response.status_code >= 500:
                    # 服务器错误，可重试
                    if attempt < max_retries:
                        wait_time = min(2 ** attempt, 30)
                        logger.warning(
                            f"Server error {e.response.status_code}, "
                            f"retrying in {wait_time}s"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    
                    from .base import ProviderUnavailableError
                    raise ProviderUnavailableError(
                        message=f"服务器错误 ({e.response.status_code}): {error_data}",
                        provider_name=self.provider_name,
                        original_error=e,
                    )
                
                else:
                    # 其他HTTP错误
                    from .base import InvalidRequestError
                    raise InvalidRequestError(
                        message=f"请求失败 ({e.response.status_code}): {error_data}",
                        provider_name=self.provider_name,
                        original_error=e,
                    )
            
            except httpx.ConnectError as e:
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    logger.warning(f"Connection error, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                
                from .base import ProviderUnavailableError
                raise ProviderUnavailableError(
                    message="无法连接到OpenAI服务",
                    provider_name=self.provider_name,
                    original_error=e,
                )
            
            except httpx.ReadTimeout as e:
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    logger.warning(f"Read timeout, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                
                raise ProviderError(
                    message="请求超时",
                    error_code="TIMEOUT",
                    recoverable=True,
                    provider_name=self.provider_name,
                    original_error=e,
                )
        
        # 所有重试都失败
        raise ProviderError(
            message=f"在{max_retries + 1}次尝试后仍失败",
            error_code="MAX_RETRIES_EXCEEDED",
            provider_name=self.provider_name,
        )
    
    async def generate_stream(
        self,
        messages: List[Message],
        options: Optional[GenerationOptions] = None
    ) -> AsyncIterator[StreamChunk]:
        """
        流式生成文本
        
        Yields:
            StreamChunk对象
        """
        if not self._initialized or not self._client:
            raise ProviderError("Provider not initialized", provider_name=self.provider_name)
        
        opts = options or GenerationOptions()
        payload = self._build_request_payload(messages, opts)
        payload["stream"] = True
        
        cumulative_tokens = 0
        
        try:
            async with self._client.stream(
                "POST",
                self.CHAT_COMPLETIONS_ENDPOINT,
                json=payload,
                timeout=httpx.Timeout(60.0, connect=10.0),
            ) as response:
                response.raise_for_status()
                
                buffer = ""
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    
                    data_str = line[6:]  # 移除 "data: " 前缀
                    
                    if data_str.strip() == "[DONE]":
                        yield StreamChunk(content="", is_final=True, cumulative_tokens=cumulative_tokens)
                        break
                    
                    try:
                        import json
                        chunk_data = json.loads(data_str)
                        
                        delta = chunk_data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        
                        if content:
                            cumulative_tokens += 1
                            yield StreamChunk(
                                content=content,
                                is_final=False,
                                delta_tokens=1,
                                cumulative_tokens=cumulative_tokens,
                            )
                            
                    except (json.JSONDecodeError, KeyError, IndexError) as e:
                        logger.warning(f"Failed to parse stream chunk: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Stream generation error: {e}")
            raise ProviderError(
                message=f"流式生成错误: {str(e)}",
                provider_name=self.provider_name,
                original_error=e,
            )
    
    async def get_token_count(self, text: str) -> int:
        """
        粗略估算token数量
        
        对于精确计数，需要使用tiktoken库。
        这里使用简单的启发式方法：
        - 英文：约4字符/token
        - 中文：约1.5字符/token
        - 混合：动态调整
        """
        if not text:
            return 0
        
        # 检测中文字符比例
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        chinese_ratio = chinese_chars / len(text)
        
        if chinese_ratio > 0.5:
            # 主要中文
            return int(len(text) / 1.5)
        elif chinese_ratio > 0:
            # 中英混合
            return int(len(text) / 2.5)
        else:
            # 纯英文
            return int(len(text / 4))
    
    async def health_check(self) -> bool:
        """检查API连接是否正常"""
        if not self._client:
            return False
        
        try:
            response = await self._client.get("/models", timeout=5.0)
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False
    
    async def cleanup(self) -> None:
        """清理资源"""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False
        logger.info("OpenAI provider cleaned up")
    
    def _build_request_payload(
        self,
        messages: List[Message],
        options: GenerationOptions
    ) -> Dict[str, Any]:
        """构建API请求体"""
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": [msg.to_dict() for msg in messages],
            **options.to_dict(),
        }
        
        # 添加用户标识（用于滥用监控）
        payload["user"] = "ericcode-user"
        
        return payload
    
    def _parse_response(self, data: Dict[str, Any], latency_ms: int) -> ModelResponse:
        """解析API响应"""
        choice = data["choices"][0]
        usage = data.get("usage", {})
        
        token_usage = TokenUsage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )
        
        cost = self._calculate_cost(token_usage)
        
        return ModelResponse(
            content=choice["message"]["content"],
            model_used=data.get("model", self._model),
            tokens_used=token_usage,
            finish_reason=choice.get("finish_reason", "stop"),
            latency_ms=latency_ms,
            cost_usd=cost,
            raw_response=data,
        )
    
    def _calculate_cost(self, usage: TokenUsage) -> float:
        """计算成本"""
        pricing = PRICING.get(self._model, {"input": 0.0, "output": 0.0})
        
        input_cost = (usage.prompt_tokens / 1000) * pricing["input"]
        output_cost = (usage.completion_tokens / 1000) * pricing["output"]
        
        return round(input_cost + output_cost, 6)
    
    @staticmethod
    def _extract_error(response: httpx.Response) -> Union[str, Dict[str, Any]]:
        """从错误响应中提取错误信息"""
        try:
            error_data = response.json()
            if "error" in error_data:
                error = error_data["error"]
                if isinstance(error, dict):
                    return error.get("message", str(error))
                return str(error)
            return error_data
        except Exception:
            return response.text
