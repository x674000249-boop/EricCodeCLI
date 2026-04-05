"""EricCode 核心功能单元测试"""
import pytest
from pathlib import Path

from ericcode.core.analyzer import PromptAnalyzer, analyze_prompt
from ericcode.config.settings import Language


class TestPromptAnalyzer:
    """提示词分析器测试"""
    
    @pytest.fixture
    def analyzer(self):
        return PromptAnalyzer()
    
    @pytest.mark.asyncio
    async def test_detect_python_language(self, analyzer):
        """测试Python语言检测"""
        prompt = "创建一个使用Flask的RESTful API"
        result = await analyzer.analyze(prompt)
        
        assert result.language == Language.PYTHON
        assert result.framework == "flask"
    
    @pytest.mark.asyncio
    async def test_detect_javascript_language(self, analyzer):
        """测试JavaScript语言检测"""
        prompt = "写一个React组件来显示用户列表"
        result = await analyzer.analyze(prompt)
        
        assert result.language in [Language.JAVASCRIPT, Language.TYPESCRIPT]
    
    @pytest.mark.asyncio
    async def test_detect_go_language(self, analyzer):
        """测试Go语言检测"""
        prompt = "实现一个goroutine并发处理任务"
        result = await analyzer.analyze(prompt)
        
        assert result.language == Language.GO
    
    @pytest.mark.asyncio
    async def test_assess_simple_complexity(self, analyzer):
        """评估简单复杂度"""
        prompt = "写一个hello world程序"
        result = await analyzer.analyze(prompt)
        
        assert result.complexity == "simple"
    
    @pytest.mark.asyncio
    async def test_assess_high_complexity(self, analyzer):
        """评估高复杂度"""
        prompt = "构建一个完整的微服务架构，包含用户认证、API网关、分布式数据库"
        result = await analyzer.analyze(prompt)
        
        assert result.complexity == "high"
    
    @pytest.mark.asyncio
    async def test_extract_requirements(self, analyzer):
        """提取特殊需求"""
        prompt = "创建一个用户注册API，需要包含错误处理、单元测试和类型注解"
        result = await analyzer.analyze(prompt)
        
        assert any("错误处理" in req for req in result.specific_requirements)
        assert any("单元测试" in req for req in result.specific_requirements)
    
    @pytest.mark.asyncio
    async def test_explicit_language_override(self, analyzer):
        """显式指定语言应覆盖自动检测"""
        prompt = "创建一个web服务器"
        result = await analyzer.analyze(prompt, explicit_language=Language.JAVA)
        
        assert result.language == Language.JAVA


class TestCodeExplainer:
    """代码解释器测试"""
    
    @pytest.fixture
    def explainer(self):
        from ericcode.core.explainer import CodeExplainer
        return CodeExplainer()
    
    @pytest.mark.asyncio
    async def test_explain_python_file(self, explainer, sample_python_code, tmp_path):
        """解释Python文件"""
        # 创建临时文件
        test_file = tmp_path / "test.py"
        test_file.write_text(sample_python_code, encoding="utf-8")
        
        # 执行解释
        result = await explainer.explain(
            file_path=str(test_file),
            level="summary",
            target_language="zh",
        )
        
        # 验证结果
        assert result.file_path == test_file
        assert result.total_lines > 0
        assert len(result.functions) >= 1  # 至少检测到quick_sort函数
        assert len(result.classes) >= 1  # 检测到DataProcessor类
        assert result.overview  # 应该有概述
    
    @pytest.mark.asyncio
    async def test_explain_javascript_file(self, explainer, sample_javascript_code, tmp_path):
        """解释JavaScript文件"""
        test_file = tmp_path / "test.js"
        test_file.write_text(sample_javascript_code, encoding="utf-8")
        
        result = await explainer.explain(str(test_file))
        
        assert result.language == "JavaScript"
        assert len(result.functions) >= 1
    
    @pytest.mark.asyncio
    async def test_explanation_levels(self, explainer, sample_python_code, tmp_path):
        """测试不同解释级别"""
        test_file = tmp_path / "test.py"
        test_file.write_text(sample_python_code, encoding="utf-8")
        
        for level in ["summary", "detailed", "tutorial"]:
            result = await explainer.explain(str(test_file), level=level)
            assert result.level.value == level
            
            if level != "summary":
                # detailed和tutorial应该有建议或更多细节
                assert hasattr(result, 'suggestions')
    
    @pytest.mark.asyncio
    async def test_explain_nonexistent_file(self, explainer):
        """解释不存在的文件应该抛出异常"""
        with pytest.raises(FileNotFoundError):
            await explainer.explain("nonexistent_file.py")
    
    @pytest.mark.asyncio
    async def test_result_to_markdown(self, explainer, sample_python_code, tmp_path):
        """测试Markdown输出格式"""
        test_file = tmp_path / "test.py"
        test_file.write_text(sample_python_code, encoding="utf-8")
        
        result = await explainer.explain(str(test_file))
        markdown = result.to_markdown()
        
        assert "# 📖 代码解释" in markdown
        assert str(result.file_path.name) in markdown
    
    @pytest.mark.asyncio
    async def test_result_to_dict(self, explainer, sample_python_code, tmp_path):
        """测试字典输出格式"""
        test_file = tmp_path / "test.py"
        test_file.write_text(sample_python_code, encoding="utf-8")
        
        result = await explainer.explain(str(test_file))
        data = result.to_dict()
        
        assert isinstance(data, dict)
        assert "file_path" in data
        assert "total_lines" in data
        assert "functions_count" in data
        assert "classes_count" in data


