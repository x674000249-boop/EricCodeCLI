"""
EricCode 代码解释器

提供多层次的代码分析和解释功能：
- 概述层：快速了解代码功能
- 详细层：逐段深入分析
- 教学层：适合初学者的教程式讲解
- 可视化输出（调用图、数据流等）
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ExplanationLevel(str, Enum):
    """解释深度"""
    SUMMARY = "summary"      # 概述：快速浏览
    DETAILED = "detailed"    # 详细：深入分析
    TUTORIAL = "tutorial"    # 教学：初学者友好


@dataclass
class CodeSegment:
    """
    代码段
    
    Attributes:
        start_line: 起始行号
        end_line: 结束行号
        content: 代码内容
        description: 功能描述
        complexity: 复杂度评估 (low/medium/high)
        key_insights: 关键洞察
    """
    start_line: int
    end_line: int
    content: str
    description: str = ""
    complexity: str = "medium"
    key_insights: List[str] = field(default_factory=list)
    
    @property
    def line_range(self) -> str:
        """返回行范围表示"""
        if self.start_line == self.end_line:
            return f"第{self.start_line}行"
        return f"第{self.start_line}-{self.end_line}行"


@dataclass
class FunctionInfo:
    """函数信息"""
    name: str
    start_line: int
    end_line: int
    parameters: List[Tuple[str, Optional[str]]]  # [(param_name, type_hint), ...]
    docstring: str = ""
    return_type: Optional[str] = None
    calls: List[str] = field(default_factory=list)  # 调用的其他函数名
    is_async: bool = False


@dataclass
class ClassInfo:
    """类信息"""
    name: str
    start_line: int
    end_line: int
    base_classes: List[str]
    methods: List[FunctionInfo]
    attributes: List[str]
    docstring: str = ""


@dataclass
class ExplanationResult:
    """
    解释结果
    
    Attributes:
        file_path: 文件路径
        total_lines: 总行数
        language: 编程语言
        overview: 整体概述
        segments: 代码段列表
        functions: 函数列表
        classes: 类列表
        key_findings: 关键发现
        suggestions: 改进建议
        warnings: 警告信息
        level: 解释级别
        target_language: 输出语言
    """
    file_path: Path
    total_lines: int
    language: str = ""
    overview: str = ""
    segments: List[CodeSegment] = field(default_factory=list)
    functions: List[FunctionInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    key_findings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    level: ExplanationLevel = ExplanationLevel.SUMMARY
    target_language: str = "zh"
    
    def to_rich_panel(self) -> Any:
        """转换为Rich Panel显示"""
        from rich.panel import Panel
        from rich.text import Text
        
        title = f"📖 代码解释 - {self.file_path.name}"
        
        content_parts = [
            f"[bold green]📊 文件概览[/]\n",
            f"  [dim]文件:[/] {self.file_path.name}\n",
            f"  [dim]行数:[/] {self.total_lines}\n",
            f"  [dim]语言:[/] {self.language or '自动检测'}\n\n",
            f"[bold blue]📝 功能概述[/]\n",
            f"{self.overview}\n",
        ]
        
        if self.key_findings:
            content_parts.append(f"\n[bold yellow]💡 关键发现[/]\n")
            for i, finding in enumerate(self.key_findings[:5], 1):
                content_parts.append(f"  {i}. {finding}\n")
        
        if self.warnings:
            content_parts.append(f"\n[bold red]⚠️ 注意事项[/]\n")
            for warning in self.warnings[:3]:
                content_parts.append(f"  • {warning}\n")
        
        if self.suggestions and self.level in [ExplanationLevel.DETAILED, ExplanationLevel.TUTORIAL]:
            content_parts.append(f"\n[bold cyan]✨ 优化建议[/]\n")
            for suggestion in self.suggestions[:5]:
                content_parts.append(f"  • {suggestion}\n")
        
        return Panel(
            "".join(content_parts),
            title=title,
            border_style="blue",
        )
    
    def to_markdown(self) -> str:
        """转换为Markdown格式"""
        parts = [
            f"# 📖 代码解释: `{self.file_path.name}`\n",
            f"\n## 📊 基本信息\n",
            f"- **文件**: {self.file_path}\n",
            f"- **总行数**: {self.total_lines}\n",
            f"- **语言**: {self.language or '未知'}\n",
            f"- **解释级别**: {self.level.value}\n",
            f"\n## 📝 功能概述\n",
            f"{self.overview}\n",
        ]
        
        if self.functions:
            parts.append(f"\n## 🔧 函数列表 ({len(self.functions)}个)\n")
            for func in self.functions:
                params = ", ".join(f"{name}: {ptype}" if ptype else name for name, ptype in func.parameters)
                parts.append(f"- **`{func.name}`** ({func.line_range}): `({params})`\n")
                if func.docstring:
                    parts.append(f"  - *{func.docstring[:100]}...*\n")
        
        if self.classes:
            parts.append(f"\n ## 🏗️ 类定义 ({len(self.classes)}个)\n")
            for cls in self.classes:
                parts.append(f"- **`{cls.name}`** ({cls.line_range})")
                if cls.base_classes:
                    parts.append(f" (继承: {', '.join(cls.base_classes)})")
                parts.append(f"\n")
        
        if self.key_findings:
            parts.append(f"\n## 💡 关键发现\n")
            for i, finding in enumerate(self.key_findings, 1):
                parts.append(f"{i}. {finding}\n")
        
        if self.warnings:
            parts.append(f"\n## ⚠️ 注意事项\n")
            for warning in self.warnings:
                parts.append(f"- ⚠️ {warning}\n")
        
        if self.suggestions:
            parts.append(f"\n## ✨ 优化建议\n")
            for suggestion in self.suggestions:
                parts.append(f"- 💡 {suggestion}\n")
        
        return "".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        return {
            "file_path": str(self.file_path),
            "total_lines": self.total_lines,
            "language": self.language,
            "overview": self.overview,
            "level": self.level.value,
            "target_language": self.target_language,
            "functions_count": len(self.functions),
            "classes_count": len(self.classes),
            "segments_count": len(self.segments),
            "key_findings": self.key_findings,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "functions": [
                {
                    "name": f.name,
                    "line_range": f.line_range,
                    "parameters": [{"name": n, "type": t} for n, t in f.parameters],
                    "docstring": f.docstring,
                }
                for f in self.functions
            ],
            "classes": [
                {
                    "name": c.name,
                    "line_range": c.line_range,
                    "base_classes": c.base_classes,
                    "methods_count": len(c.methods),
                }
                for c in self.classes
            ],
        }


class CodeExplainer:
    """
    代码解释器
    
    提供多层次、多维度的代码分析功能。
    
    使用示例::
        
        explainer = CodeExplainer()
        result = await explainer.explain(
            file_path="algorithm.py",
            level=ExplanationLevel.DETAILED,
            target_language="zh"
        )
        print(result.overview)
    """
    
    def __init__(self):
        self._parser = CodeParser()
        self._analyzer = ComplexityAnalyzer()
    
    async def explain(
        self,
        file_path: str,
        level: str = "summary",
        target_language: str = "zh",
        interactive: bool = False,
        line_range: Optional[Tuple[int, int]] = None,
    ) -> ExplanationResult:
        """
        解释代码文件
        
        Args:
            file_path: 要解释的文件路径
            level: 解释深度 (summary/detailed/tutorial)
            target_language: 输出语言 (zh/en/both)
            interactive: 是否交互式模式
            line_range: 指定分析的行范围
            
        Returns:
            ExplanationResult对象
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # 读取文件内容
        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")
        total_lines = len(lines)
        
        # 如果指定了行范围，只分析该范围
        if line_range:
            start, end = line_range
            start = max(1, start or 1)
            end = min(total_lines, end or total_lines)
            lines_to_analyze = lines[start-1:end]
            content_analyze = "\n".join(lines_to_analyze)
        else:
            start, end = 1, total_lines
            content_analyze = content
        
        # 解析代码结构
        parsed_info = self._parser.parse(content_analyze, path.suffix)
        
        # 分析复杂度
        complexity_analysis = self._analyzer.analyze(content_analyze)
        
        # 根据级别生成不同详细程度的解释
        explanation_level = ExplanationLevel(level)
        
        result = ExplanationResult(
            file_path=path,
            total_lines=end - start + 1 if line_range else total_lines,
            language=parsed_info.get("language", ""),
            level=explanation_level,
            target_language=target_language,
        )
        
        # 填充解析结果
        result.functions.extend(parsed_info.get("functions", []))
        result.classes.extend(parsed_info.get("classes", []))
        
        # 生成概述
        result.overview = self._generate_overview(parsed_info, complexity_analysis, target_language)
        
        # 提取关键发现
        result.key_findings = self._extract_key_findings(parsed_info, complexity_analysis, target_language)
        
        # 生成警告
        result.warnings = self._generate_warnings(complexity_analysis, target_language)
        
        # 生成建议（仅在detailed和tutorial级别）
        if explanation_level in [ExplanationLevel.DETAILED, ExplanationLevel.TUTORIAL]:
            result.suggestions = self._generate_suggestions(complexity_analysis, target_language)
            
            # 分割代码段（仅在detailed和tutorial级别）
            if not line_range:
                result.segments = self._segment_code(lines, parsed_info)
        
        logger.info(
            f"Explained {file_path}: "
            f"{len(result.functions)} functions, "
            f"{len(result.classes)} classes, "
            f"level={level}"
        )
        
        return result
    
    def _generate_overview(
        self,
        parsed_info: Dict[str, Any],
        complexity: Dict[str, Any],
        lang: str
    ) -> str:
        """生成概述"""
        func_count = len(parsed_info.get("functions", []))
        class_count = len(parsed_info.get("classes", []))
        
        if lang == "zh":
            overview_parts = [
                f"该文件包含{func_count}个函数和{class_count}个类定义。",
            ]
            
            if class_count > 0:
                main_class = parsed_info["classes"][0].name
                overview_parts.append(f"主要类为`{main_class}`。")
            
            if func_count > 0:
                main_func = parsed_info["functions"][0].name
                overview_parts.append(f"核心函数包括`{main_func}`等。")
                
            avg_complexity = complexity.get("average_complexity", "中等")
            overview_parts.append(f"整体复杂度为{avg_complexity}。")
            
        else:  # English
            overview_parts = [
                f"This file contains {func_count} function(s) and {class_count} class(es).",
            ]
            
            if class_count > 0:
                main_class = parsed_info["classes"][0].name
                overview_parts.append(f"The main class is `{main_class}`.")
            
            if func_count > 0:
                main_func = parsed_info["functions"][0].name
                overview_parts.append(f"Key functions include `{main_func}`, etc.")
            
            avg_complexity = complexity.get("average_complexity", "Medium")
            overview_parts.append(f"Overall complexity is {avg_complexity}.")
        
        return " ".join(overview_parts)
    
    def _extract_key_findings(
        self,
        parsed_info: Dict[str, Any],
        complexity: Dict[str, Any],
        lang: str
    ) -> List[str]:
        """提取关键发现"""
        findings = []
        
        # 复杂度相关
        max_complexity_func = complexity.get("most_complex_function")
        if max_complexity_func:
            if lang == "zh":
                findings.append(f"`{max_complexity_func}` 是最复杂的函数，可能需要重构或拆分")
            else:
                findings.append(f"`{max_complexity_func}` is the most complex function and may need refactoring")
        
        # 设计模式检测
        patterns = complexity.get("detected_patterns", [])
        if patterns:
            pattern_str = ", ".join(patterns)
            if lang == "zh":
                findings.append(f"使用了设计模式: {pattern_str}")
            else:
                findings.append(f"Design patterns detected: {pattern_str}")
        
        # 函数数量
        func_count = len(parsed_info.get("functions", []))
        if func_count > 10:
            if lang == "zh":
                findings.append(f"包含较多函数({func_count}个)，考虑模块化组织")
            else:
                findings.append(f"Contains many functions ({func_count}), consider modular organization")
        
        return findings
    
    def _generate_warnings(
        self,
        complexity: Dict[str, Any],
        lang: str
    ) -> List[str]:
        """生成警告"""
        warnings = []
        
        # 长函数警告
        long_functions = complexity.get("long_functions", [])
        for func_name, line_count in long_functions[:3]:
            if lang == "zh":
                warnings.append(f"函数`{func_name}`较长({line_count}行)，可能影响可读性")
            else:
                warnings.append(f"Function `{func_name}` is lengthy ({line_count} lines), may affect readability")
        
        # 高圈复杂度警告
        high_cyclomatic = complexity.get("high_cyclomatic_complexity", [])
        for func_name, score in high_cyclomatic[:2]:
            if lang == "zh":
                warnings.append(f"函数`{func_name}`的圈复杂度为{score}，可能过于复杂")
            else:
                warnings.append(f"Function `{func_name}` has cyclomatic complexity of {score}, possibly too complex")
        
        # 深嵌套警告
        deep_nesting = complexity.get("deep_nesting", [])
        for func_name, depth in deep_nesting[:2]:
            if lang == "zh":
                warnings.append(f"函数`{func_name}`嵌套层级达{depth}，建议简化控制流")
            else:
                warnings.append(f"Function `{func_name}` has nesting depth of {depth}, consider simplifying control flow")
        
        return warnings
    
    def _generate_suggestions(
        self,
        complexity: Dict[str, Any],
        lang: str
    ) -> List[str]:
        """生成优化建议"""
        suggestions = []
        
        # TODO: 基于更详细的规则生成建议
        if lang == "zh":
            suggestions = [
                "考虑添加类型注解以提高代码可读性和IDE支持",
                "建议增加单元测试覆盖率，特别是核心逻辑部分",
                "可以添加文档字符串来提高API文档质量",
                "考虑使用logging替代print语句进行日志记录",
            ]
        else:
            suggestions = [
                "Consider adding type annotations for better IDE support and readability",
                "Increase unit test coverage, especially for core logic",
                "Add docstrings to improve API documentation quality",
                "Consider using logging instead of print statements",
            ]
        
        return suggestions
    
    def _segment_code(
        self,
        lines: List[str],
        parsed_info: Dict[str, Any]
    ) -> List[CodeSegment]:
        """将代码分割成有意义的段落"""
        segments = []
        
        current_segment_start = 1
        current_content = []
        
        # 简单实现：按空行分割
        in_code_block = False
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            if stripped:  # 非空行
                current_content.append(line)
                if not in_code_block:
                    current_segment_start = i
                    in_code_block = True
            else:  # 空行
                if in_code_block and current_content:
                    # 结束当前段
                    segment = CodeSegment(
                        start_line=current_segment_start,
                        end_line=i - 1,
                        content="\n".join(current_content),
                        description="",  # TODO: AI生成描述
                        complexity="medium",
                    )
                    segments.append(segment)
                    current_content = []
                    in_code_block = False
        
        # 处理最后一段
        if current_content:
            segment = CodeSegment(
                start_line=current_segment_start,
                end_line=len(lines),
                content="\n".join(current_content),
            )
            segments.append(segment)
        
        # 合并过小的段（少于3行的段合并到前一段）
        merged_segments = []
        for segment in segments:
            if (merged_segments and 
                segment.end_line - segment.start_line < 3 and
                merged_segments[-1].end_line + 1 >= segment.start_line):
                # 合并到前一段
                last = merged_segments[-1]
                last.end_line = segment.end_line
                last.content += "\n\n" + segment.content
            else:
                merged_segments.append(segment)
        
        return merged_segments


