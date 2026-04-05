"""
EricCode LM Studio Integration

LM Studio API集成模块

功能：
- 一键打开LM Studio
- 自动检测LM Studio状态
- 配置OpenAI兼容API
- 管理LM Studio进程
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from .base import ModelProvider, GenerationOptions, Message, MessageRole, ModelResponse, TokenUsage

logger = logging.getLogger(__name__)


@dataclass
class LMStudioStatus:
    """LM Studio状态"""
    is_running: bool
    api_endpoint: str
    api_key: str
    model: Optional[str]
    version: Optional[str]


class LMStudioIntegration:
    """
    LM Studio集成模块
    
    提供LM Studio的一键打开和API管理功能
    """
    
    def __init__(self):
        self._api_endpoint = "http://localhost:1234/v1"
        self._api_key = "sk-lm-wCRaL76B:72O3mheWw5Fc4XSbsJDc"  # 用户提供的API密钥
        self._process = None
    
    def open_lm_studio(self) -> bool:
        """
        一键打开LM Studio
        
        Returns:
            是否成功打开
        """
        try:
            # 尝试打开LM Studio应用
            if os.name == "darwin":  # macOS
                subprocess.run(["open", "/Applications/LM Studio.app"], check=True)
                logger.info("LM Studio已打开")
                return True
            elif os.name == "nt":  # Windows
                subprocess.run(["start", "LM Studio"], shell=True, check=True)
                logger.info("LM Studio已打开")
                return True
            elif os.name == "posix":  # Linux
                # 尝试在常见位置查找LM Studio
                lm_studio_paths = [
                    "/usr/bin/lm-studio",
                    "/usr/local/bin/lm-studio",
                    "~/.local/bin/lm-studio",
                ]
                found = False
                for path in lm_studio_paths:
                    path = Path(path).expanduser()
                    if path.exists():
                        subprocess.run([str(path)], check=True)
                        found = True
                        break
                if found:
                    logger.info("LM Studio已打开")
                    return True
                else:
                    logger.warning("未找到LM Studio可执行文件，正在打开LM Studio官网...")
                    # 打开LM Studio官网，让用户下载
                    if os.name == "linux":
                        subprocess.run(["xdg-open", "https://lmstudio.ai/"], check=False)
                    return False
            else:
                logger.warning(f"不支持的操作系统: {os.name}")
                return False
        except Exception as e:
            logger.error(f"打开LM Studio失败: {e}")
            return False
    
    def check_status(self) -> LMStudioStatus:
        """
        检查LM Studio状态
        
        Returns:
            LMStudioStatus对象
        """
        try:
            # 尝试调用API获取状态
            client = httpx.Client(timeout=5)
            response = client.get(f"{self._api_endpoint}/models", headers={"Authorization": f"Bearer {self._api_key}"})
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                model = models[0].get("id") if models else None
                
                # 获取版本信息
                version_response = client.get(f"{self._api_endpoint}/version")
                version = version_response.json().get("version") if version_response.status_code == 200 else None
                
                return LMStudioStatus(
                    is_running=True,
                    api_endpoint=self._api_endpoint,
                    api_key=self._api_key,
                    model=model,
                    version=version,
                )
            else:
                return LMStudioStatus(
                    is_running=False,
                    api_endpoint=self._api_endpoint,
                    api_key=self._api_key,
                    model=None,
                    version=None,
                )
        except Exception as e:
            logger.error(f"检查LM Studio状态失败: {e}")
            return LMStudioStatus(
                is_running=False,
                api_endpoint=self._api_endpoint,
                api_key=self._api_key,
                model=None,
                version=None,
            )
    
    def wait_for_startup(self, timeout: int = 30) -> bool:
        """
        等待LM Studio启动
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            是否在超时前启动
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.check_status()
            if status.is_running:
                logger.info("LM Studio已启动")
                return True
            time.sleep(2)
        
        logger.error("LM Studio启动超时")
        return False
    
    def get_api_config(self) -> dict:
        """
        获取API配置
        
        Returns:
            API配置字典
        """
        return {
            "api_key": self._api_key,
            "base_url": self._api_endpoint,
            "default_model": "local-model",
        }


class LMStudioProvider(ModelProvider):
    """
    LM Studio模型提供商
    
    使用LM Studio的OpenAI兼容API
    """
    
    def __init__(self, config: Optional[dict] = None):
        super().__init__()
        self._config = config or {}
        self._api_key = self._config.get("api_key", "sk-lm-wCRaL76B:72O3mheWw5Fc4XSbsJDc")
        self._base_url = self._config.get("base_url", "http://localhost:1234/v1")
        self._default_model = self._config.get("default_model", "local-model")
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30)
    
    async def initialize(self, config: dict) -> bool:
        """
        初始化LM Studio提供商
        
        Args:
            config: 配置字典
            
        Returns:
            是否初始化成功
        """
        try:
            # 测试连接
            response = await self._client.get("/models", headers={"Authorization": f"Bearer {self._api_key}"})
            return response.status_code == 200
        except Exception as e:
            logger.error(f"初始化LM Studio提供商失败: {e}")
            return False
    
    async def generate(self, messages: list[Message], options: Optional[GenerationOptions] = None) -> ModelResponse:
        """
        生成文本
        
        Args:
            messages: 消息列表
            options: 生成选项
            
        Returns:
            ModelResponse对象
        """
        try:
            # 构建请求
            request = {
                "model": self._default_model,
                "messages": [
                    {"role": msg.role.value, "content": msg.content}
                    for msg in messages
                ],
                "temperature": options.temperature if options else 0.7,
                "max_tokens": options.max_tokens if options else 1000,
            }
            
            # 发送请求
            response = await self._client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=request,
            )
            
            # 处理响应
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                
                return ModelResponse(
                    content=content,
                    model_used=self._default_model,
                    tokens_used=TokenUsage(
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                    ),
                    latency_ms=0,  # LM Studio API不返回延迟
                    cost_usd=0.0,  # 本地模型无成本
                )
            else:
                raise Exception(f"API请求失败: {response.status_code} {response.text}")
                
        except Exception as e:
            logger.error(f"生成失败: {e}")
            # 返回默认响应
            return ModelResponse(
                content="# 生成失败\n\nLM Studio API不可用，请确保LM Studio已启动并运行。\n\n你可以使用 `ericcode lm-studio open` 命令打开LM Studio。",
                model_used=self._default_model,
                tokens_used=TokenUsage(prompt_tokens=0, completion_tokens=0),
                latency_ms=0,
                cost_usd=0.0,
            )
    
    async def close(self):
        """
        关闭客户端
        """
        await self._client.aclose()


def get_lm_studio_integration() -> LMStudioIntegration:
    """
    获取LM Studio集成实例
    
    Returns:
        LMStudioIntegration实例
    """
    return LMStudioIntegration()