class TestCodeCompleter:
    """代码补全器测试"""
    
    @pytest.fixture
    def completer(self):
        from ericcode.core.completer import CodeCompleter
        return CodeCompleter(watch_mode=False)
    
    def test_complete_existing_file(self, completer, sample_python_code, tmp_path):
        """补全已存在的文件"""
        test_file = tmp_path / "complete_test.py"
        test_file.write_text(sample_python_code, encoding="utf-8")
        
        result = completer.get_suggestions(str(test_file), line=3, column=5)
        
        assert isinstance(result.suggestions, list)
        assert result.cursor_line == 3
        assert result.latency_ms > 0
    
    def test_complete_nonexistent_file(self, completer):
        """补全不存在的文件应该返回空结果"""
        result = completer.get_suggestions("nonexistent.py")
        
        assert len(result.suggestions) == 0
    
    def test_completion_has_best_suggestion(self, completer, sample_python_code, tmp_path):
        """补全结果应该有最佳建议（即使为None）"""
        test_file = tmp_path / "best_suggestion.py"
        test_file.write_text(sample_python_code, encoding="utf-8")
        
        result = completer.get_suggestions(str(test_file))
        
        # best_suggestion可能为None，但属性应该存在
        assert hasattr(result, 'best_suggestion')


class TestConfigSettings:
    """配置管理测试"""
    
    def test_default_settings_exist(self):
        """默认配置应该存在"""
        from ericcode.config.settings import settings
        
        assert settings is not None
        assert settings.cache is not None
        assert settings.openai is not None
        assert settings.ui is not None
    
    def test_config_dir_is_path(self):
        """配置目录应该是Path对象"""
        from ericcode.config.settings import settings
        
        assert isinstance(settings.config_dir, Path)
        assert isinstance(settings.data_dir, Path)


class TestProviderBase:
    """模型提供商基础类测试"""
    
    def test_message_creation(self):
        """消息对象创建"""
        from ericcode.providers.base import Message, MessageRole
        
        msg = Message(role=MessageRole.USER, content="Hello")
        
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"
        assert msg.name is None
    
    def test_message_to_dict(self):
        """消息转换为字典"""
        from ericcode.providers.base import Message, MessageRole
        
        msg = Message(role=MessageRole.SYSTEM, content="System message", name="system")
        msg_dict = msg.to_dict()
        
        assert msg_dict["role"] == "system"
        assert msg_dict["content"] == "System message"
        assert msg_dict["name"] == "system"
    
    def test_generation_options_defaults(self):
        """生成选项默认值"""
        from ericcode.providers.base import GenerationOptions
        
        options = GenerationOptions()
        
        assert options.temperature == 0.7
        assert options.max_tokens == 2048
        assert options.top_p == 1.0
    
    def test_model_response_creation(self):
        """模型响应对象创建"""
        from ericcode.providers.base import ModelResponse, TokenUsage
        
        response = ModelResponse(
            content="Generated code",
            model_used="gpt-4o",
            tokens_used=TokenUsage(prompt_tokens=100, completion_tokens=50),
            latency_ms=1500,
        )
        
        assert response.content == "Generated code"
        assert response.tokens_used.total_tokens == 150
        assert response.is_complete
        assert not response.is_truncated
    
    def test_token_usage_calculation(self):
        """Token使用统计计算"""
        from ericcode.providers.base import TokenUsage
        
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50)
        
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
