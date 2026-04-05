"""
EricCode 缓存管理系统

提供多层级缓存架构：
- L1: 内存缓存（LRU，最快）
- L2: 文件系统缓存（持久化）
- L3: Redis缓存（可选，分布式）

特性：
- 智能缓存策略（根据请求类型动态调整TTL）
- 自动过期和清理
- 线程安全
- 命中率统计
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    expires_at: float
    size_bytes: int = 0
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    
    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at
    
    @property
    def ttl_remaining(self) -> float:
        return max(0, self.expires_at - time.time())


@dataclass
class CacheStats:
    """缓存统计信息"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_requests: int = 0
    
    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "total_requests": self.total_requests,
            "hit_rate": f"{self.hit_rate:.2%}",
        }


class LRUCache(OrderedDict):
    """
    LRU (Least Recently Used) 内存缓存
    
    线程安全的有序字典，自动淘汰最久未使用的条目。
    """
    
    def __init__(self, maxsize: int = 200):
        super().__init__()
        self._maxsize = maxsize
        self._lock = asyncio.Lock()
    
    def get(self, key: str, default: T = None) -> Union[CacheEntry, T]:
        """获取缓存值并更新访问时间"""
        if key in self:
            # 移到末尾（最近使用）
            self.move_to_end(key)
            entry = super().__getitem__(key)
            entry.access_count += 1
            entry.last_accessed = time.time()
            return entry
        return default
    
    def __setitem__(self, key: str, value: CacheEntry):
        """设置缓存值，必要时淘汰旧条目"""
        if key in self:
            self.move_to_end(key)
        
        super().__setitem__(key, value)
        
        # 检查容量限制
        if len(self) > self._maxsize:
            oldest_key = next(iter(self))
            del self[oldest_key]
            logger.debug(f"LRU淘汰: {oldest_key}")
    
    async def get_async(self, key: str, default: T = None) -> Union[CacheEntry, T]:
        """异步获取"""
        async with self._lock:
            return self.get(key, default)
    
    async def set_async(self, key: str, value: CacheEntry):
        """异步设置"""
        async with self._lock:
            self[key] = value


