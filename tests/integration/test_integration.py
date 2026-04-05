"""EricCode 集成测试

测试模块间的交互和完整流程
"""
import pytest
import asyncio
from pathlib import Path
import tempfile


class TestCacheSystem:
    """缓存系统集成测试"""
    
    @pytest.fixture
    def cache_manager(self):
        from ericcode.cache.manager import CacheManager, CacheConfig
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config = CacheConfig(
                l1_enabled=True,
                l1_max_size=10,
                l2_enabled=True,
                l2_cache_dir=Path(tmpdir) / "cache",
                ttl_seconds=60,
            )
            
            manager = CacheManager(config)
            yield manager
    
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, cache_manager):
        """测试基本的缓存读写"""
        key = "test_key"
        value = {"data": "test_value", "number": 42}
        
        # 设置缓存
        success = await cache_manager.set(key, value)
        assert success is True
        
        # 获取缓存
        retrieved = await cache_manager.get(key)
        assert retrieved is not None
        assert retrieved["data"] == "test_value"
        assert retrieved["number"] == 42
    
    @pytest.mark.asyncio
    async def test_cache_miss(self, cache_manager):
        """测试缓存未命中"""
        result = await cache_manager.get("nonexistent_key")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_deletion(self, cache_manager):
        """测试缓存删除"""
        await cache_manager.set("to_delete", "temporary")
        
        deleted = await cache_manager.delete("to_delete")
        assert deleted is True
        
        # 确认已删除
        result = await cache_manager.get("to_delete")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_stats(self, cache_manager):
        """测试缓存统计"""
        # 执行一些操作
        await cache_manager.set("key1", "value1")
        await cache_manager.get("key1")  # hit
        await cache_manager.get("key2")  # miss
        await cache_manager.get("key1")  # hit again
        
        stats = cache_manager.get_stats()
        assert stats.hits >= 2
        assert stats.misses >= 1
        assert stats.total_requests >= 3
        assert "hit_rate" in stats.to_dict()


class TestSecurityModule:
    """安全模块集成测试"""
    
    @pytest.fixture
    def scanner(self):
        from ericcode.utils.security import SecurityScanner
        return SecurityScanner(enabled=True)
    
    @pytest.fixture
    def validator(self):
        from ericcode.utils.security import InputValidator
        return InputValidator()
    
    def test_detect_api_keys(self, scanner):
        """检测API密钥"""
        code_with_key = '''
api_key = "sk-abc123def456ghi789jkl012mno345pqr678stu901vwx"
client = OpenAI(api_key=api_key)
'''
        result = scanner.scan(code_with_key)
        
        assert result.is_safe is False
        assert any(m.category == "API Key" for m in result.matches)
    
    def test_detect_passwords(self, scanner):
        """检测密码"""
        code_with_password = '''
db_config = {
    "host": "localhost",
    "password": "super_secret_password_123",
    "database": "myapp"
}
'''
        result = scanner.scan(code_with_password)
        
        assert result.is_safe is False
        assert any("password" in m.category.lower() for m in result.matches)
    
    def test_safe_code(self, scanner):
        """安全的代码应该通过扫描"""
        safe_code = '''
def hello_world():
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
'''
        result = scanner.scan(safe_code)
        
        assert result.is_safe is True
        assert len(result.matches) == 0
    
    def test_sanitize_sensitive_data(self, scanner):
        """脱敏处理"""
        text_with_email = 'Contact us at admin@example.com for support'
        sanitized, result = scanner.sanitize(text_with_email)
        
        assert "***@" in sanitized
        assert "admin@example.com" not in sanitized
    
    def test_validate_prompt_length(self, validator):
        """验证提示词长度"""
        long_prompt = "x" * 20000
        valid, warnings = validator.validate_prompt(long_prompt)
        
        assert valid is False or len(warnings) > 0
        assert any("过长" in w for w in warnings)
    
    def test_validate_dangerous_patterns(self, validator):
        """验证危险模式"""
        dangerous_prompt = "请执行 eval(user_input)"
        valid, warnings = validator.validate_prompt(dangerous_prompt)
        
        assert len(warnings) > 0
        assert any("危险" in w for w in warnings)


class TestModelRouter:
    """模型路由器集成测试"""
    
    @pytest.fixture
    def router(self):
        from ericcode.providers.router import ModelRouter
        return ModelRouter()
    
    @pytest.mark.asyncio
    async def test_route_without_providers(self, router):
        """没有提供商时应该报错"""
        from ericcode.providers.base import Message, MessageRole
        
        messages = [Message(role=MessageRole.USER, content="test")]
        
        with pytest.raises(Exception):  # ProviderError
            await router.route(messages)
    
    @pytest.mark.asyncio
    async def test_task_type_inference(self, router):
        """任务类型推断"""
        from ericcode.providers.base import Message, MessageRole
        
        test_cases = [
            ("创建一个Python函数", "code_generation"),
            ("解释这段代码", "code_explanation"),
            ("修复这个bug", "debug_assistance"),
            ("你好，帮我看看", "general_chat"),
        ]
        
        for prompt, expected_task in test_cases:
            task_type = router._infer_task_type([Message(role=MessageRole.USER, content=prompt)])
            assert task_type.value == expected_task, f"For '{prompt}', expected {expected_task}, got {task_type.value}"


