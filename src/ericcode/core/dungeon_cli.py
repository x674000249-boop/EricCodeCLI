"""
EricCode Dungeon CLI

终端文字冒险游戏

功能：
- 完全基于文本的冒险体验
- 无限创意内容生成
- 支持自然语言交互
- 多种游戏场景和角色
- 保存和加载游戏进度
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..providers.base import (
    GenerationOptions,
    Message,
    MessageRole,
    ModelResponse,
)
from ..providers.router import get_model_router

logger = logging.getLogger(__name__)


@dataclass
class GameState:
    """游戏状态"""
    player_name: str
    location: str
    inventory: List[str] = field(default_factory=list)
    health: int = 100
    mana: int = 50
    score: int = 0
    game_history: List[str] = field(default_factory=list)
    current_scenario: str = ""


class DungeonCLI:
    """
    终端文字冒险游戏
    
    基于AI生成的无限创意内容
    """
    
    def __init__(self, save_path: Optional[Path] = None):
        self._router = get_model_router()
        self._save_path = save_path or Path.home() / ".ericcode" / "dungeon_save.json"
        self._game_state = None
    
    def start_new_game(self, player_name: str) -> str:
        """
        开始新游戏
        
        Args:
            player_name: 玩家名称
            
        Returns:
            游戏开始场景描述
        """
        # 初始化游戏状态
        self._game_state = GameState(
            player_name=player_name,
            location="神秘洞穴入口",
            inventory=["火把", "小刀"],
        )
        
        # 生成初始场景
        initial_scenario = self._generate_initial_scenario()
        self._game_state.current_scenario = initial_scenario
        self._game_state.game_history.append(f"游戏开始：{initial_scenario}")
        
        # 保存游戏
        self._save_game()
        
        return initial_scenario
    
    def load_game(self) -> Optional[GameState]:
        """
        加载游戏
        
        Returns:
            游戏状态，None表示加载失败
        """
        if self._save_path.exists():
            try:
                with open(self._save_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                self._game_state = GameState(
                    player_name=data["player_name"],
                    location=data["location"],
                    inventory=data["inventory"],
                    health=data["health"],
                    mana=data["mana"],
                    score=data["score"],
                    game_history=data["game_history"],
                    current_scenario=data["current_scenario"],
                )
                
                return self._game_state
            except Exception as e:
                logger.error(f"加载游戏失败: {e}")
        
        return None
    
    def _save_game(self):
        """
        保存游戏
        """
        if self._game_state:
            try:
                # 确保目录存在
                self._save_path.parent.mkdir(parents=True, exist_ok=True)
                
                data = {
                    "player_name": self._game_state.player_name,
                    "location": self._game_state.location,
                    "inventory": self._game_state.inventory,
                    "health": self._game_state.health,
                    "mana": self._game_state.mana,
                    "score": self._game_state.score,
                    "game_history": self._game_state.game_history,
                    "current_scenario": self._game_state.current_scenario,
                }
                
                with open(self._save_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"保存游戏失败: {e}")
    
    def _generate_initial_scenario(self) -> str:
        """
        生成初始场景
        
        Returns:
            场景描述
        """
        system_prompt = """
你是一个专业的文字冒险游戏设计师，擅长创建引人入胜的游戏场景和故事。

任务：
- 为一个新的文字冒险游戏生成初始场景
- 场景应该是一个神秘的洞穴入口
- 描述环境、氛围和可能的互动选项
- 保持描述生动有趣，激发玩家的探索欲望
- 不要添加任何游戏机制的解释，只描述场景

输出格式：
仅输出场景描述，不要包含其他内容。
        """
        
        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
        ]
        
        response, _ = self._router.route(
            messages,
            GenerationOptions(temperature=0.7, max_tokens=500),
        )
        
        return response.content.strip()
    
    async def process_action(self, action: str) -> str:
        """
        处理玩家动作
        
        Args:
            action: 玩家输入的动作
            
        Returns:
            动作结果描述
        """
        if not self._game_state:
            return "游戏尚未开始，请先开始新游戏。"
        
        # 构建系统提示词
        system_prompt = f"""
你是一个专业的文字冒险游戏设计师，负责处理玩家的动作并生成游戏世界的响应。

当前游戏状态：
- 玩家名称: {self._game_state.player_name}
- 当前位置: {self._game_state.location}
- 物品栏: {', '.join(self._game_state.inventory) if self._game_state.inventory else '空'}
- 生命值: {self._game_state.health}
- 魔法值: {self._game_state.mana}
- 当前场景: {self._game_state.current_scenario}

任务：
- 分析玩家的动作：{action}
- 生成合理的游戏响应
- 保持游戏世界的一致性
- 描述动作的结果和新的游戏状态
- 提供新的互动选项
- 保持描述生动有趣

输出格式：
仅输出动作结果描述，不要包含其他内容。
        """
        
        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=action),
        ]
        
        response, _ = await self._router.route(
            messages,
            GenerationOptions(temperature=0.7, max_tokens=800),
        )
        
        result = response.content.strip()
        
        # 更新游戏状态
        self._game_state.game_history.append(f"你: {action}")
        self._game_state.game_history.append(f"游戏: {result}")
        
        # 随机更新一些游戏状态
        if random.random() < 0.3:
            # 随机获得物品
            items = ["金币", "药水", "钥匙", "宝石"]
            new_item = random.choice(items)
            if new_item not in self._game_state.inventory:
                self._game_state.inventory.append(new_item)
                result += f"\n\n你发现了一个 {new_item}，已添加到物品栏。"
        
        if random.random() < 0.1:
            # 随机受伤
            damage = random.randint(5, 20)
            self._game_state.health = max(0, self._game_state.health - damage)
            result += f"\n\n你受到了 {damage} 点伤害！"
        
        # 增加分数
        self._game_state.score += 10
        
        # 保存游戏
        self._save_game()
        
        return result
    
    def get_game_status(self) -> str:
        """
        获取游戏状态
        
        Returns:
            游戏状态描述
        """
        if not self._game_state:
            return "游戏尚未开始"
        
        status = f"""
=== 游戏状态 ===
玩家: {self._game_state.player_name}
位置: {self._game_state.location}
生命值: {self._game_state.health}/100
魔法值: {self._game_state.mana}/50
分数: {self._game_state.score}
物品栏: {', '.join(self._game_state.inventory) if self._game_state.inventory else '空'}
当前场景: {self._game_state.current_scenario[:100]}...
=== 游戏状态 ===
        """
        
        return status
    
    def quit_game(self):
        """
        退出游戏
        """
        self._save_game()
        self._game_state = None
        return "游戏已保存，再见！"


def start_game(player_name: str, save_path: Optional[str] = None) -> DungeonCLI:
    """
    开始新游戏
    
    Args:
        player_name: 玩家名称
        save_path: 保存路径
        
    Returns:
        DungeonCLI实例
    """
    game = DungeonCLI(Path(save_path) if save_path else None)
    initial_scenario = game.start_new_game(player_name)
    return game


def load_saved_game(save_path: Optional[str] = None) -> Optional[DungeonCLI]:
    """
    加载保存的游戏
    
    Args:
        save_path: 保存路径
        
    Returns:
        DungeonCLI实例，None表示加载失败
    """
    game = DungeonCLI(Path(save_path) if save_path else None)
    if game.load_game():
        return game
    return None
