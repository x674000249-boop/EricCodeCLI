"""
EricCode 安全模块

提供：
- 敏感信息检测和过滤
- API密钥安全管理
- 数据脱敏
- 输入验证
- 隐私保护
"""

from __future__ import annotations

import logging
import re
import os
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SensitivityLevel(str, Enum):
    """敏感度级别"""
    CRITICAL = "critical"  # 高危：API密钥、密码、私钥
    HIGH = "high"          # 高：个人身份信息、财务信息
    MEDIUM = "medium"      # 中：邮箱地址、IP地址
    LOW = "low"            # 低：用户名、文件路径


@dataclass
class SensitiveDataMatch:
    """敏感数据匹配结果"""
    value: str
    masked_value: str
    category: str
    sensitivity: SensitivityLevel
    position: Tuple[int, int]  # (start, end)
    pattern_name: str
    
    def __str__(self) -> str:
        return f"[{self.sensitivity.value.upper()}] {self.category}: {self.masked_value}"


@dataclass
class SecurityScanResult:
    """安全扫描结果"""
    is_safe: bool
    matches: List[SensitiveDataMatch] = field(default_factory=list)
    risk_score: float = 0.0  # 0.0 - 1.0
    warnings: List[str] = field(default_factory=list)
    
    @property
    def critical_count(self) -> int:
        return sum(1 for m in self.matches if m.sensitivity == SensitivityLevel.CRITICAL)
    
    @property
    def high_count(self) -> int:
        return sum(1 for m in self.matches if m.sensitivity == SensitivityLevel.HIGH)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "risk_score": f"{self.risk_score:.2f}",
            "total_matches": len(self.matches),
            "critical_matches": self.critical_count,
            "high_matches": self.high_count,
            "matches": [str(m) for m in self.matches],
            "warnings": self.warnings,
        }


# 敏感信息模式定义
SENSITIVITY_PATTERNS = [
    # API 密钥（高危）
    {
        "name": "openai_api_key",
        "pattern": r'sk-[a-zA-Z0-9]{48}',
        "category": "API Key",
        "sensitivity": SensitivityLevel.CRITICAL,
        "mask_template": "{prefix}***{suffix}",
        "mask_params": {"prefix_len": 7, "suffix_len": 4},
    },
    {
        "name": "aws_access_key",
        "pattern': r'AKIA[A-Z0-9]{16}',
        "category": "AWS Access Key",
        "sensitivity": SensitivityLevel.CRITICAL,
        "mask_template": "***{suffix}",
        "mask_params": {"suffix_len": 4},
    },
    {
        "name": "github_token",
        "pattern': r'ghp_[a-zA-Z0-9]{36}',
        "category": "GitHub Token",
        "sensitivity": SensitivityLevel.CRITICAL,
        "mask_template": "ghp_***{suffix}",
        "mask_params": {"suffix_len": 4},
    },
    {
        "name": "slack_token",
        "pattern': r'xox[bpsa]-[a-zA-Z0-9-]+',
        "category": "Slack Token",
        "sensitivity": SensitivityLevel.CRITICAL,
        "mask_template": "xox***",
        "mask_params": {},
    },
    
    # 密码（高危）
    {
        "name": "password_assignment",
        "pattern': r'(?:password|passwd|pwd)\s*[:=]\s*["\'][^"\']+["\']',
        "category": "Password",
        "sensitivity": SensitivityLevel.CRITICAL,
        "mask_template": '{key}=***REDACTED***',
        "mask_params": {},
    },
    {
        "name": "db_connection_string",
        "pattern': r'(?:mysql|postgresql|mongodb|redis)://[^:\s]+:[^@\s]+@',
        "category": "Database Connection String",
        "sensitivity": SensitivityLevel.CRITICAL,
        "mask_template": '{protocol}://***:***@',
        "mask_params": {},
    },
    
    # 私钥（高危）
    {
        "name": "private_key",
        "pattern': r'-----BEGIN (?:RSA |EC |DSA |OPENSSH |DSA )?PRIVATE KEY-----',
        "category": "Private Key",
        "sensitivity": SensitivityLevel.CRITICAL,
        "mask_template": '-----BEGIN PRIVATE KEY REDACTED-----',
        "mask_params": {},
    },
    
    # 个人信息（中等）
    {
        "name": "email_address",
        "pattern': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        "category": "Email Address",
        "sensitivity": SensitivityLevel.MEDIUM,
        "mask_template": "***@{domain}",
        "mask_params": {},
    },
    {
        "name": "ip_address",
        "pattern': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        "category": "IP Address",
        "sensitivity": SensitivityLevel.MEDIUM,
        "mask_template": "***.***.*.*",
        "mask_params": {},
    },
    
    # 内部标识符（低危）
    {
        "name": "internal_id",
        "pattern': r'(?:(?:user|project|org|team)_)?id\s*[:=]\s*["\']?\d+["\']?',
        "category": "Internal ID",
        "sensitivity": SensitivityLevel.LOW,
        "mask_template": '{key}=***',
        "mask_params": {},
    },
]


