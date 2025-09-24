#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
远程配置服务

从MySQL数据库获取配置信息，替代本地config.json文件
项目启动时获取配置并缓存到内存中供后续使用
"""

import json
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pymysql.cursors


class RemoteConfigService:
    """远程配置服务"""
    
    # 硬编码的数据库连接信息
    DB_CONFIG = {
        'host': '106.14.82.245',
        'port': 3326,
        'username': 'root', 
        'password': '123456zw',
        'database': 'warp',
        'charset': 'utf8mb4'
    }
    
    # 配置缓存有效期（分钟）
    CACHE_EXPIRY_MINUTES = 30
    
    def __init__(self):
        """初始化远程配置服务"""
        self._config_cache: Dict[str, Any] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._connection = None
    
    def _get_connection(self):
        """获取数据库连接"""
        if self._connection is None or not self._connection.open:
            try:
                self._connection = pymysql.connect(
                    host=self.DB_CONFIG['host'],
                    port=self.DB_CONFIG['port'],
                    user=self.DB_CONFIG['username'],
                    password=self.DB_CONFIG['password'],
                    database=self.DB_CONFIG['database'],
                    charset=self.DB_CONFIG['charset'],
                    cursorclass=pymysql.cursors.DictCursor,
                    autocommit=True
                )
            except Exception as e:
                print(f"❌ 连接远程配置数据库失败: {e}")
                return None
        return self._connection
    
    def _is_cache_expired(self) -> bool:
        """检查缓存是否过期"""
        if self._cache_timestamp is None:
            return True
        return datetime.now() - self._cache_timestamp > timedelta(minutes=self.CACHE_EXPIRY_MINUTES)
    
    def _fetch_config_from_db(self) -> Dict[str, Any]:
        """从数据库获取配置"""
        conn = self._get_connection()
        if not conn:
            return self._get_fallback_config()
        
        try:
            with conn.cursor() as cursor:
                # 获取系统配置
                cursor.execute("SELECT config_key, config_value, config_type FROM warp_configs WHERE is_active = 1")
                configs = cursor.fetchall()
                
                config_dict = {}
                for config in configs:
                    key = config['config_key']
                    value = config['config_value']
                    config_type = config['config_type']
                    
                    # 根据类型转换值
                    if config_type == 'json':
                        try:
                            value = json.loads(value)
                        except:
                            pass
                    elif config_type == 'int':
                        try:
                            value = int(value)
                        except:
                            pass
                    elif config_type == 'bool':
                        value = str(value).lower() in ('true', '1', 'yes', 'on')
                    
                    # 支持嵌套配置键
                    keys = key.split('.')
                    current = config_dict
                    for k in keys[:-1]:
                        if k not in current:
                            current[k] = {}
                        current = current[k]
                    current[keys[-1]] = value
                
                # 🔧 配置后处理：将扁平化配置转换为嵌套结构以兼容现有代码
                processed_config = self._process_config_structure(config_dict)
                return processed_config
                
        except Exception as e:
            print(f"❌ 从数据库获取配置失败: {e}")
            return self._get_fallback_config()
    
    def _process_config_structure(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理配置结构，将扁平化配置转换为嵌套结构以兼容现有代码
        
        Args:
            config_dict: 从数据库获取的扁平化配置
            
        Returns:
            处理后的配置字典
        """
        processed = config_dict.copy()
        
        # 构建 moemail 嵌套结构
        if 'moemail_url' in processed and 'api_key' in processed:
            processed['moemail'] = {
                'base_url': processed['moemail_url'],
                'api_key': processed['api_key']
            }
            print(f"✅ 构建moemail配置: {processed['moemail']}")
        
        # 确保数据库配置结构正确
        # 检查并构建完整的数据库配置结构
        if 'database' in processed:
            # 如果已有database配置，确保包含mysql_config
            if 'mysql_config' not in processed['database']:
                processed['database']['mysql_config'] = {
                    'mysql': self.DB_CONFIG
                }
                print("✅ 添加mysql_config到现有database配置")
        else:
            # 如果没有database配置，创建完整结构
            processed['database'] = {
                "enable_mysql": True,
                "mysql_config": {
                    "mysql": self.DB_CONFIG
                }
            }
            print("✅ 创建完整数据库配置结构")
        
        return processed
    
    def _get_fallback_config(self) -> Dict[str, Any]:
        """获取后备配置（硬编码的默认配置）"""
        return {
            "api_key": "mk_IpnNUYb8KgdCTJLokCgAthP7OVirjIqX",
            "register_url": "https://app.warp.dev",
            "login_url": "https://app.warp.dev/login",
            "email_prefix": "zB3w3SQB",
            "email_expiry_hours": 1,
            "auto_refresh": True,
            "check_interval": 5,
            "max_wait_time": 300,
            "firebase_api_keys": [
                "AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs"
            ],
            "firebase_api_key": "AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs",
            # 添加 moemail 嵌套配置结构，匹配GUI代码的期望
            "moemail": {
                "base_url": "https://rsgdfb.filegear-sg.me",
                "api_key": "mk_IpnNUYb8KgdCTJLokCgAthP7OVirjIqX"
            },
            # 保留扁平化的配置作为兼容性
            "moemail_url": "https://rsgdfb.filegear-sg.me",
            "database": {
                "enable_mysql": True,
                "mysql_config": {
                    "mysql": self.DB_CONFIG
                }
            },
            "backup_restore": {
                "enabled": True
            }
        }
    
    def get_config(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        获取配置信息
        
        Args:
            force_refresh: 是否强制从数据库重新获取
            
        Returns:
            Dict[str, Any]: 配置字典
        """
        # 如果缓存有效且不强制刷新，返回缓存
        if not force_refresh and not self._is_cache_expired() and self._config_cache:
            return self._config_cache
        
        # 从数据库获取新配置
        config = self._fetch_config_from_db()
        
        # 更新缓存
        self._config_cache = config
        self._cache_timestamp = datetime.now()
        
        return config
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        获取指定配置值
        
        Args:
            key: 配置键，支持点号分隔的嵌套键
            default: 默认值
            
        Returns:
            Any: 配置值
        """
        config = self.get_config()
        
        # 支持嵌套键
        keys = key.split('.')
        value = config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def refresh_config(self) -> bool:
        """
        刷新配置缓存
        
        Returns:
            bool: 刷新成功返回True
        """
        try:
            self.get_config(force_refresh=True)
            print("✅ 远程配置刷新成功")
            return True
        except Exception as e:
            print(f"❌ 远程配置刷新失败: {e}")
            return False
    
    def close(self):
        """关闭数据库连接"""
        if self._connection:
            self._connection.close()
            self._connection = None


# 全局远程配置服务实例
_global_remote_config_service = None


def get_remote_config_service() -> RemoteConfigService:
    """获取全局远程配置服务实例"""
    global _global_remote_config_service
    if _global_remote_config_service is None:
        _global_remote_config_service = RemoteConfigService()
    return _global_remote_config_service


def get_config() -> Dict[str, Any]:
    """获取配置（兼容性函数）"""
    return get_remote_config_service().get_config()


def get_config_value(key: str, default: Any = None) -> Any:
    """获取配置值（兼容性函数）"""
    return get_remote_config_service().get_config_value(key, default)


if __name__ == "__main__":
    # 测试远程配置服务
    service = RemoteConfigService()
    print("🔍 测试远程配置服务...")
    
    config = service.get_config()
    print(f"✅ 配置获取成功: {len(config)} 个配置项")
    
    api_key = service.get_config_value('api_key')
    print(f"API密钥: {'已配置' if api_key else '未配置'}")
    
    firebase_key = service.get_config_value('firebase_api_key')
    print(f"Firebase密钥: {'已配置' if firebase_key else '未配置'}")
    
    service.close()
