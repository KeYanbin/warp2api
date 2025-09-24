#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
辅助函数模块
提供通用的工具函数
"""

import random
import string
from typing import Dict


def generate_random_headers() -> Dict[str, str]:
    """生成随机浏览器headers"""
    # 随机Chrome版本 (120-131)
    chrome_major = random.randint(120, 131)
    chrome_minor = random.randint(0, 9)
    chrome_build = random.randint(6000, 6999)
    chrome_patch = random.randint(100, 999)
    chrome_version = f"{chrome_major}.{chrome_minor}.{chrome_build}.{chrome_patch}"

    # 随机WebKit版本
    webkit_version = f"537.{random.randint(30, 40)}"

    # 随机操作系统版本
    os_versions = [
        "10_15_7",  # macOS Big Sur
        "11_0_1",   # macOS Big Sur
        "12_0_1",   # macOS Monterey
        "13_0_1",   # macOS Ventura
        "14_0_0",   # macOS Sonoma
    ]
    os_version = random.choice(os_versions)

    # 随机语言偏好
    languages = [
        "en-US,en;q=0.9",
        "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "en-US,en;q=0.9,fr;q=0.8",
        "en-US,en;q=0.9,es;q=0.8",
        "en-US,en;q=0.9,de;q=0.8",
    ]
    accept_language = random.choice(languages)

    # 生成User-Agent
    user_agent = f"Mozilla/5.0 (Macintosh; Intel Mac OS X {os_version}) AppleWebKit/{webkit_version} (KHTML, like Gecko) Chrome/{chrome_version} Safari/{webkit_version}"

    return {
        'Content-Type': 'application/json',
        'User-Agent': user_agent,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': accept_language,
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site',
        'Origin': 'https://app.warp.dev',
        'Referer': 'https://app.warp.dev/',
        'Sec-Ch-Ua': f'"Chromium";v="{chrome_major}", "Google Chrome";v="{chrome_major}", "Not=A?Brand";v="99"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"macOS"'
    }


def generate_random_email_prefix() -> str:
    """生成随机邮箱前缀"""
    # 随机单词列表
    words = [
        'alpha', 'beta', 'gamma', 'delta', 'omega', 'sigma', 'theta',
        'nova', 'star', 'moon', 'sun', 'sky', 'cloud', 'wind', 'fire',
        'water', 'earth', 'light', 'dark', 'swift', 'quick', 'fast',
        'blue', 'red', 'green', 'gold', 'silver', 'crystal', 'diamond',
        'magic', 'power', 'force', 'energy', 'spark', 'flash', 'bolt',
        'wave', 'flow', 'stream', 'river', 'ocean', 'lake', 'forest',
        'mountain', 'valley', 'peak', 'edge', 'core', 'prime', 'ultra',
        'mega', 'super', 'hyper', 'turbo', 'boost', 'rush', 'dash',
        'zoom', 'speed', 'rapid', 'sonic', 'echo', 'pulse', 'vibe'
    ]

    # 选择随机单词
    word = random.choice(words)

    # 生成随机字符串（6-8位）
    length = random.randint(6, 8)
    chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    return f"{word}{chars}"


def validate_email(email: str) -> bool:
    """简单的邮箱格式验证"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def generate_machine_id() -> str:
    """生成随机机器ID"""
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=32))


def safe_get_dict_value(data: dict, keys: list, default=None):
    """安全地从嵌套字典中获取值"""
    try:
        result = data
        for key in keys:
            result = result[key]
        return result
    except (KeyError, TypeError, AttributeError):
        return default