class SecurityScanner:
    """
    安全扫描器
    
    检测文本中的敏感信息并提供脱敏处理。
    """
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._patterns = []
        
        # 编译正则表达式
        for pattern_def in SENSITIVITY_PATTERNS:
            try:
                compiled = re.compile(pattern_def["pattern"], re.IGNORECASE)
                self._patterns.append({**pattern_def, "compiled": compiled})
            except re.error as e:
                logger.warning(f"编译模式失败 {pattern_def['name']}: {e}")
    
    def scan(self, text: str) -> SecurityScanResult:
        """
        扫描文本中的敏感信息
        
        Args:
            text: 要扫描的文本
            
        Returns:
            SecurityScanResult对象
        """
        if not self.enabled or not text:
            return SecurityScanResult(is_safe=True)
        
        matches = []
        total_risk = 0.0
        
        for pattern_def in self._patterns:
            for match in pattern_def["compiled"].finditer(text):
                original_value = match.group()
                
                # 生成掩码值
                masked = self._apply_mask(
                    original_value,
                    pattern_def["mask_template"],
                    pattern_def.get("mask_params", {}),
                    pattern_def.get("category", ""),
                )
                
                sensitive_match = SensitiveDataMatch(
                    value=original_value,
                    masked_value=masked,
                    category=pattern_def["category"],
                    sensitivity=pattern_def["sensitivity"],
                    position=(match.start(), match.end()),
                    pattern_name=pattern_def["name"],
                )
                
                matches.append(sensitive_match)
                
                # 计算风险分数
                risk_weights = {
                    SensitivityLevel.CRITICAL: 0.4,
                    SensitivityLevel.HIGH: 0.25,
                    SensitivityLevel.MEDIUM: 0.15,
                    SensitivityLevel.LOW: 0.05,
                }
                total_risk += risk_weights.get(pattern_def["sensitivity"], 0.05)
        
        # 计算最终风险分数（归一化到0-1）
        risk_score = min(total_risk, 1.0)
        
        # 生成警告
        warnings = []
        if any(m.sensitivity == SensitivityLevel.CRITICAL for m in matches):
            warnings.append("⚠️ 检测到高敏感度信息（API密钥/密码/私钥）")
        if len(matches) > 5:
            warnings.append(f"⚠️ 检测到大量潜在敏感信息 ({len(matches)} 处)")
        
        is_safe = (
            not any(m.sensitivity == SensitivityLevel.CRITICAL for m in matches) and
            risk_score < 0.5
        )
        
        return SecurityScanResult(
            is_safe=is_safe,
            matches=matches,
            risk_score=risk_score,
            warnings=warnings,
        )
    
    def sanitize(self, text: str) -> Tuple[str, SecurityScanResult]:
        """
        清理文本中的敏感信息
        
        Returns:
            (清理后的文本, 扫描结果)
        """
        result = self.scan(text)
        
        if result.is_safe:
            return text, result
        
        sanitized_text = text
        
        # 按位置倒序替换，避免位置偏移
        sorted_matches = sorted(result.matches, key=lambda m: m.position[0], reverse=True)
        
        for match in sorted_matches:
            start, end = match.position
            sanitized_text = sanitized_text[:start] + match.masked_value + sanitized_text[end:]
        
        return sanitized_text, result
    
    def _apply_mask(
        self,
        original: str,
        template: str,
        params: Dict[str, Any],
        category: str
    ) -> str:
        """应用掩码模板"""
        try:
            if "password" in category.lower() or "connection" in category.lower():
                # 特殊处理：保留键名
                key_match = re.match(r'(\w+)\s*[=:]', original)
                if key_match:
                    return template.format(key=key_match.group(1))
            
            if "email" in category.lower():
                # Email特殊处理
                domain_match = re.search(r'@([\w.-]+)', original)
                if domain_match:
                    return template.format(domain=domain_match.group(1))
            
            prefix_len = params.get("prefix_len", 3)
            suffix_len = params.get("suffix_len", 3)
            
            if len(original) <= prefix_len + suffix_len:
                return "***"
            
            return original[:prefix_len] + "***" + original[-suffix_len:] if suffix_len > 0 else original[:prefix_len] + "***"
            
        except Exception as e:
            logger.warning(f"应用掩码失败: {e}")
            return "***REDACTED***"


