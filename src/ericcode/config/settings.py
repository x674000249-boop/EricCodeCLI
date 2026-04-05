"""
EricCode 配置管理模块

提供类型安全的配置管理，支持：
- 多层级配置（默认值 < 环境变量 < 配置文件 < 命令行参数）
- TOML/YAML格式的配置文件
- 敏感信息的安全存储
- 配置验证和迁移
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(str, Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Language(str, Enum):
    """支持的编程语言"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    CPP = "c++"
    CSHARP = "c#"
    PHP = "php"
    RUBY = "ruby"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    SHELL = "shell"
    SQL = "sql"
    HTML = "html"
    CSS = "css"
    YAML = "yaml"
    JSON = "json"


class ModelProvider(str, Enum):
    """模型提供商"""
    OPENAI = "openai"
    LOCAL = "local"
    AUTO = "auto"  # 自动选择





class LocalModel(str, Enum):
    """本地支持的模型"""
    CODE_LLAMA_7B = "CodeLlama-7B"
    CODE_LLAMA_13B = "CodeLlama-13B"
    DEEPSEEK_CODER_6_7B = "DeepSeek-Coder-6.7B"
    STARCODER2_15B = "StarCoder2-15B"
    QWEN2_5_CODER_7B = "Qwen2.5-Coder-7B"


class CacheConfig(BaseSettings):
    """缓存配置"""
    model_config = SettingsConfigDict(env_prefix="ERICCODE_CACHE_")
    
    enabled: bool = Field(default=True, description="是否启用缓存")
    ttl_seconds: int = Field(default=3600, ge=60, le=86400, description="缓存过期时间（秒）")
    max_size: int = Field(default=1000, ge=100, le=10000, description="最大缓存条目数")
    
    # L1 内存缓存
    l1_enabled: bool = True
    l1_max_size: int = 200
    
    # L2 文件缓存
    l2_enabled: bool = True
    l2_cache_dir: Optional[Path] = None  # 默认使用 ~/.cache/ericcode
    
    # L3 Redis缓存（可选）
    l3_enabled: bool = False
    l3_redis_url: Optional[str] = None


class OpenAIConfig(BaseSettings):
    """OpenAI API配置"""
    model_config = SettingsConfigDict(env_prefix="ERICCODE_OPENAI_")
    
    api_key: Optional[str] = Field(default=None, description="API密钥")
    base_url: Optional[str] = Field(default=None, description="自定义API端点")
    organization: Optional[str] = Field(default=None, description="组织ID")
    
    default_model: str = Field(default="gpt-4o", description="默认模型")
    max_tokens: int = Field(default=4096, ge=256, le=128000, description="最大token数")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    top_p: float = Field(default=1.0, ge=0.0, le=1.0, description="Top-p采样")
    
    # 速率限制
    rpm_limit: int = Field(default=500, ge=10, le=10000, description="每分钟请求数限制")
    tpm_limit: int = Field(default=200000, ge=1000, le=5000000, description="每分钟token数限制")
    
    # 超时和重试
    timeout: float = Field(default=30.0, ge=5.0, le=120.0, description="请求超时（秒）")
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")
    
    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: Optional[str]) -> Optional[str]:
        # 允许LM Studio的API密钥格式
        if v and not (v.startswith("sk-") or v.startswith("sk-lm-")):
            raise ValueError("API密钥应以 'sk-' 或 'sk-lm-' 开头")
        return v


class LocalModelConfig(BaseSettings):
    """本地模型配置"""
    model_config = SettingsConfigDict(env_prefix="ERICCODE_LOCAL_")
    
    enabled: bool = Field(default=True, description="是否启用本地模型")
    default_model: LocalModel = Field(
        default=LocalModel.DEEPSEEK_CODER_6_7B,
        description="默认本地模型"
    )
    models_dir: Path = Field(
        default=Path.home() / ".local" / "share" / "ericcode" / "models",
        description="模型存储目录"
    )
    
    # 量化设置
    quantization: str = Field(
        default="4bit",
        pattern=r"^(none|4bit|8bit)$",
        description="量化级别"
    )
    
    # 设备设置
    device: str = Field(
        default="auto",
        pattern=r"^(auto|cuda|cpu|mps)$",
        description="计算设备"
    )
    
    # 性能设置
    max_memory_gb: Optional[float] = Field(
        default=None,
        ge=2.0,
        le=128.0,
        description="最大显存/内存使用（GB），None表示自动"
    )
    
    # 模型卸载策略
    idle_unload_minutes: int = Field(
        default=30,
        ge=5,
        le=120,
        description="闲置多少分钟后卸载模型"
    )


