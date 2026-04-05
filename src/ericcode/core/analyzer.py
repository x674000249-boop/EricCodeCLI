"""
EricCode 提示词分析器

负责分析和理解用户的自然语言输入，提取关键信息：
- 检测编程语言
- 识别技术框架
- 评估任务复杂度
- 提取特定需求
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from ..config.settings import Language

logger = logging.getLogger(__name__)


@dataclass
class PromptAnalysis:
    """提示词分析结果"""
    language: Optional[Language]
    framework: Optional[str]
    complexity: str  # simple/medium/high
    specific_requirements: List[str]
    estimated_lines: int


# 语言关键词映射
LANGUAGE_KEYWORDS = {
    Language.PYTHON: [
        "python", "py", "django", "flask", "fastapi", "numpy", "pandas",
        "pytest", "pip", "virtualenv", "jupyter", "colab",
        "装饰器", "推导式", "切片", "生成器", "异步"
    ],
    Language.JAVASCRIPT: [
        "javascript", "js", "node", "nodejs", "npm", "express",
        "react", "vue", "angular", "webpack", "babel", "typescript兼容",
        "回调", "promise", "async/await", "dom", "浏览器"
    ],
    Language.TYPESCRIPT: [
        "typescript", "ts", ".ts", "tsx", "接口", "类型注解",
        "泛型", "枚举", "angular"
    ],
    Language.JAVA: [
        "java", "spring", "springboot", "maven", "gradle",
        "jvm", "servlet", "jsp", "android", "kotlin兼容",
        "类", "对象", "继承", "接口", "抽象"
    ],
    Language.GO: [
        "go", "golang", "goroutine", "channel", "gin", "echo",
        "并发", "协程", "接口", "结构体"
    ],
    Language.RUST: [
        "rust", "cargo", "所有权", "借用", "生命周期",
        "trait", "模式匹配", "unsafe", "wasm"
    ],
    Language.CPP: [
        "c++", "cpp", "stl", "模板", "指针", "引用",
        "面向对象", "内存管理", "qt", "cmake"
    ],
    Language.CSHARP: [
        "c#", "csharp", ".net", "asp.net", "unity", "linq",
        "委托", "事件", "泛型"
    ],
    Language.SHELL: [
        "shell", "bash", "sh", "zsh", "脚本", "命令行",
        "管道", "重定向", "cron", "devops"
    ],
    Language.SQL: [
        "sql", "数据库", "查询", "mysql", "postgresql",
        "select", "insert", "update", "join", "索引"
    ],
}

# 框架关键词映射
FRAMEWORK_KEYWORDS = {
    "fastapi": ["fastapi", "快速api"],
    "flask": ["flask"],
    "django": ["django"],
    "express": ["express", "express.js"],
    "spring": ["spring", "spring boot", "springboot"],
    "gin": ["gin (go)"],
    "rails": ["rails", "ruby on rails"],
    "laravel": ["laravel"],
    "next.js": ["next", "next.js", "nextjs"],
    "vue": ["vue", "vue.js", "nuxt"],
    "react": ["react", "react.js", "nextjs"],
}


async def analyze_prompt(
    prompt: str,
    explicit_language: Optional[Language] = None
) -> PromptAnalysis:
    """
    分析用户提示词
    
    Args:
        prompt: 用户输入的文本
        explicit_language: 用户明确指定的语言（如果有的话）
        
    Returns:
        PromptAnalysis对象
    """
    analyzer = PromptAnalyzer()
    return await analyzer.analyze(prompt, explicit_language)


class PromptAnalyzer:
    """提示词分析器"""
    
    async def analyze(
        self,
        prompt: str,
        explicit_language: Optional[Language] = None
    ) -> PromptAnalysis:
        """执行分析"""
        prompt_lower = prompt.lower()
        
        # 1. 语言检测
        language = explicit_language or self._detect_language(prompt_lower)
        
        # 2. 框架检测
        framework = self._detect_framework(prompt_lower)
        
        # 3. 复杂度评估
        complexity = self._assess_complexity(prompt)
        
        # 4. 提取特殊要求
        requirements = self._extract_requirements(prompt)
        
        # 5. 估算代码行数
        estimated_lines = self._estimate_lines(complexity)
        
        analysis = PromptAnalysis(
            language=language,
            framework=framework,
            complexity=complexity,
            specific_requirements=requirements,
            estimated_lines=estimated_lines,
        )
        
        logger.debug(f"Prompt analyzed: {analysis}")
        return analysis
    
    def _detect_language(self, prompt: str) -> Optional[Language]:
        """检测目标编程语言"""
        scores = {}
        
        for language, keywords in LANGUAGE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in prompt)
            if score > 0:
                scores[language] = score
        
        if not scores:
            return None
        
        # 返回得分最高的语言
        best_language = max(scores.items(), key=lambda x: x[1])
        
        # 如果最高分太低（<2），可能检测不准确
        if best_language[1] < 2:
            return None
        
        logger.debug(f"Detected language: {best_language[0].value} (score={best_language[1]})")
        return best_language[0]
    
    def _detect_framework(self, prompt: str) -> Optional[str]:
        """检测使用的框架"""
        for framework, keywords in FRAMEWORK_KEYWORDS.items():
            if any(kw in prompt for kw in keywords):
                logger.debug(f"Detected framework: {framework}")
                return framework
        return None
    
    def _assess_complexity(self, prompt: str) -> str:
        """评估任务复杂度"""
        high_complexity_indicators = [
            r'完整.*系统', r'完整.*应用', r'完整.*项目',
            r'microservice', r'micro-services', '微服务',
            r'distributed', '分布式',
            r'authentication.*authorization', '认证授权',
            r'real.time', '实时',
            r'scalable', '可扩展',
            r'production.*ready', '生产环境',
            r'enterprise', '企业级',
            r'multiple.*integration', '多个集成',
            r'complex.*algorithm', '复杂算法',
            r'machine.learning', '机器学习',
            r'api.*gateway', 'API网关',
        ]
        
        medium_complexity_indicators = [
            r'api', 'rest', 'graphql', 'endpoint',
            r'database', '数据库', r'model', '模型',
            r'auth', 'login', 'register', '用户',
            r'crud', '增删改查',
            r'file.*upload', '文件上传',
            r'validation', '验证',
            r'error.*handling', '错误处理',
            r'unit.*test', '单元测试',
            r'class', '类', r'interface', '接口',
            r'module', '模块', r'component', '组件',
        ]
        
        simple_complexity_indicators = [
            r'hello.world', '你好世界', '示例',
            r'simple', '简单',
            r'basic', '基础',
            r'quick', '快速',
            r'small', '小',
            r'single.*function', '单个函数',
            r'one.liner', '单行',
            r'demo', '演示',
        ]
        
        import re
        
        high_score = sum(1 for pattern in high_complexity_indicators if re.search(pattern, prompt, re.IGNORECASE))
        medium_score = sum(1 for pattern in medium_complexity_indicators if re.search(pattern, prompt, re.IGNORECASE))
        simple_score = sum(1 for pattern in simple_complexity_indicators if re.search(pattern, prompt, re.IGNORECASE))
        
        if high_score > 0:
            return "high"
        elif medium_score >= 2 or (medium_score > 0 and len(prompt.split()) > 20):
            return "medium"
        elif simple_score > 0:
            return "simple"
        else:
            # 基于长度判断
            word_count = len(prompt.split())
            if word_count < 10:
                return "simple"
            elif word_count < 30:
                return "medium"
            else:
                return "high"
    
    def _extract_requirements(self, prompt: str) -> List[str]:
        """提取特殊需求"""
        requirements = []
        
        # 类型注解
        if any(kw in prompt for kw in ['type hint', '类型注解', 'typing']):
            requirements.append("添加类型注解")
        
        # 文档字符串
        if any(kw in prompt for kw in ['docstring', '文档', '注释完整']):
            requirements.append("添加完整的文档字符串")
        
        # 错误处理
        if any(kw in prompt for kw in ['error handling', '错误处理', '异常处理']):
            requirements.append("包含完善的错误处理")
        
        # 测试
        if any(kw in prompt for kw in ['test', '测试', '单元测试']):
            requirements.append("包含单元测试")
        
        # 性能优化
        if any(kw in prompt for kw in ['performance', '性能', '优化', '高效']):
            requirements.append("考虑性能优化")
        
        # 安全性
        if any(kw in prompt for kw in ['security', '安全', 'secure', '加密']):
            requirements.append("符合安全最佳实践")
        
        # 异步
        if any(kw in prompt for kw in ['async', '异步', 'concurrent', '并发']):
            requirements.append("使用异步/并发模式")
        
        # 国际化
        if any(kw in prompt for kw in ['i18n', '国际化', '多语言']):
            requirements.append("支持国际化")
        
        return requirements
    
    def _estimate_lines(self, complexity: str) -> int:
        """估算生成的代码行数"""
        estimates = {
            "simple": (5, 30),
            "medium": (30, 150),
            "high": (150, 500),
        }
        
        min_lines, max_lines = estimates.get(complexity, (30, 150))
        return (min_lines + max_lines) // 2  # 返回平均值
