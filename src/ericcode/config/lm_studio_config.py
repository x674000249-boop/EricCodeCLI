"""
LM Studio 配置管理模块

自动检测和配置LM Studio

功能：
- 自动检测LM Studio状态
- 自动配置OpenAI兼容API
- 管理LM Studio的启动和停止
- 提供配置建议
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from .settings import settings
from ..providers.lm_studio import get_lm_studio_integration

logger = logging.getLogger(__name__)


class LMStudioConfigManager:
    """
    LM Studio配置管理器
    
    负责自动检测和配置LM Studio
    """
    
    def __init__(self):
        self._integration = get_lm_studio_integration()
    
    def auto_configure(self) -> bool:
        """
        自动配置LM Studio
        
        Returns:
            是否配置成功
        """
        try:
            # 检查LM Studio是否运行
            status = self._integration.check_status()
            
            if not status.is_running:
                # 尝试打开LM Studio
                logger.info("LM Studio未运行，尝试打开...")
                success = self._integration.open_lm_studio()
                if not success:
                    logger.error("无法打开LM Studio")
                    return False
                
                # 等待LM Studio启动
                logger.info("等待LM Studio启动...")
                if not self._integration.wait_for_startup():
                    logger.error("LM Studio启动超时")
                    return False
            
            # 配置OpenAI设置
            config = self._integration.get_api_config()
            self._update_openai_config(config)
            
            logger.info("LM Studio配置成功")
            return True
            
        except Exception as e:
            logger.error(f"自动配置LM Studio失败: {e}")
            return False
    
    def _update_openai_config(self, config: dict):
        """
        更新OpenAI配置
        
        Args:
            config: LM Studio API配置
        """
        # 检查环境变量是否已设置
        if not os.environ.get("ERICCODE_OPENAI_API_KEY"):
            os.environ["ERICCODE_OPENAI_API_KEY"] = config["api_key"]
        
        if not os.environ.get("ERICCODE_OPENAI_BASE_URL"):
            os.environ["ERICCODE_OPENAI_BASE_URL"] = config["base_url"]
        
        if not os.environ.get("ERICCODE_OPENAI_DEFAULT_MODEL"):
            os.environ["ERICCODE_OPENAI_DEFAULT_MODEL"] = config["default_model"]
        
        # 重新加载设置
        global settings
        settings = settings.__class__()
    
    def create_env_file(self, path: Optional[Path] = None) -> bool:
        """
        创建.env文件
        
        Args:
            path: 文件路径，默认为当前目录
            
        Returns:
            是否创建成功
        """
        try:
            # 获取配置
            config = self._integration.get_api_config()
            
            # 确定文件路径
            if not path:
                path = Path(".env")
            
            # 写入配置
            content = f"""
# EricCode 配置文件
# LM Studio API 配置
ERICCODE_OPENAI_API_KEY={config['api_key']}
ERICCODE_OPENAI_BASE_URL={config['base_url']}
ERICCODE_OPENAI_DEFAULT_MODEL={config['default_model']}

# 其他配置
ERICCODE_LOG_LEVEL=INFO
ERICCODE_UI_THEME=dark
"""
            
            path.write_text(content.strip(), encoding="utf-8")
            logger.info(f"已创建.env文件: {path}")
            return True
            
        except Exception as e:
            logger.error(f"创建.env文件失败: {e}")
            return False
    
    def check_compatibility(self) -> dict:
        """
        检查兼容性
        
        Returns:
            兼容性检查结果
        """
        result = {
            "lm_studio_running": False,
            "api_available": False,
            "model_loaded": False,
            "compatible": False,
            "issues": [],
        }
        
        try:
            # 检查LM Studio状态
            status = self._integration.check_status()
            result["lm_studio_running"] = status.is_running
            
            if status.is_running:
                result["api_available"] = True
                result["model_loaded"] = status.model is not None
                result["compatible"] = True
            else:
                result["issues"].append("LM Studio未运行")
                
        except Exception as e:
            result["issues"].append(f"检查失败: {e}")
        
        return result
    
    def get_recommendations(self) -> list[str]:
        """
        获取配置建议
        
        Returns:
            建议列表
        """
        recommendations = []
        
        # 检查LM Studio状态
        status = self._integration.check_status()
        
        if not status.is_running:
            recommendations.append("请启动LM Studio并启用OpenAI兼容API")
        
        if not status.model:
            recommendations.append("请在LM Studio中加载一个代码模型")
        
        # 检查OpenAI配置
        if not settings.openai.api_key:
            recommendations.append("请设置ERICCODE_OPENAI_API_KEY环境变量")
        
        if not settings.openai.base_url:
            recommendations.append("请设置ERICCODE_OPENAI_BASE_URL环境变量")
        
        return recommendations


def get_lm_studio_config_manager() -> LMStudioConfigManager:
    """
    获取LM Studio配置管理器实例
    
    Returns:
        LMStudioConfigManager实例
    """
    return LMStudioConfigManager()


def auto_configure_lm_studio() -> bool:
    """
    自动配置LM Studio的便捷函数
    
    Returns:
        是否配置成功
    """
    manager = get_lm_studio_config_manager()
    return manager.auto_configure()


def create_lm_studio_env_file(path: Optional[str] = None) -> bool:
    """
    创建LM Studio配置文件的便捷函数
    
    Args:
        path: 文件路径
        
    Returns:
        是否创建成功
    """
    manager = get_lm_studio_config_manager()
    return manager.create_env_file(Path(path) if path else None)