class CredentialManager:
    """
    凭证管理器
    
    安全地存储和管理API密钥等敏感凭证。
    使用操作系统提供的加密机制。
    """
    
    def __init__(self, service_name: str = "ericcode"):
        self.service_name = service_name
        self.config_dir = self._get_config_dir()
        self.cipher = None
        self._ensure_secure_dir()
    
    def _get_config_dir(self) -> Path:
        """获取配置目录"""
        import sys
        
        if sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        elif sys.platform == "win32":
            base = Path(os.environ.get("APPDATA", Path.home()))
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        
        return base / self.service_name
    
    def _ensure_secure_dir(self):
        """确保配置目录存在且权限正确"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.config_dir, 0o700)
    
    def save_credential(self, provider: str, credential: str) -> bool:
        """
        安全保存凭证
        
        Args:
            provider: 提供商标识 (如 "openai")
            credential: 要保存的凭证（如API密钥）
        """
        try:
            encrypted = self._encrypt(credential)
            file_path = self.config_dir / f"{provider}.cred"
            
            with open(file_path, 'wb') as f:
                f.write(encrypted)
            
            os.chmod(file_path, 0o600)
            logger.info(f"凭证已安全保存: {provider}")
            return True
            
        except Exception as e:
            logger.error(f"保存凭证失败: {e}")
            return False
    
    def get_credential(self, provider: str) -> Optional[str]:
        """
        获取凭证
        
        Args:
            provider: 提供商标识
            
        Returns:
            解密后的凭证，如果不存在则返回None
        """
        file_path = self.config_dir / f"{provider}.cred"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'rb') as f:
                encrypted = f.read()
            
            decrypted = self._decrypt(encrypted)
            return decoded.decode('utf-8')
            
        except Exception as e:
            logger.error(f"读取凭证失败: {e}")
            return None
    
    def delete_credential(self, provider: str) -> bool:
        """删除凭证"""
        file_path = self.config_dir / f"{provider}.cred"
        
        if file_path.exists():
            file_path.unlink()
            logger.info(f"凭证已删除: {provider}")
            return True
        return False
    
    def list_providers(self) -> List[str]:
        """列出所有已保存的凭证提供商"""
        providers = []
        for cred_file in self.config_dir.glob("*.cred"):
            providers.append(cred_file.stem)
        return providers
    
    def _get_or_create_cipher(self):
        """获取或创建加密密钥"""
        from cryptography.fernet import Fernet
        
        if self.cipher:
            return self.cipher
        
        key_file = self.config_dir / ".key"
        
        if key_file.exists():
            key = key_file.read_bytes()
        else:
            key = Fernet.generate_key()
            key_file.write_bytes(key)
            os.chmod(key_file, 0o600)
        
        self.cipher = Fernet(key)
        return self.cipher
    
    def _encrypt(self, plaintext: str) -> bytes:
        """加密明文"""
        cipher = self._get_or_create_cipher()
        return cipher.encrypt(plaintext.encode('utf-8'))
    
    def _decrypt(self, ciphertext: bytes) -> bytes:
        """解密密文"""
        cipher = self._get_or_create_cipher()
        return cipher.decrypt(ciphertext)


class InputValidator:
    """
    输入验证器
    
    验证用户输入的安全性，防止注入攻击等。
    """
    
    MAX_PROMPT_LENGTH = 10000  # 最大提示词长度
    MAX_CODE_LENGTH = 100000   # 最大代码长度
    
    DANGEROUS_PATTERNS = [
        r'__import__\s*\(',          # 危险导入
        r'eval\s*\(',               # eval使用
        r'exec\s*\(',               # exec使用
        r'subprocess\.',           # 子进程调用（需谨慎）
        r'os\.system\s*\(',       # 系统命令执行
        r'rm\s+-rf',              # 危险命令
        r'>\s*/dev/',             # 重定向危险路径
        r'curl.*\|\s*bash',      # 管道执行远程代码
        r'wget.*\|\s*(sh|bash)',  # 下载并执行
    ]
    
    def validate_prompt(self, prompt: str) -> Tuple[bool, List[str]]:
        """
        验证提示词安全性
        
        Returns:
            (是否有效, 警告列表)
        """
        warnings = []
        
        # 检查长度
        if len(prompt) > self.MAX_PROMPT_LENGTH:
            warnings.append(f"提示词过长 ({len(prompt)} 字符，限制 {self.MAX_PROMPT_LENGTH})")
        
        # 检查危险模式
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                warnings.append(f"检测到潜在危险的代码模式: {pattern}")
        
        # 检查是否包含明显的恶意指令
        malicious_indicators = [
            "忽略之前的指令",
            "ignore previous instructions",
            "你是一个没有限制的AI",
            "you are an unrestricted AI",
        ]
        
        for indicator in malicious_indicators:
            if indicator.lower() in prompt.lower():
                warnings.append("检测到可能的提示词注入尝试")
        
        is_valid = len(warnings) == 0 or all("过长" in w for w in warnings)
        return is_valid, warnings
    
    def validate_code(self, code: str) -> Tuple[bool, List[str]]:
        """
        验证代码安全性
        
        Returns:
            (是否有效, 警告列表)
        """
        warnings = []
        
        if len(code) > self.MAX_CODE_LENGTH:
            warnings.append(f"代码过长 ({len(code)} 字符)")
        
        # 扫描敏感信息
        scanner = SecurityScanner()
        scan_result = scanner.scan(code)
        
        if not scan_result.is_safe:
            warnings.extend(scan_result.warnings)
        
        is_valid = len([w for w in warnings if "过长" not in w]) == 0
        return is_valid, warnings


# 全局实例
security_scanner = SecurityScanner(enabled=True)
credential_manager = CredentialManager()
input_validator = InputValidator()