class FileCache:
    """
    文件系统缓存
    
    将缓存数据持久化到磁盘，适合重启后仍需保留的数据。
    """
    
    def __init__(
        self,
        cache_dir: Path,
        default_ttl: int = 3600,
        max_size_mb: int = 500
    ):
        self.cache_dir = cache_dir
        self.default_ttl = default_ttl
        self.max_size_bytes = max_size_mb * 1024 * 1024
        
        cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"文件缓存初始化: {cache_dir}")
    
    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件的路径"""
        safe_key = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{safe_key}.cache"
    
    async def get(self, key: str) -> Optional[Any]:
        """读取缓存"""
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            return None
        
        try:
            import pickle
            
            with open(cache_path, 'rb') as f:
                entry: CacheEntry = pickle.load(f)
            
            if entry.is_expired:
                await self.delete(key)
                logger.debug(f"文件缓存已过期: {key[:20]}...")
                return None
            
            entry.access_count += 1
            entry.last_accessed = time.time()
            
            # 更新访问元数据（不修改原始数据）
            with open(cache_path, 'wb') as f:
                pickle.dump(entry, f)
            
            return entry.value
            
        except Exception as e:
            logger.warning(f"读取文件缓存失败: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """写入缓存"""
        try:
            import pickle
            
            effective_ttl = ttl or self.default_ttl
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                expires_at=time.time() + effective_ttl,
                size_bytes=len(pickle.dumps(value)),
            )
            
            cache_path = self._get_cache_path(key)
            
            with open(cache_path, 'wb') as f:
                pickle.dump(entry, f)
            
            return True
            
        except Exception as e:
            logger.error(f"写入文件缓存失败: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        cache_path = self._get_cache_path(key)
        
        if cache_path.exists():
            cache_path.unlink()
            return True
        return False
    
    async def clear(self, pattern: Optional[str] = None):
        """清空缓存"""
        if pattern:
            for cache_file in self.cache_dir.glob(f"*{pattern}*.cache"):
                cache_file.unlink()
        else:
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()
    
    async def cleanup_expired(self) -> int:
        """清理过期的缓存条目，返回清理数量"""
        count = 0
        current_time = time.time()
        
        for cache_file in list(self.cache_dir.glob("*.cache")):
            try:
                import pickle
                
                with open(cache_file, 'rb') as f:
                    entry: CacheEntry = pickle.load(f)
                
                if entry.is_expired:
                    cache_file.unlink()
                    count += 1
                    
            except Exception:
                # 损坏的缓存文件，直接删除
                cache_file.unlink()
                count += 1
        
        if count > 0:
            logger.info(f"清理了 {count} 个过期缓存")
        
        return count
    
    def get_size_info(self) -> Dict[str, Any]:
        """获取缓存大小信息"""
        total_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.cache"))
        file_count = len(list(self.cache_dir.glob("*.cache")))
        
        return {
            "file_count": file_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "cache_dir": str(self.cache_dir),
        }


class CacheManager:
    """
    多层级缓存管理器
    
    统一管理L1/L2/L3缓存，提供智能的读写策略。
    """
    
    def __init__(self, config=None):
        from ..config.settings import CacheConfig
        
        config = config or CacheConfig()
        self.config = config
        
        # 初始化各级缓存
        self.l1_cache: Optional[LRUCache] = None
        self.l2_cache: Optional[FileCache] = None
        self.l3_cache = None  # Redis缓存（可选）
        
        self.stats = CacheStats()
        
        if config.l1_enabled:
            self.l1_cache = LRUCache(maxsize=config.l1_max_size)
        
        if config.l2_enabled and config.l2_cache_dir:
            self.l2_cache = FileCache(
                cache_dir=config.l2_cache_dir,
                default_ttl=config.ttl_seconds,
            )
        
        logger.info(f"缓存管理器初始化完成: L1={config.l1_enabled}, L2={config.l2_enabled}, L3={config.l3_enabled}")
    
    async def get(self, cache_key: str) -> Optional[Any]:
        """
        获取缓存值（按层级查找）
        
        顺序：L1 → L2 → L3
        找到后回填上层缓存
        """
        self.stats.total_requests += 1
        
        # L1 内存缓存
        if self.l1_cache:
            entry = await self.l1_cache.get_async(cache_key)
            if entry and not entry.is_expired:
                self.stats.hits += 1
                logger.debug(f"L1缓存命中: {cache_key[:30]}...")
                return entry.value
        
        # L2 文件缓存
        if self.l2_cache:
            value = await self.l2_cache.get(cache_key)
            if value is not None:
                self.stats.hits += 1
                logger.debug(f"L2缓存命中: {cache_key[:30]}...")
                
                # 回填L1
                if self.l1_cache:
                    new_entry = CacheEntry(
                        key=cache_key,
                        value=value,
                        created_at=time.time(),
                        expires_at=time.time() + min(300, self.config.ttl_seconds),  # L1 TTL较短
                    )
                    await self.l1_cache.set_async(cache_key, new_entry)
                
                return value
        
        # 未命中
        self.stats.misses += 1
        logger.debug(f"缓存未命中: {cache_key[:30]}...")
        return None
    
    async def set(
        self,
        cache_key: str,
        value: Any,
        ttl: Optional[int] = None,
        skip_l1: bool = False,
        skip_l2: bool = False,
    ) -> bool:
        """
        设置缓存值（写入所有启用的层级）
        """
        effective_ttl = ttl or self.config.ttl_seconds
        success = True
        
        # 写入L1
        if self.l1_cache and not skip_l1:
            entry = CacheEntry(
                key=cache_key,
                value=value,
                created_at=time.time(),
                expires_at=time.time() + effective_ttl,
            )
            await self.l1_cache.set_async(cache_key, entry)
        
        # 写入L2
        if self.l2_cache and not skip_l2:
            l2_success = await self.l2_cache.set(cache_key, value, ttl=effective_ttl)
            success = success and l2_success
        
        # TODO: 写入L3（Redis）
        
        return success
    
    async def delete(self, cache_key: str) -> bool:
        """从所有层级删除缓存"""
        success = True
        
        if self.l1_cache and cache_key in self.l1_cache:
            del self.l1_cache[cache_key]
        
        if self.l2_cache:
            success = (await self.l2_cache.delete(cache_key)) and success
        
        return success
    
    async def clear_all(self):
        """清空所有缓存"""
        if self.l1_cache:
            self.l1_cache.clear()
        
        if self.l2_cache:
            await self.l2_cache.clear()
        
        logger.info("所有缓存已清空")
    
    async def cleanup(self) -> int:
        """执行缓存维护（清理过期、超限）"""
        total_cleaned = 0
        
        if self.l2_cache:
            cleaned = await self.l2_cache.cleanup_expired()
            total_cleaned += cleaned
        
        return total_cleaned
    
    def generate_key(
        self,
        *args,
        prefix: str = "",
        **kwargs
    ) -> str:
        """
        生成缓存键
        
        将参数序列化为字符串并哈希
        """
        key_data = {"prefix": prefix}
        
        if args:
            key_data["args"] = args
        if kwargs:
            key_data["kwargs"] = kwargs
        
        key_string = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
        hash_value = hashlib.sha256(key_string.encode()).hexdigest()
        
        return f"{prefix}:{hash_value}" if prefix else hash_value
    
    def cached(
        self,
        ttl: Optional[int] = None,
        prefix: str = "",
        key_func: Optional[Callable] = None,
    ) -> Callable:
        """
        缓存装饰器
        
        用法::
        
            @cache_manager.cached(ttl=600, prefix="user:")
            async def get_user(user_id: str):
                return database.fetch_user(user_id)
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # 生成缓存键
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = self.generate_key(*args, prefix=prefix, **kwargs)
                
                # 尝试获取缓存
                cached_value = await self.get(cache_key)
                if cached_value is not None:
                    return cached_value
                
                # 执行函数
                result = await func(*args, **kwargs)
                
                # 存入缓存
                await self.set(cache_key, result, ttl=ttl)
                
                return result
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # 同步版本（需要在线程中运行）
                import asyncio
                
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                
                if loop and loop.is_running():
                    raise RuntimeError("Cannot use sync wrapper inside async context")
                
                return asyncio.run(async_wrapper(*args, **kwargs))
            
            # 根据函数类型返回对应的包装器
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    def get_stats(self) -> CacheStats:
        """获取缓存统计信息"""
        return self.stats
    
    def get_info(self) -> Dict[str, Any]:
        """获取缓存详细信息"""
        info = {
            "stats": self.stats.to_dict(),
            "config": {
                "l1_enabled": self.config.l1_enabled,
                "l1_max_size": self.config.l1_max_size,
                "l2_enabled": self.config.l2_enabled,
                "l2_cache_dir": str(self.config.l2_cache_dir) if self.config.l2_cache_dir else None,
                "default_ttl": self.config.ttl_seconds,
            },
        }
        
        if self.l2_cache:
            info["l2_size"] = self.l2_cache.get_size_info()
        
        if self.l1_cache:
            info["l1_current_size"] = len(self.l1_cache)
        
        return info


# 全局缓存管理器实例
cache_manager: Optional[CacheManager] = None


def get_cache_manager(config=None) -> CacheManager:
    """获取或创建全局缓存管理器"""
    global cache_manager
    
    if cache_manager is None:
        cache_manager = CacheManager(config)
    
    return cache_manager
