"""
EricCode Secret Scrubber

自动识别并抹除文本中的敏感信息

功能：
- 识别密码、API密钥、IP地址等敏感信息
- 智能脱敏处理
- 支持从文件或标准输入读取内容
- 支持输出到文件或标准输出
- 可配置脱敏规则
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Pattern

logger = logging.getLogger(__name__)


@dataclass
class ScrubResult:
    """脱敏结果"""
    scrubbed_text: str  # 脱敏后的文本
    detected_secrets: List[Dict[str, str]]  # 检测到的敏感信息列表
    scrub_count: int  # 脱敏的数量


class SecretScrubber:
    """
    敏感信息清洗器
    
    自动识别并抹除文本中的敏感信息
    """
    
    def __init__(self):
        self._patterns = {
            "api_key": re.compile(r"(api[_\s-]?key|api[_\s-]?secret)[:\s]+([a-zA-Z0-9_\-]{30,})", re.IGNORECASE),
            "password": re.compile(r"(password|pwd)[:\s]+([a-zA-Z0-9_\-!@#$%^&*]{6,})", re.IGNORECASE),
            "token": re.compile(r"(token|jwt|bearer)[:\s]+([a-zA-Z0-9_\-\.]{20,})", re.IGNORECASE),
            "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
            "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
            "social_security": re.compile(r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b"),
            "phone_number": re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b"),
        }
    
    def scrub(self, text: str, rules: Optional[List[str]] = None) -> ScrubResult:
        """
        清洗文本中的敏感信息
        
        Args:
            text: 要清洗的文本
            rules: 要应用的规则列表，None表示使用所有规则
            
        Returns:
            ScrubResult对象
        """
        scrubbed_text = text
        detected_secrets = []
        scrub_count = 0
        
        # 确定要使用的规则
        active_patterns = {}
        if rules:
            for rule in rules:
                if rule in self._patterns:
                    active_patterns[rule] = self._patterns[rule]
        else:
            active_patterns = self._patterns
        
        # 应用每个规则
        for rule_name, pattern in active_patterns.items():
            for match in pattern.finditer(scrubbed_text):
                detected_secrets.append({
                    "type": rule_name,
                    "value": match.group(0),
                })
                scrub_count += 1
                
                # 替换敏感信息
                if rule_name == "ip_address":
                    # IP地址替换为掩码
                    scrubbed_text = scrubbed_text.replace(match.group(0), "***.***.***.***")
                elif rule_name == "email":
                    # 邮箱替换为掩码
                    email = match.group(0)
                    local, domain = email.split("@")
                    masked_local = local[0] + "*" * (len(local) - 1) if len(local) > 1 else "*"
                    masked_email = f"{masked_local}@{domain}"
                    scrubbed_text = scrubbed_text.replace(email, masked_email)
                else:
                    # 其他敏感信息替换为星号
                    scrubbed_text = scrubbed_text.replace(match.group(0), "***[REDACTED]***")
        
        return ScrubResult(
            scrubbed_text=scrubbed_text,
            detected_secrets=detected_secrets,
            scrub_count=scrub_count,
        )
    
    def scrub_file(self, input_path: Path, output_path: Optional[Path] = None, rules: Optional[List[str]] = None) -> ScrubResult:
        """
        清洗文件中的敏感信息
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径，None表示覆盖原文件
            rules: 要应用的规则列表
            
        Returns:
            ScrubResult对象
        """
        # 读取文件
        text = input_path.read_text(encoding="utf-8")
        
        # 清洗
        result = self.scrub(text, rules)
        
        # 写入输出
        output = output_path or input_path
        output.write_text(result.scrubbed_text, encoding="utf-8")
        
        return result
    
    def add_pattern(self, name: str, pattern: Pattern[str]):
        """
        添加自定义脱敏规则
        
        Args:
            name: 规则名称
            pattern: 正则表达式模式
        """
        self._patterns[name] = pattern
    
    def remove_pattern(self, name: str):
        """
        移除脱敏规则
        
        Args:
            name: 规则名称
        """
        if name in self._patterns:
            del self._patterns[name]
    
    def list_patterns(self) -> List[str]:
        """
        列出所有可用的脱敏规则
        
        Returns:
            规则名称列表
        """
        return list(self._patterns.keys())


def scrub_text(text: str, rules: Optional[List[str]] = None) -> ScrubResult:
    """
    清洗文本中的敏感信息的便捷函数
    
    Args:
        text: 要清洗的文本
        rules: 要应用的规则列表
        
    Returns:
        ScrubResult对象
    """
    scrubber = SecretScrubber()
    return scrubber.scrub(text, rules)


def scrub_file(input_path: str, output_path: Optional[str] = None, rules: Optional[List[str]] = None) -> ScrubResult:
    """
    清洗文件中的敏感信息的便捷函数
    
    Args:
        input_path: 输入文件路径
        output_path: 输出文件路径
        rules: 要应用的规则列表
        
    Returns:
        ScrubResult对象
    """
    scrubber = SecretScrubber()
    return scrubber.scrub_file(Path(input_path), Path(output_path) if output_path else None, rules)
