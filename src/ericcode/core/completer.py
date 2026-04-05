"""
EricCode 代码补全引擎

提供实时的智能代码补全功能：
- 基于上下文的语义补全
- 多种补全类型（语法、API、模式）
- 高性能响应（<500ms P99）
- 本地缓存优化
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CompletionSuggestion:
    """
    补全建议
    
    Attributes:
        text: 建议的文本内容
        display_text: 显示文本（可能包含格式化）
        confidence: 置信度 (0.0-1.0)
        suggestion_type: 建议类型
        documentation: 相关文档（可选）
    """
    text: str
    display_text: str = ""
    confidence: float = 0.0
    suggestion_type: str = "auto"  # syntax/semantic/api/pattern
    documentation: str = ""
    
    def __post_init__(self):
        if not self.display_text:
            self.display_text = self.text


@dataclass
class CompletionResult:
    """
    补全结果
    
    Attributes:
        suggestions: 排序后的建议列表
        cursor_position: 光标位置（行，列）
        prefix: 当前输入的前缀
        latency_ms: 响应时间
    """
    suggestions: List[CompletionSuggestion]
    cursor_line: int = 1
    cursor_column: int = 1
    prefix: str = ""
    latency_ms: float = 0.0
    
    @property
    def best_suggestion(self) -> Optional[CompletionSuggestion]:
        """返回置信度最高的建议"""
        if not self.suggestions:
            return None
        return max(self.suggestions, key=lambda s: s.confidence)
    
    @property
    def has_high_confidence(self) -> bool:
        """是否有高置信度的建议（>80%）"""
        return any(s.confidence > 0.8 for s in self.suggestions)


class CodeCompleter:
    """
    代码补全器
    
    提供基于AI的智能代码补全功能。
    
    使用示例::
        
        completer = CodeCompleter()
        result = completer.get_suggestions("main.py", line=10, column=15)
        for sug in result.suggestions:
            print(f"{sug.text} ({sug.confidence:.0%})")
    """
    
    def __init__(self, watch_mode: bool = False):
        """
        初始化补全器
        
        Args:
            watch_mode: 是否启用持续监听模式
        """
        self._watch_mode = watch_mode
        self._cache = {}  # 简单的内存缓存
        self._file_watcher = None
        
        # TODO: 初始化本地模型或连接到服务
    
    def get_suggestions(
        self,
        file_path: str,
        line: Optional[int] = None,
        column: Optional[int] = None,
        prefix: Optional[str] = None
    ) -> CompletionResult:
        """
        获取补全建议
        
        Args:
            file_path: 文件路径
            line: 光标所在行号（从1开始）
            column: 光标所在列号（从1开始）
            prefix: 当前行已输入的内容
            
        Returns:
            CompletionResult对象
        """
        import asyncio
        
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self._get_suggestions_async(file_path, line, column, prefix)
                )
                return future.result()
        else:
            return asyncio.run(self._get_suggestions_async(file_path, line, column, prefix))
    
    async def _get_suggestions_async(
        self,
        file_path: str,
        line: Optional[int],
        column: Optional[int],
        prefix: Optional[str]
    ) -> CompletionResult:
        """异步获取补全建议"""
        start_time = time.perf_counter()
        
        try:
            path = Path(file_path)
            
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # 读取文件内容
            content = path.read_text(encoding="utf-8")
            lines = content.split("\n")
            
            # 确定光标位置
            actual_line = line or len(lines)
            actual_column = column or (len(lines[actual_line - 1]) + 1 if actual_line <= len(lines) else 1)
            
            # 获取当前行的前缀
            if not prefix and actual_line <= len(lines):
                prefix = lines[actual_line - 1][:actual_column - 1]
            
            # 检查缓存
            cache_key = f"{path}:{actual_line}:{prefix}"
            cached = self._cache.get(cache_key)
            if cached and (time.time() - cached["timestamp"] < 300):  # 5分钟缓存
                logger.debug(f"Cache hit for completion at line {actual_line}")
                return cached["result"]
            
            # 分析上下文并生成建议
            suggestions = await self._generate_suggestions(content, actual_line, actual_column, prefix)
            
            result = CompletionResult(
                suggestions=suggestions[:5],  # 返回最多5个建议
                cursor_line=actual_line,
                cursor_column=actual_column,
                prefix=prefix or "",
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )
            
            # 更新缓存
            self._cache[cache_key] = {
                "result": result,
                "timestamp": time.time(),
            }
            
            # 清理过期缓存（保留最近100条）
            if len(self._cache) > 100:
                sorted_cache = sorted(self._cache.items(), key=lambda x: x[1]["timestamp"])
                for key, _ in sorted_cache[:len(self._cache) - 100]:
                    del self._cache[key]
            
            return result
            
        except Exception as e:
            logger.error(f"Completion error: {e}")
            return CompletionResult(
                suggestions=[],
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )
    
    async def _generate_suggestions(
        self,
        content: str,
        line: int,
        column: int,
        prefix: str
    ) -> List[CompletionSuggestion]:
        """生成补全建议"""
        suggestions = []
        
        # 获取上下文（前后几行）
        lines = content.split("\n")
        context_before = "\n".join(lines[max(0, line-5):line])
        context_after = "\n".join(lines[line:min(len(lines), line+3)])
        
        # TODO: 集成实际的模型调用
        # 这里先返回基于规则的示例建议
        
        # 示例：简单的关键字补全
        keyword_suggestions = self._get_keyword_suggestions(prefix)
        suggestions.extend(keyword_suggestions)
        
        # 示例：模式补全
        pattern_suggestions = self._get_pattern_suggestions(context_before, prefix)
        suggestions.extend(pattern_suggestions)
        
        # 按置信度排序
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        
        return suggestions
    
    def _get_keyword_suggestions(self, prefix: str) -> List[CompletionSuggestion]:
        """基于关键字的简单补全"""
        common_keywords = {
            "def": ("def function_name(params):\n    pass", "函数定义", 0.95),
            "class": ("class ClassName:\n    pass", "类定义", 0.95),
            "if": ("if condition:\n    pass", "条件语句", 0.90),
            "for": ("for item in iterable:\n    pass", "循环语句", 0.90),
            "while": ("while condition:\n    pass", "While循环", 0.88),
            "try": ("try:\n    pass\nexcept Exception as e:\n    raise", "异常处理", 0.85),
            "with": ("with open('file', 'r') as f:\n    pass", "上下文管理器", 0.85),
            "import": ("import module_name", "导入语句", 0.92),
            "from": ("from module import name", "From导入", 0.90),
            "return": ("return value", "返回语句", 0.88),
            "async": ("async def async_function():\n    pass", "异步函数", 0.82),
        }
        
        suggestions = []
        prefix_lower = prefix.lower().strip()
        
        for keyword, (text, doc, conf) in common_keywords.items():
            if keyword.startswith(prefix_lower) or prefix_lower in keyword:
                suggestions.append(CompletionSuggestion(
                    text=text,
                    display_text=f"{keyword} → {text.split(chr(10))[0]}",
                    confidence=conf,
                    suggestion_type="syntax",
                    documentation=doc,
                ))
        
        return suggestions
    
    def _get_pattern_suggestions(
        self,
        context_before: str,
        prefix: str
    ) -> List[CompletionSuggestion]:
        """基于模式的补全"""
        suggestions = []
        
        # 检测常见模式
        patterns = [
            # 函数文档字符串
            ('def \\w+\\([^)]*\\):\\s*$', 
             '"""\n    Brief description.\n\n    Args:\n        param: description\n\n    Returns:\n        description\n    """',
             "函数文档字符串", 0.88),
            
            # 类初始化方法
            ('class \\w+:\\s*$',
             'def __init__(self, param):\n        self.param = param',
             "__init__方法", 0.90),
            
            # main入口点
            ('if __name__',
             ' == "__main__":\n    main()',
             "main入口", 0.95),
            
            # 日志记录
            ('(logger|logging)',
             '.info("message")\n.logger.debug("debug info")\n.logger.warning("warning")\n.logger.error("error")',
             "日志调用", 0.82),
        ]
        
        import re
        for pattern, completion, doc, conf in patterns:
            if re.search(pattern, context_before.strip()):
                suggestions.append(CompletionSuggestion(
                    text=completion,
                    display_text=completion.split("\n")[0] if "\n" in completion else completion,
                    confidence=conf,
                    suggestion_type="pattern",
                    documentation=doc,
                ))
        
        return suggestions
    
    async def start_watch(self, file_path: str):
        """启动文件监听模式（TODO: 实现）"""
        pass
    
    async def stop_watch(self):
        """停止监听（TODO: 实现）"""
        pass
