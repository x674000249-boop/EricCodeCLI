"""
EricCode 代码生成器

核心功能：基于自然语言描述生成高质量、可执行的代码
支持：
- 多语言代码生成
- 上下文感知
- 模板系统
- 代码验证
- 流式输出
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config.settings import Language
from ..providers.base import (
    GenerationOptions,
    Message,
    MessageRole,
    ModelProvider,
    ModelResponse,
)

logger = logging.getLogger(__name__)


@dataclass
class GeneratedCode:
    """
    生成的代码结果
    
    Attributes:
        code: 生成的代码文本
        language: 检测或指定的编程语言
        explanation: 代码说明
        confidence: 置信度 (0.0-1.0)
        model_used: 使用的模型
        latency_ms: 响应时间（毫秒）
        suggestions: 改进建议列表
    """
    code: str
    language: Optional[str] = None
    explanation: str = ""
    confidence: float = 0.0
    model_used: str = ""
    latency_ms: float = 0.0
    suggestions: List[str] = field(default_factory=list)
    
    def save_to_file(self, path: Path) -> None:
        """保存代码到文件"""
        path.write_text(self.code, encoding="utf-8")
        logger.info(f"Code saved to {path}")


@dataclass
class GenerateRequest:
    """
    生成请求
    
    Attributes:
        prompt: 用户输入的自然语言提示词
        language: 目标编程语言（可选，自动检测）
        framework: 目标框架（可选）
        context_path: 上下文文件/目录路径
        output_path: 输出文件路径
        options: 生成选项
    """
    prompt: str
    language: Optional[Language] = None
    framework: Optional[str] = None
    context_path: Optional[Path] = None
    output_path: Optional[Path] = None
    options: Optional[GenerationOptions] = None


class CodeGenerator:
    """
    代码生成器
    
    负责将用户的自然语言描述转换为可执行的代码。
    
    使用示例::
        
        generator = CodeGenerator()
        result = generator.generate(
            "创建一个RESTful API的用户认证模块",
            language=Language.PYTHON,
            framework="fastapi"
        )
        print(result.code)
    """
    
    def __init__(self, provider: Optional[ModelProvider] = None):
        """
        初始化生成器
        
        Args:
            provider: 模型提供商实例。如果为None，将使用默认配置初始化。
        """
        self._provider = provider
        self._context_analyzer = ContextAnalyzer()
        self._template_engine = TemplateEngine()
        self._code_validator = CodeValidator()
    
    def generate(
        self,
        prompt: str,
        **kwargs
    ) -> GeneratedCode:
        """
        同步接口：生成代码
        
        Args:
            prompt: 自然语言提示词
            **kwargs: 其他参数（language, framework等）
            
        Returns:
            GeneratedCode对象
        """
        import asyncio
        
        # 如果在异步上下文中运行，直接调用async版本
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop and loop.is_running():
            # 已经在事件循环中，需要用新线程
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._generate_async(prompt, **kwargs))
                return future.result()
        else:
            return asyncio.run(self._generate_async(prompt, **kwargs))
    
    async def _generate_async(
        self,
        prompt: str,
        **kwargs
    ) -> GeneratedCode:
        """
        异步核心：执行代码生成流程
        """
        start_time = time.perf_counter()
        
        # 1. 构建请求对象
        request = self._build_request(prompt, **kwargs)
        
        # 2. 分析提示词
        analysis = await self._analyze_prompt(request)
        logger.info(f"Prompt analysis: language={analysis.language}, complexity={analysis.complexity}")
        
        # 3. 收集上下文
        if request.context_path:
            context = await self._collect_context(request.context_path)
        else:
            context = ""
        
        # 4. 构建系统提示词
        system_prompt = self._build_system_prompt(analysis, context)
        
        # 5. 构建用户消息
        user_message = self._build_user_message(request.prompt, analysis)
        
        # 6. 调用模型
        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=user_message),
        ]
        
        response = await self._call_model(messages, request.options)
        
        # 7. 后处理和验证
        generated_code = await self._post_process(response, analysis)
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        generated_code.latency_ms = latency_ms
        
        logger.info(
            f"Code generation completed in {latency_ms:.2f}ms, "
            f"confidence={generated_code.confidence:.2f}"
        )
        
        # 8. 可选：保存到文件
        if request.output_path:
            generated_code.save_to_file(request.output_path)
        
        return generated_code
    
    def _build_request(self, prompt: str, **kwargs) -> GenerateRequest:
        """构建请求对象"""
        # 处理语言参数
        language = kwargs.get("language")
        
        # 初始化路由器
        if not hasattr(self, '_router'):
            from ..providers.router import get_model_router
            self._router = get_model_router()
        
        return GenerateRequest(
            prompt=prompt,
            language=language,
            framework=kwargs.get("framework"),
            context_path=Path(kwargs["context_path"]) if kwargs.get("context_path") else None,
            output_path=Path(kwargs["output_path"]) if kwargs.get("output_path") else None,
            options=GenerationOptions(
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 4096),
            ) if any(k in kwargs for k in ["temperature", "max_tokens"]) else None,
        )
    
    async def _analyze_prompt(self, request: GenerateRequest) -> PromptAnalysis:
        """分析用户提示词"""
        analyzer = PromptAnalyzer()
        return await analyzer.analyze(request.prompt, request.language)
    
    async def _collect_context(self, context_path: Path) -> str:
        """收集上下文信息"""
        return await self._context_analyzer.analyze(context_path)
    
    def _build_system_prompt(self, analysis: PromptAnalysis, context: str = "") -> str:
        """
        构建系统提示词
        
        这是代码生成的核心部分，决定了输出质量。
        """
        if analysis.language:
            # 检查是否是枚举对象
            if hasattr(analysis.language, 'value'):
                language_name = analysis.language.value
            else:
                language_name = analysis.language
        else:
            language_name = "自动检测"
        
        prompt_parts = [
            f"# 你是一个专业的代码生成AI助手",
            f"",
            f"## 任务",
            f"根据用户的自然语言描述，生成高质量、可执行的{language_name}代码。",
            f"",
            f"## 要求",
            f"- 代码语法正确，可以直接运行",
            f"- 遵循{language_name}的编码规范和最佳实践",
            f"- 包含必要的错误处理和边界条件检查",
            f"- 添加清晰的中文注释解释关键逻辑",
            f"- 使用有意义的变量和函数命名",
            f"- 考虑性能和安全性",
        ]
        
        if analysis.framework:
            prompt_parts.extend([
                f"",
                f"## 技术栈",
                f"- 语言: {language_name}",
                f"- 框架: {analysis.framework}",
            ])
        
        if analysis.complexity == "high":
            prompt_parts.extend([
                f"",
                f"## 复杂度注意",
                f"这是一个复杂的任务，请确保：",
                f"- 代码结构清晰，模块化设计",
                f"- 添加类型注解（如果语言支持）",
                f"- 包含完整的文档字符串",
            ])
        
        if context:
            prompt_parts.extend([
                f"",
                f"## 项目上下文",
                f"{context}",
            ])
        
        prompt_parts.extend([
            f"",
            f"## 输出格式",
            f"直接输出代码，不要包含额外的markdown标记（如```python）。",
            f"如果需要解释，在代码后以注释形式简要说明。",
        ])
        
        return "\n".join(prompt_parts)
    
    def _build_user_message(self, prompt: str, analysis: PromptAnalysis) -> str:
        """构建用户消息"""
        message_parts = [f"请生成以下功能的代码：\n\n"]
        message_parts.append(f"{prompt}\n")
        
        if analysis.specific_requirements:
            message_parts.append("\n特殊要求：\n")
            for req in analysis.specific_requirements:
                message_parts.append(f"- {req}")
        
        return "".join(message_parts)
    
    async def _call_model(
        self,
        messages: List[Message],
        options: Optional[GenerationOptions]
    ) -> ModelResponse:
        """调用模型API"""
        if not hasattr(self, '_router'):
            from ..providers.router import get_model_router
            self._router = get_model_router()
        
        response, decision = await self._router.route(messages, options)
        return response
    
    async def _post_process(
        self,
        response: ModelResponse,
        analysis: PromptAnalysis
    ) -> GeneratedCode:
        """后处理响应"""
        code = response.content.strip()
        
        # 清理可能的markdown代码块标记
        if code.startswith("```"):
            lines = code.split("\n")
            # 移除第一行的 ```language 和最后一行的 ```
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            code = "\n".join(lines).strip()
        
        # 验证代码质量
        validation_result = await self._code_validator.validate(code, analysis.language)
        
        # 处理语言值
        language_value = None
        if analysis.language:
            if hasattr(analysis.language, 'value'):
                language_value = analysis.language.value
            else:
                language_value = analysis.language
        
        return GeneratedCode(
            code=code,
            language=language_value,
            confidence=validation_result.confidence_score,
            model_used=response.model_used,
            explanation="",  # TODO: 从响应中提取或单独生成
            suggestions=validation_result.suggestions,
        )


class PromptAnalyzer:
    """提示词分析器"""
    
    async def analyze(
        self,
        prompt: str,
        explicit_language: Optional[Language] = None
    ) -> "PromptAnalysis":
        """分析提示词，提取关键信息"""
        from .analyzer import analyze_prompt
        return await analyze_prompt(prompt, explicit_language)


@dataclass
class PromptAnalysis:
    """提示词分析结果"""
    language: Optional[Language]
    framework: Optional[str]
    complexity: str  # simple/medium/high
    specific_requirements: List[str]
    estimated_lines: int


class ContextAnalyzer:
    """上下文分析器"""
    
    async def analyze(self, path: Path) -> str:
        """分析文件或目录，提取有用的上下文信息"""
        if path.is_file():
            return await self._analyze_file(path)
        elif path.is_dir():
            return await self._analyze_directory(path)
        else:
            raise FileNotFoundError(f"Context path not found: {path}")
    
    async def _analyze_file(self, file_path: Path) -> str:
        """分析单个文件"""
        content = file_path.read_text(encoding="utf-8")
        
        # 提取前100行作为摘要（避免token过多）
        lines = content.split("\n")
        preview = "\n".join(lines[:100])
        
        if len(lines) > 100:
            preview += f"\n... (共{len(lines)}行)"
        
        return f"参考文件: {file_path.name}\n\n{preview}"
    
    async def _analyze_directory(self, dir_path: Path) -> str:
        """分析目录结构"""
        files = list(dir_path.rglob("*.*"))
        
        info_parts = [
            f"项目目录: {dir_path.name}",
            f"文件数量: {len(files)}",
            "",
            "主要文件:",
        ]
        
        for f in sorted(files)[:20]:  # 限制数量
            rel_path = f.relative_to(dir_path)
            size = f.stat().st_size
            info_parts.append(f"  - {rel_path} ({self._format_size(size)})")
        
        if len(files) > 20:
            info_parts.append(f"  ... 以及其他 {len(files) - 20} 个文件")
        
        return "\n".join(info_parts)
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f}TB"


class TemplateEngine:
    """模板引擎（预留）"""
    pass


class CodeValidator:
    """代码验证器"""
    
    async def validate(
        self,
        code: str,
        language: Optional[Language]
    ) -> "ValidationResult":
        """验证生成的代码质量"""
        score = 1.0
        suggestions = []
        
        # 基本检查
        if not code or len(code.strip()) < 10:
            score -= 0.3
            suggestions.append("生成的代码过短，可能不完整")
        
        # 语言特定检查
        if language:
            lang_checks = {
                Language.PYTHON: self._check_python,
                Language.JAVASCRIPT: self._check_javascript,
                Language.JAVA: self._check_java,
                Language.GO: self._check_go,
            }
            
            check_func = lang_checks.get(language)
            if check_func:
                check_suggestions = check_func(code)
                suggestions.extend(check_suggestions)
                if check_suggestions:
                    score -= min(len(check_suggestions) * 0.05, 0.3)
        
        return ValidationResult(
            confidence_score=max(0.0, min(1.0, score)),
            is_valid=score >= 0.7,
            suggestions=suggestions,
        )
    
    def _check_python(self, code: str) -> List[str]:
        """Python特定检查"""
        issues = []
        
        # 检查基本语法
        try:
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            issues.append(f"语法错误: {e}")
        
        # 检查是否有函数定义
        if "def " not in code and "class " not in code:
            issues.append("建议定义函数或类来组织代码")
        
        return issues
    
    def _check_javascript(self, code: str) -> List[str]:
        """JavaScript特定检查"""
        issues = []
        # TODO: 实现JS语法检查
        return issues
    
    def _check_java(self, code: str) -> List[str]:
        """Java特定检查"""
        issues = []
        # TODO: 实现Java语法检查
        return issues
    
    def _check_go(self, code: str) -> List[str]:
        """Go特定检查"""
        issues = []
        # TODO: 实现Go语法检查
        return issues


@dataclass
class ValidationResult:
    """验证结果"""
    confidence_score: float
    is_valid: bool
    suggestions: List[str]
