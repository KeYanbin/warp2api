#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Firebase API密钥池管理器
解决API密钥限制和SSL连接问题
"""

import json
import time
import random
import requests
import urllib3
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class FirebaseAPIPool:
    """Firebase API密钥池管理器"""
    
    def __init__(self):
        """初始化API密钥池"""
        self.api_keys = []
        self.current_key_index = 0
        self.key_usage_stats = {}
        self.key_cooldowns = {}
        self.lock = threading.Lock()
        
        # 从远程配置服务加载配置
        self._load_config()
        
        # 初始化使用统计
        self._init_usage_stats()
        
        print(f"🔑 Firebase API密钥池初始化完成，共 {len(self.api_keys)} 个密钥")
    
    def _load_config(self):
        """从远程配置服务加载配置"""
        try:
            try:
                from simple_config import load_config
            except ImportError:
                try:
                    from config_manager import load_config
                except ImportError:
                    from src.modules.config_manager import load_config
            config = load_config()
            
            if not config:
                raise ValueError("无法加载远程配置")
            
            # 支持新的密钥池格式和旧的单密钥格式
            if 'firebase_api_keys' in config:
                self.api_keys = config['firebase_api_keys']
            elif 'firebase_api_key' in config:
                self.api_keys = [config['firebase_api_key']]
            else:
                raise ValueError("远程配置中未找到Firebase API密钥")
            
            # 过滤空密钥
            self.api_keys = [key for key in self.api_keys if key and key.strip()]
            
            if not self.api_keys:
                raise ValueError("没有有效的Firebase API密钥")
                
        except Exception as e:
            print(f"❌ 加载远程配置失败: {e}")
            # 使用默认密钥作为后备
            self.api_keys = ["AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs"]
    
    def _init_usage_stats(self):
        """初始化使用统计"""
        for key in self.api_keys:
            self.key_usage_stats[key] = {
                'total_requests': 0,
                'failed_requests': 0,
                'last_used': None,
                'success_rate': 1.0
            }
            self.key_cooldowns[key] = None
    
    def get_next_api_key(self) -> str:
        """获取下一个可用的API密钥"""
        with self.lock:
            # 查找可用的密钥（不在冷却期）
            available_keys = []
            current_time = datetime.now()
            
            for i, key in enumerate(self.api_keys):
                cooldown_until = self.key_cooldowns.get(key)
                if cooldown_until is None or current_time > cooldown_until:
                    available_keys.append((i, key))
            
            if not available_keys:
                # 如果所有密钥都在冷却期，选择冷却时间最短的
                print("⚠️ 所有API密钥都在冷却期，选择最快恢复的密钥")
                min_cooldown_key = min(self.api_keys, 
                                     key=lambda k: self.key_cooldowns.get(k, datetime.min))
                return min_cooldown_key
            
            # 根据成功率选择最佳密钥
            best_key = max(available_keys, 
                          key=lambda x: self.key_usage_stats[x[1]]['success_rate'])
            
            self.current_key_index = best_key[0]
            return best_key[1]
    
    def mark_key_failed(self, api_key: str, error_type: str = "unknown"):
        """标记密钥失败"""
        with self.lock:
            if api_key in self.key_usage_stats:
                stats = self.key_usage_stats[api_key]
                stats['failed_requests'] += 1
                stats['total_requests'] += 1
                
                # 更新成功率
                if stats['total_requests'] > 0:
                    success_requests = stats['total_requests'] - stats['failed_requests']
                    stats['success_rate'] = success_requests / stats['total_requests']
                
                # 根据错误类型设置冷却时间
                cooldown_minutes = self._get_cooldown_time(error_type)
                if cooldown_minutes > 0:
                    self.key_cooldowns[api_key] = datetime.now() + timedelta(minutes=cooldown_minutes)
                    print(f"🚫 API密钥进入冷却期 {cooldown_minutes} 分钟: {api_key[:20]}...")
    
    def mark_key_success(self, api_key: str):
        """标记密钥成功"""
        with self.lock:
            if api_key in self.key_usage_stats:
                stats = self.key_usage_stats[api_key]
                stats['total_requests'] += 1
                stats['last_used'] = datetime.now()
                
                # 更新成功率
                success_requests = stats['total_requests'] - stats['failed_requests']
                stats['success_rate'] = success_requests / stats['total_requests']
                
                # 清除冷却时间
                self.key_cooldowns[api_key] = None
    
    def _get_cooldown_time(self, error_type: str) -> int:
        """根据错误类型获取冷却时间（分钟）"""
        cooldown_map = {
            "rate_limit": 15,      # 频率限制
            "ssl_error": 5,        # SSL错误
            "connection_error": 3,  # 连接错误
            "timeout": 2,          # 超时
            "unknown": 1           # 未知错误
        }
        return cooldown_map.get(error_type, 1)
    
    def make_firebase_request(self, url: str, method: str = "POST", 
                            data: Optional[Dict] = None, 
                            headers: Optional[Dict] = None,
                            max_retries: int = 3) -> requests.Response:
        """使用密钥池发起Firebase请求"""
        
        if headers is None:
            headers = {}
        
        # 设置SSL安全的请求配置
        session = requests.Session()
        session.verify = False  # 禁用SSL验证以解决Windows证书问题
        
        # 检查是否设置了代理（仅用于本地调试）
        import os
        proxies = None
        if os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY'):
            proxy_url = os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            print(f"🌐 检测到代理配置: {proxy_url}")
        
        # 设置默认headers
        default_headers = {
            'Content-Type': 'application/json',
            'User-Agent': self._generate_random_user_agent(),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache'
        }
        default_headers.update(headers)
        
        for attempt in range(max_retries):
            # 获取API密钥
            api_key = self.get_next_api_key()
            
            # 构建完整URL
            separator = '&' if '?' in url else '?'
            full_url = f"{url}{separator}key={api_key}"
            
            try:
                print(f"🌐 Firebase请求 (尝试 {attempt + 1}/{max_retries}): {method} {url[:50]}...")
                print(f"🔑 使用API密钥: {api_key[:20]}...")
                
                # 发起请求（支持可选代理）
                if method.upper() == "POST":
                    response = session.post(full_url, json=data, headers=default_headers, timeout=30, proxies=proxies)
                elif method.upper() == "GET":
                    response = session.get(full_url, headers=default_headers, timeout=30, proxies=proxies)
                else:
                    response = session.request(method, full_url, json=data, headers=default_headers, timeout=30, proxies=proxies)
                
                # 检查响应
                if response.status_code == 200:
                    self.mark_key_success(api_key)
                    print(f"✅ Firebase请求成功: {response.status_code}")
                    return response
                elif response.status_code == 429:  # 频率限制
                    self.mark_key_failed(api_key, "rate_limit")
                    print(f"⚠️ API密钥频率限制: {response.status_code}")
                else:
                    self.mark_key_failed(api_key, "unknown")
                    print(f"⚠️ Firebase请求失败: {response.status_code}")
                
                # 如果不是最后一次尝试，等待后重试
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt + random.uniform(0, 1)
                    print(f"⏳ 等待 {wait_time:.1f} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    return response
                    
            except requests.exceptions.SSLError as e:
                self.mark_key_failed(api_key, "ssl_error")
                print(f"🔒 SSL错误 (尝试 {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    raise
                    
            except requests.exceptions.ConnectionError as e:
                self.mark_key_failed(api_key, "connection_error")
                print(f"🌐 连接错误 (尝试 {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    raise
                    
            except requests.exceptions.Timeout as e:
                self.mark_key_failed(api_key, "timeout")
                print(f"⏰ 请求超时 (尝试 {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    raise
            
            except Exception as e:
                self.mark_key_failed(api_key, "unknown")
                print(f"❌ 未知错误 (尝试 {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    raise
        
        raise Exception("所有重试都失败了")
    
    def _generate_random_user_agent(self) -> str:
        """生成随机User-Agent"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
        ]
        return random.choice(user_agents)
    
    def get_pool_status(self) -> Dict[str, Any]:
        """获取密钥池状态"""
        with self.lock:
            status = {
                'total_keys': len(self.api_keys),
                'current_key_index': self.current_key_index,
                'keys_status': []
            }
            
            current_time = datetime.now()
            for key in self.api_keys:
                stats = self.key_usage_stats[key]
                cooldown = self.key_cooldowns.get(key)
                
                key_status = {
                    'key_preview': key[:20] + '...',
                    'total_requests': stats['total_requests'],
                    'failed_requests': stats['failed_requests'],
                    'success_rate': f"{stats['success_rate']:.2%}",
                    'last_used': stats['last_used'].isoformat() if stats['last_used'] else None,
                    'in_cooldown': cooldown is not None and current_time < cooldown,
                    'cooldown_until': cooldown.isoformat() if cooldown and current_time < cooldown else None
                }
                status['keys_status'].append(key_status)
            
            return status


# 全局实例
_firebase_pool = None

def get_firebase_pool() -> FirebaseAPIPool:
    """获取Firebase API密钥池实例（单例模式）"""
    global _firebase_pool
    if _firebase_pool is None:
        _firebase_pool = FirebaseAPIPool()
    return _firebase_pool

def make_firebase_request(url: str, method: str = "POST", 
                         data: Optional[Dict] = None, 
                         headers: Optional[Dict] = None,
                         max_retries: int = 3) -> requests.Response:
    """便捷函数：使用密钥池发起Firebase请求"""
    pool = get_firebase_pool()
    return pool.make_firebase_request(url, method, data, headers, max_retries)


if __name__ == "__main__":
    # 测试代码
    pool = FirebaseAPIPool()
    print("🔍 测试Firebase API密钥池...")
    
    # 显示池状态
    status = pool.get_pool_status()
    print(f"密钥池状态: {json.dumps(status, indent=2, ensure_ascii=False)}")
    
    # 测试获取密钥
    for i in range(5):
        key = pool.get_next_api_key()
        print(f"获取密钥 {i+1}: {key[:20]}...")