class UIConfig(BaseSettings):
    """用户界面配置"""
    model_config = SettingsConfigDict(env_prefix="ERICCODE_UI_")
    
    theme: str = Field(default="dark", description="主题 (dark/light)")
    color_output: bool = Field(default=True, description="彩色输出")
    emoji_support: bool = Field(default=True, description="Emoji支持")
    
    # 补全显示
    completion_max_suggestions: int = Field(default=5, ge=1, le=10)
    completion_show_confidence: bool = True
    
    # 输出格式
    output_language: str = Field(default="zh", description="默认输出语言 (zh/en)")
    code_highlighting: bool = True
    
    # 交互式模式
    repl_history_size: int = Field(default=1000, ge=100, le=10000)


class LoggingConfig(BaseSettings):
    """日志配置"""
    model_config = SettingsConfigDict(env_prefix="ERICCODE_LOG_")
    
    level: LogLevel = Field(default=LogLevel.INFO, description="日志级别")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="日志格式"
    )
    
    file_logging: bool = False
    log_file: Path = Field(default=Path(".ericcode/logs/ericcode.log"))
    max_file_size_mb: int = Field(default=10, ge=1, le=100)
    backup_count: int = Field(default=5, ge=1, le=20)
    
    # 结构化日志（推荐用于生产）
    structured: bool = True
    include_timestamp: bool = True
    include_caller: bool = True


class SecurityConfig(BaseSettings):
    """安全配置"""
    model_config = SettingsConfigDict(env_prefix="ERICCODE_SECURITY_")
    
    # API密钥加密
    encrypt_credentials: bool = Field(default=True, description="是否加密存储凭证")
    
    # 敏感数据检测
    detect_sensitive_data: bool = Field(default=True, description="发送前检测敏感数据")
    auto_mask_sensitive: bool = Field(default=True, description="自动脱敏敏感数据")
    
    # 数据收集（遥测）
    enable_telemetry: bool = Field(default=False, description="启用匿名遥测数据收集")
    telemetry_id: Optional[str] = None  # 自动生成或从配置读取
    
    # 对话历史
    save_chat_history: bool = Field(default=True, description="保存对话历史")
    chat_retention_days: int = Field(default=7, ge=1, le=90, description="对话保留天数")


class Settings(BaseSettings):
    """
    EricCode 主配置类
    
    支持多层级配置覆盖：
    1. 默认值（代码中的默认值）
    2. 环境变量（ERICCODE_* 前缀）
    3. 配置文件（~/.config/ericcode/config.toml 或 --config 指定）
    4. 命令行参数（运行时传入）
    """
    model_config = SettingsConfigDict(
        env_prefix="ERICCODE_",
        env_nested_delimiter="__",
        extra="ignore",
    )
    
    # 基础配置
    config_dir: Path = Field(
        default_factory=lambda: _get_default_config_dir(),
        description="配置目录"
    )
    data_dir: Path = Field(
        default_factory=lambda: _get_default_data_dir(),
        description="数据目录"
    )
    
    # 子配置
    cache: CacheConfig = Field(default_factory=CacheConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    local_model: LocalModelConfig = Field(default_factory=LocalModelConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    
    # 高级设置
    debug: bool = Field(default=False, description="调试模式")
    verbose: bool = Field(default=False, description="详细输出")
    
    def get_effective_model_provider(self) -> ModelProvider:
        """获取实际使用的模型提供商"""
        # TODO: 实现智能选择逻辑
        return ModelProvider.AUTO
    
    def ensure_directories(self) -> None:
        """确保所有必要的目录存在"""
        for directory in [self.config_dir, self.data_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        if self.cache.l2_cache_dir:
            self.cache.l2_cache_dir.mkdir(parents=True, exist_ok=True)
        
        if self.local_model.models_dir:
            self.local_model.models_dir.mkdir(parents=True, exist_ok=True)
    
    def to_toml(self) -> str:
        """导出为TOML格式"""
        try:
            import tomli_w
            return tomli_w.dumps(self.model_dump(exclude_none=True))
        except ImportError:
            # 如果没有tomli-w，返回简化的字典表示
            return str(self.model_dump(exclude_none=True))


def _get_default_config_dir() -> Path:
    """获取默认配置目录路径（遵循XDG规范）"""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ericcode"
    elif sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "ericcode"
    else:
        xdg_config = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
        return Path(xdg_config) / "ericcode"


def _get_default_data_dir() -> Path:
    """获取默认数据目录路径"""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ericcode"
    elif sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ericcode"
    else:
        xdg_data = os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
        return Path(xdg_data) / "ericcode"


import sys

settings = Settings()
