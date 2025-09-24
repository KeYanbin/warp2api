#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的配置加载器 - 用于账号池服务
不依赖远程数据库，直接使用本地配置
"""

from typing import Dict, Any, Optional


def load_config() -> Dict[str, Any]:
    """
    加载配置（简化版）
    
    Returns:
        配置字典
    """
    return {
        "api_key": "mk_IpnNUYb8KgdCTJLokCgAthP7OVirjIqX",
        "moemail_url": "https://rsgdfb.filegear-sg.me",
        "moemail_api_key": "mk_IpnNUYb8KgdCTJLokCgAthP7OVirjIqX",
        "register_url": "https://app.warp.dev",
        "login_url": "https://app.warp.dev/login",
        "email_prefix": "warp",
        "email_expiry_hours": 1,
        "auto_refresh": True,
        "check_interval": 5,
        "max_wait_time": 300,
        "firebase_api_keys": [
            "AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs"
        ],
        "firebase_api_key": "AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs",
        # moemail 嵌套结构
        "moemail": {
            "base_url": "https://rsgdfb.filegear-sg.me",
            "api_key": "mk_IpnNUYb8KgdCTJLokCgAthP7OVirjIqX"
        }
    }


def get_config_value(key: str, default: Any = None) -> Any:
    """
    获取配置值
    
    Args:
        key: 配置键，支持点号分隔的嵌套键如 'moemail.base_url'
        default: 默认值
        
    Returns:
        配置值
    """
    config = load_config()
    
    # 支持嵌套键访问
    keys = key.split('.')
    value = config
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k)
            if value is None:
                return default
        else:
            return default
    
    return value if value is not None else default