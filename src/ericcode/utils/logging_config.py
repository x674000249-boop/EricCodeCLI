"""
EricCode 日志系统

提供结构化日志记录：
- 多级别日志（DEBUG/INFO/WARNING/ERROR/CRITICAL）
- 格式化输出
- 文件和控制台输出
- 性能日志
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    structured: bool = True,
    include_timestamp: bool = True,
) -> logging.Logger:
    """
    配置日志系统
    
    Args:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        log_file: 日志文件路径（可选）
        structured: 是否使用结构化格式
        include_timestamp: 是否包含时间戳
        
    Returns:
        配置好的logger实例
    """
    # 获取根logger
    logger = logging.getLogger("ericcode")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # 清除现有处理器
    logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.DEBUG)
    
    if structured:
        console_format = StructuredFormatter(include_timestamp=include_timestamp)
    else:
        console_format = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # 文件处理器（如果指定）
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8',
        )
        file_handler.setLevel(logging.DEBUG)
        
        file_format = StructuredFormatter(include_timestamp=True, colorize=False)
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    
    return logger


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # 青色
        'INFO': '\033[32m',      # 绿色
        'WARNING': '\033[33m',   # 黄色
        'ERROR': '\033[31m',     # 红色
        'CRITICAL': '\033[35m',  # 紫色
    }
    RESET = '\033[0m'
    
    def __init__(
        self,
        include_timestamp: bool = True,
        colorize: bool = True,
    ):
        self.include_timestamp = include_timestamp
        self.colorize = colorize and sys.stdout.isatty()
        super().__init__()
    
    def format(self, record: logging.LogRecord) -> str:
        parts = []
        
        # 时间戳
        if self.include_timestamp:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created))
            parts.append(timestamp)
        
        # 级别
        level = record.levelname
        
        if self.colorize:
            color = self.COLORS.get(level, '')
            reset = self.RESET
            parts.append(f"{color}{level:<8}{reset}")
        else:
            parts.append(f"{level:<8}")
        
        # Logger名称
        if record.name != "root":
            parts.append(f"[{record.name}]")
        
        # 消息
        parts.append(record.getMessage())
        
        # 异常信息
        if record.exc_info:
            parts.append(self.formatException(record.exc_info))
        
        # 额外字段
        extra_data = {}
        for key, value in record.__dict__.items():
            if key not in (
                'name', 'msg', 'args', 'created', 'filename',
                'funcName', 'levelname', 'levelno', 'lineno',
                'module', 'pathname', 'process', 'processName',
                'relativeCreated', 'stack_info', 'exc_info', 'exc_text',
                'thread', 'threadName', 'taskName', 'message',
            ):
                extra_data[key] = value
        
        if extra_data:
            parts.append(f" | {extra_data}")
        
        return " ".join(parts)


class PerformanceLogger:
    """性能日志记录器"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def log_operation(
        self,
        operation_name: str,
        duration_ms: float,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """记录操作性能"""
        status = "✓" if duration_ms < 1000 else "⚠" if duration_ms < 5000 else "✗"
        
        self.logger.info(
            f"{status} {operation_name}: {duration_ms:.2f}ms",
            extra={
                "operation": operation_name,
                "duration_ms": duration_ms,
                **(metadata or {}),
            }
        )
    
    async def track_async(self, operation_name: str):
        """
        异步上下文管理器，自动记录执行时间
        
        使用::
            
            perf_logger = PerformanceLogger(logger)
            async with perf_logger.track_async("API调用") as result:
                response = await api.call()
                result.value = response
        """
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def _tracker():
            start_time = time.perf_counter()
            result_holder = [None]
            
            try:
                yield result_holder
            finally:
                duration_ms = (time.perf_counter() - start_time) * 1000
                self.log_operation(operation_name, duration_ms)
        
        return await _tracker()


# 初始化默认日志器
default_logger = setup_logging()
perf_logger = PerformanceLogger(default_logger)