class CodeParser:
    """代码解析器"""
    
    def parse(self, content: str, extension: str) -> Dict[str, Any]:
        """
        解析代码结构
        
        Returns:
            包含以下键的字典：
            - language: 语言名称
            - functions: FunctionInfo列表
            - classes: ClassInfo列表
        """
        result = {
            "language": self._detect_language(extension),
            "functions": [],
            "classes": [],
        }
        
        lines = content.split("\n")
        
        # 简单的Python解析（TODO: 使用AST或tree-sitter进行更精确的解析）
        if extension in [".py"]:
            self._parse_python(lines, result)
        elif extension in [".js", ".ts", ".jsx", ".tsx"]:
            self._parse_javascript(lines, result)
        elif extension in [".go"]:
            self._parse_go(lines, result)
        elif extension in [".java"]:
            self._parse_java(lines, result)
        # 其他语言的简单解析可以在这里添加
        
        return result
    
    def _detect_language(self, extension: str) -> str:
        """根据扩展名检测语言"""
        mapping = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".jsx": "JavaScript JSX",
            ".tsx": "TypeScript JSX",
            ".java": "Java",
            ".go": "Go",
            ".rs": "Rust",
            ".cpp": "C++",
            ".c": "C",
            ".cs": "C#",
            ".rb": "Ruby",
            ".php": "PHP",
            ".swift": "Swift",
            ".kt": "Kotlin",
            ".sh": "Shell",
            ".sql": "SQL",
            ".html": "HTML",
            ".css": "CSS",
        }
        return mapping.get(extension.lower(), "Unknown")
    
    def _parse_python(self, lines: List[str], result: Dict[str, Any]):
        """解析Python代码"""
        import ast
        
        try:
            tree = ast.parse("\n".join(lines))
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    params = [(arg.arg, ast.unparse(arg.annotation) if arg.annotation else None) 
                             for arg in node.args.args]
                    
                    func_info = FunctionInfo(
                        name=node.name,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        parameters=params,
                        docstring=ast.get_docstring(node) or "",
                        is_async=isinstance(node, ast.AsyncFunctionDef),
                    )
                    result["functions"].append(func_info)
                    
                elif isinstance(node, ast.ClassDef):
                    methods = []
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            methods.append(FunctionInfo(
                                name=item.name,
                                start_line=item.lineno,
                                end_line=item.end_lineno or item.lineno,
                            ))
                    
                    class_info = ClassInfo(
                        name=node.name,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        base_classes=[ast.unparse(base) for base in node.bases],
                        methods=methods,
                        attributes=[],
                        docstring=ast.get_docstring(node) or "",
                    )
                    result["classes"].append(class_info)
                    
        except SyntaxError as e:
            logger.warning(f"Failed to parse Python code: {e}")
    
    def _parse_javascript(self, lines: List[str], result: Dict[str, Any]):
        """简单的JS/TS解析（基于正则）"""
        func_pattern = re.compile(r'(?:async\s+)?function\s+(\w+)\s*\(|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>)')
        class_pattern = re.compile(r'class\s+(\w+)(?:\s+extends\s+(\w+))?')
        
        for i, line in enumerate(lines, 1):
            # 函数匹配
            for match in func_pattern.finditer(line):
                func_name = match.group(1) or match.group(2)
                result["functions"].append(FunctionInfo(
                    name=func_name,
                    start_line=i,
                    end_line=i,  # 简化处理
                ))
            
            # 类匹配
            for match in class_pattern.finditer(line):
                class_name = match.group(1)
                base_class = match.group(2)
                result["classes"].append(ClassInfo(
                    name=class_name,
                    start_line=i,
                    end_line=i,
                    base_classes=[base_class] if base_class else [],
                    methods=[],
                    attributes=[],
                ))
    
    def _parse_go(self, lines: List[str], result: Dict[str, Any]):
        """简单的Go解析"""
        func_pattern = re.compile(r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(')
        type_pattern = re.compile(r'type\s+(\w+)\s+struct')
        
        for i, line in enumerate(lines, 1):
            for match in func_pattern.finditer(line):
                result["functions"].append(FunctionInfo(
                    name=match.group(1),
                    start_line=i,
                    end_line=i,
                ))
            
            for match in type_pattern.finditer(line):
                result["classes"].append(ClassInfo(
                    name=match.group(1),
                    start_line=i,
                    end_line=i,
                    base_classes=[],
                    methods=[],
                    attributes=[],
                ))
    
    def _parse_java(self, lines: List[str], result: Dict[str, Any]):
        """简单的Java解析"""
        class_pattern = re.compile(r'(?:public|private|protected)?\s*(?:abstract)?\s*class\s+(\w+)(?:\s+extends\s+(\w+))?')
        method_pattern = re.compile(r'(?:public|private|protected)?\s*(?:static)?\s+\w+\s+(\w+)\s*\(')
        
        for i, line in enumerate(lines, 1):
            for match in class_pattern.finditer(line):
                result["classes"].append(ClassInfo(
                    name=match.group(1),
                    start_line=i,
                    end_line=i,
                    base_classes=[match.group(2)] if match.group(2) else [],
                    methods=[],
                    attributes=[],
                ))
            
            for match in method_pattern.finditer(line):
                result["functions"].append(FunctionInfo(
                    name=match.group(1),
                    start_line=i,
                    end_line=i,
                ))


class ComplexityAnalyzer:
    """复杂度分析器"""
    
    def analyze(self, content: str) -> Dict[str, Any]:
        """分析代码复杂度"""
        lines = content.split("\n")
        
        result = {
            "average_complexity": "medium",
            "most_complex_function": None,
            "long_functions": [],
            "high_cyclomatic_complexity": [],
            "deep_nesting": [],
            "detected_patterns": [],
        }
        
        # 简单的启发式分析
        func_starts = {}  # 行号 -> 函数名
        func_lengths = {}
        current_func = None
        func_start_line = 0
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # 检测函数开始（简化版）
            if re.match(r'^def |^func |^function |^\w+\s+\w+\s*\(', stripped):
                if current_func:
                    func_lengths[current_func] = i - func_start_line
                
                # 提取函数名
                match = re.search(r'(?:def|func|function)\s+(\w+)', stripped)
                if match:
                    current_func = match.group(1)
                    func_start_line = i
                    func_starts[i] = current_func
        
        # 记录最后一个函数
        if current_func:
            func_lengths[current_func] = len(lines) - func_start_line + 1
        
        # 找出长函数
        sorted_funcs = sorted(func_lengths.items(), key=lambda x: x[1], reverse=True)
        for func_name, length in sorted_funcs[:3]:
            if length > 50:  # 超过50行认为是长函数
                result["long_functions"].append((func_name, length))
        
        if sorted_funcs:
            result["most_complex_function"] = sorted_funcs[0][0]
        
        # 估算平均复杂度
        if len(lines) < 100:
            result["average_complexity"] = "低" if len(lines) < 30 else "中等"
        elif len(lines) < 500:
            result["average_complexity"] = "中等"
        else:
            result["average_complexity"] = "高"
        
        return result
