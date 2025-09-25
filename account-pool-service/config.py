#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账号池服务配置文件
统一管理所有配置项，支持环境变量覆盖
"""

import os
from typing import Dict, Any


class Config:
    """配置管理类"""
    
    # 账号池服务配置
    POOL_SERVICE_HOST = os.getenv("POOL_SERVICE_HOST", "127.0.0.1")
    POOL_SERVICE_PORT = int(os.getenv("POOL_SERVICE_PORT", 8019))
    
    # 数据库配置
    DATABASE_PATH = os.getenv("DATABASE_PATH", "accounts.db")
    
    # 号池配置
    MIN_POOL_SIZE = int(os.getenv("MIN_POOL_SIZE", 5))  # 最少维持5个账号
    MAX_POOL_SIZE = int(os.getenv("MAX_POOL_SIZE", 9999))  # 最大储备50个账号
    ACCOUNTS_PER_REQUEST = int(os.getenv("ACCOUNTS_PER_REQUEST", 5))  # 每个请求分配1个账号
    
    # 注册器配置
    BATCH_REGISTER_SIZE = int(os.getenv("BATCH_REGISTER_SIZE", 10))  # 每次批量注册10个账号
    REGISTER_TIMEOUT = int(os.getenv("REGISTER_TIMEOUT", 300))  # 注册超时时间（秒）
    
    # 邮箱服务配置（真实可用）
    MOEMAIL_URL = os.getenv("MOEMAIL_URL", "https://rsgdfb.filegear-sg.me")
    MOEMAIL_API_KEY = os.getenv("MOEMAIL_API_KEY", "3055f451-d038-4e2d-ab70-6b824b2e16a1")
    EMAIL_EXPIRY_HOURS = int(os.getenv("EMAIL_EXPIRY_HOURS", 1))
    EMAIL_PREFIX = os.getenv("EMAIL_PREFIX", "zB3w3SQB")
    
    # Firebase配置（真实可用）
    FIREBASE_API_KEYS = [
        os.getenv("FIREBASE_API_KEY_1", "AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs"),
        # 可以继续添加更多API密钥
    ]
    
    # Warp API配置 - 严格按照参考实现
    WARP_BASE_URL = os.getenv("WARP_BASE_URL", "https://app.warp.dev")
    WARP_API_URL = os.getenv("WARP_API_URL", "https://app.warp.dev/ai/multi-agent")
    WARP_GRAPHQL_URL = os.getenv("WARP_GRAPHQL_URL", "https://app.warp.dev/graphql/v2")
    WARP_CLIENT_VERSION = os.getenv("WARP_CLIENT_VERSION", "v0.2025.08.06.08.12.stable_02")
    
    # 操作系统信息 - 严格按照参考实现
    OS_CATEGORY = os.getenv("OS_CATEGORY", "Windows")
    OS_NAME = os.getenv("OS_NAME", "Windows")
    OS_VERSION = os.getenv("OS_VERSION", "11 (26100)")
    
    # JWT和认证配置
    REFRESH_TOKEN_B64 = os.getenv("REFRESH_TOKEN_B64", "Z3JhbnRfdHlwZT1yZWZyZXNoX3Rva2VuJnJlZnJlc2hfdG9rZW49QU1mLXZCeFNSbWRodmVHR0JZTTY5cDA1a0RoSW4xaTd3c2NBTEVtQzlmWURScEh6akVSOWRMN2trLWtIUFl3dlk5Uk9rbXk1MHFHVGNJaUpaNEFtODZoUFhrcFZQTDkwSEptQWY1Zlo3UGVqeXBkYmNLNHdzbzhLZjNheGlTV3RJUk9oT2NuOU56R2FTdmw3V3FSTU5PcEhHZ0JyWW40SThrclc1N1I4X3dzOHU3WGNTdzh1MERpTDlIcnBNbTBMdHdzQ2g4MWtfNmJiMkNXT0ViMWxJeDNIV1NCVGVQRldzUQ==")
    REFRESH_URL = os.getenv("REFRESH_URL", "https://app.warp.dev/proxy/token?key=AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs")
    
    # 日志配置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
    LOG_FILE = os.getenv("LOG_FILE", "account-pool-service.log")
    
    # 安全配置
    MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 2))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))
    
    # 性能优化配置
    HTTP_KEEPALIVE = int(os.getenv("HTTP_KEEPALIVE", 30))  # Keep-Alive超时
    CONNECTION_POOL_SIZE = int(os.getenv("CONNECTION_POOL_SIZE", 10))  # 连接池大小
    RESPONSE_CACHE_TTL = int(os.getenv("RESPONSE_CACHE_TTL", 0))  # 响应缓存TTL（秒，0表示禁用）
    STREAM_CHUNK_DELAY = float(os.getenv("STREAM_CHUNK_DELAY", 0.005))  # 流响应延迟

    @classmethod
    def get_firebase_api_keys(cls) -> list:
        """获取所有Firebase API密钥"""
        keys = [key for key in cls.FIREBASE_API_KEYS if key]
        return keys if keys else ["AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs"]
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """转换为字典格式"""
        config = {}
        for attr in dir(cls):
            if not attr.startswith('_') and not callable(getattr(cls, attr)):
                config[attr] = getattr(cls, attr)
        return config
    
    @classmethod
    def validate(cls) -> bool:
        """验证配置有效性"""
        # 基本校验
        if cls.MIN_POOL_SIZE <= 0:
            raise ValueError("MIN_POOL_SIZE必须大于0")
        
        if cls.MAX_POOL_SIZE < cls.MIN_POOL_SIZE:
            raise ValueError("MAX_POOL_SIZE必须大于等于MIN_POOL_SIZE")
        
        if cls.ACCOUNTS_PER_REQUEST <= 0:
            raise ValueError("ACCOUNTS_PER_REQUEST必须大于0")
        
        # 检查是否有可用的Firebase API密钥
        if not cls.get_firebase_api_keys():
            raise ValueError("至少需要一个有效的Firebase API密钥")
        
        return True


# 配置实例
config = Config()

# 在导入时验证配置
config.validate()