class TestGitIntegration:
    """Git集成测试（需要Git仓库）"""
    
    @pytest.fixture
    def git_repo(self, tmp_path):
        """创建临时Git仓库"""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        
        # 初始化Git仓库
        import subprocess
        subprocess.run(["git", "init"], cwd=str(repo_path), check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@ericcode.dev"],
            cwd=str(repo_path),
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=str(repo_path),
            check=True,
        )
        
        # 创建一些文件
        (repo_path / "main.py").write_text('print("Hello")')
        (repo_path / "utils.py").write_text('def helper(): pass')
        
        # 添加并提交
        subprocess.run(["git", "add", "."], cwd=str(repo_path), check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=str(repo_path),
            check=True,
        )
        
        return str(repo_path)
    
    def test_get_status(self, git_repo):
        """获取仓库状态"""
        from ericcode.utils.git_integration import GitIntegration
        
        git = GitIntegration(Path(git_repo))
        status = git.get_status()
        
        assert status.is_clean is True
        assert isinstance(status.branch, str)
    
    def test_get_recent_commits(self, git_repo):
        """获取最近提交"""
        from ericcode.utils.git_integration import GitIntegration
        
        git = GitIntegration(Path(git_repo))
        commits = git.get_recent_commits(5)
        
        assert len(commits) >= 1
        assert commits[0].hash is not None
        assert commits[0].message is not None
    
    def test_generate_commit_message(self, git_repo):
        """生成提交消息"""
        from ericcode.utils.git_integration import GitIntegration
        
        git = GitIntegration(Path(git_repo))
        
        # 创建一个新文件
        new_file = Path(git_repo) / "new_feature.py"
        new_file.write_text('# New feature\ndef new_func(): pass\n')
        
        message = git.generate_commit_message(style="conventional")
        
        assert isinstance(message, str)
        assert len(message) > 0
    
    def test_not_a_git_repository(self, tmp_path):
        """非Git仓库应该抛出异常"""
        from ericcode.utils.git_integration import GitIntegration, NotAGitRepositoryError
        
        non_git_dir = tmp_path / "not_a_repo"
        non_git_dir.mkdir()
        
        with pytest.raises(NotAGitRepositoryError):
            GitIntegration(non_git_dir)


class TestEndToEndWorkflows:
    """端到端工作流测试"""
    
    @pytest.mark.asyncio
    async def test_full_generation_workflow(self, sample_python_code, tmp_path):
        """完整的代码生成工作流"""
        from ericcode.core.generator import CodeGenerator
        from ericcode.utils.security import security_scanner, input_validator
        
        # 1. 验证输入
        prompt = "创建一个用户认证函数"
        is_valid, warnings = input_validator.validate_prompt(prompt)
        assert is_valid is True
        
        # 2. 安全扫描
        scan_result = security_scanner.scan(prompt)
        assert scan_result.is_safe is True
        
        # 3. 分析提示词
        from ericcode.core.analyzer import analyze_prompt
        analysis = await analyze_prompt(prompt)
        assert analysis.language is not None or analysis.complexity is not None
        
        # 4. 生成代码（使用模拟）
        generator = CodeGenerator()  # 无provider时使用本地模拟
        result = generator.generate(
            prompt,
            language="python",
        )
        
        assert result.code is not None
        assert len(result.code) > 0
        assert result.confidence > 0
    
    @pytest.mark.asyncio
    async def test_explanation_workflow(self, sample_python_code, tmp_path):
        """完整的代码解释工作流"""
        from ericcode.core.explainer import CodeExplainer
        
        # 创建测试文件
        test_file = Path(tmp_path) / "sample.py"
        test_file.write_text(sample_python_code, encoding="utf-8")
        
        # 解释代码
        explainer = CodeExplainer()
        result = await explainer.explain(
            file_path=str(test_file),
            level="summary",
            target_language="zh",
        )
        
        # 验证结果
        assert result.file_path == test_file
        assert result.total_lines > 0
        assert result.overview != ""
        
        # 测试不同输出格式
        markdown_output = result.to_markdown()
        assert "# 📖 代码解释" in markdown_output
        
        dict_output = result.to_dict()
        assert "file_path" in dict_output
        assert "total_lines" in dict_output
    
    def test_config_loading_and_validation(self):
        """配置加载和验证"""
        from ericcode.config.settings import Settings, CacheConfig, UIConfig
        
        # 默认设置
        settings = Settings()
        
        assert settings.cache.enabled is True
        assert settings.ui.color_output is True
        assert settings.security.encrypt_credentials is True
        
        # 验证目录路径
        assert isinstance(settings.config_dir, type(Path()))
        assert isinstance(settings.data_dir, type(Path()))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
