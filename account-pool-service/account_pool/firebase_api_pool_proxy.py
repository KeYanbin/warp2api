#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
支持代理的Firebase API池
"""

import os
import json
import time
import random
import requests
import urllib3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class FirebaseAPIPoolWithProxy:
    """支持代理的Firebase API密钥池管理器"""
    
    def __init__(self, proxy_url: str = None):
        """
        初始化API密钥池
        
        Args:
            proxy_url: 代理服务器URL，例如 "http://127.0.0.1:7890" 或 "socks5://127.0.0.1:7891"
        """
        self.api_keys = []
        self.current_key_index = 0
        
        # 设置代理
        self.proxy_url = proxy_url or os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
        if self.proxy_url:
            self.proxies = {
                'http': self.proxy_url,
                'https': self.proxy_url
            }
            print(f"🌐 使用代理: {self.proxy_url}")
        else:
            self.proxies = None
            print("⚠️ 未配置代理，将直接连接（可能失败）")
        
        # 加载配置
        self._load_config()
        
        print(f"🔑 Firebase API密钥池初始化完成，共 {len(self.api_keys)} 个密钥")
    
    def _load_config(self):
        """加载配置"""
        try:
            from simple_config import load_config
            config = load_config()
            
            if 'firebase_api_keys' in config:
                self.api_keys = config['firebase_api_keys']
            elif 'firebase_api_key' in config:
                self.api_keys = [config['firebase_api_key']]
            else:
                # 使用默认密钥
                self.api_keys = ["AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs"]
        except Exception as e:
            print(f"⚠️ 加载配置失败: {e}")
            self.api_keys = ["AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs"]
    
    def get_next_api_key(self) -> str:
        """获取下一个API密钥"""
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key
    
    def make_firebase_request(self, url: str, method: str = "POST", 
                            data: Optional[Dict] = None, 
                            headers: Optional[Dict] = None,
                            max_retries: int = 3) -> requests.Response:
        """使用代理发起Firebase请求"""
        
        if headers is None:
            headers = {}
        
        # 设置默认headers
        default_headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
        }
        default_headers.update(headers)
        
        for attempt in range(max_retries):
            # 获取API密钥
            api_key = self.get_next_api_key()
            
            # 构建完整URL
            separator = '&' if '?' in url else '?'
            full_url = f"{url}{separator}key={api_key}"
            
            try:
                print(f"🌐 Firebase请求 (尝试 {attempt + 1}/{max_retries})")
                print(f"   URL: {url[:50]}...")
                print(f"   密钥: {api_key[:20]}...")
                if self.proxies:
                    print(f"   代理: {self.proxy_url}")
                
                # 创建session并配置
                session = requests.Session()
                session.verify = False  # 禁用SSL验证
                
                # 发起请求
                if method.upper() == "POST":
                    response = session.post(
                        full_url, 
                        json=data, 
                        headers=default_headers, 
                        timeout=30,
                        proxies=self.proxies
                    )
                else:
                    response = session.get(
                        full_url, 
                        headers=default_headers, 
                        timeout=30,
                        proxies=self.proxies
                    )
                
                print(f"   响应: {response.status_code}")
                
                # 返回响应
                return response
                    
            except requests.exceptions.ProxyError as e:
                print(f"❌ 代理错误: {str(e)[:100]}...")
                if attempt == max_retries - 1:
                    raise Exception(f"代理连接失败: {e}")
                    
            except requests.exceptions.ConnectionError as e:
                print(f"❌ 连接错误: {str(e)[:100]}...")
                if attempt == max_retries - 1:
                    raise Exception(f"连接失败: {e}")
                    
            except requests.exceptions.Timeout as e:
                print(f"❌ 请求超时: {str(e)[:100]}...")
                if attempt == max_retries - 1:
                    raise Exception(f"请求超时: {e}")
                    
            except Exception as e:
                print(f"❌ 未知错误: {str(e)[:100]}...")
                if attempt == max_retries - 1:
                    raise
            
            # 重试前等待
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"⏳ 等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
        
        raise Exception("所有重试都失败了")


# 便捷函数
def make_firebase_request_with_proxy(url: str, method: str = "POST", 
                                    data: Optional[Dict] = None,
                                    proxy_url: str = None) -> requests.Response:
    """
    使用代理发起Firebase请求的便捷函数
    
    Args:
        url: 请求URL
        method: 请求方法
        data: 请求数据
        proxy_url: 代理URL（如果不提供，将从环境变量读取）
    """
    pool = FirebaseAPIPoolWithProxy(proxy_url)
    return pool.make_firebase_request(url, method, data)


def test_with_proxy():
    """测试代理连接"""
    print("=" * 80)
    print("🧪 测试通过代理连接Firebase")
    print("=" * 80)
    
    # 尝试从环境变量或用户输入获取代理
    proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
    
    if not proxy:
        print("\n请输入代理服务器地址（例如: http://127.0.0.1:7890）")
        print("如果没有代理，请直接按回车跳过：")
        proxy = input("代理地址: ").strip()
    
    if proxy:
        print(f"\n使用代理: {proxy}")
    else:
        print("\n不使用代理（可能无法连接）")
    
    # 创建池
    pool = FirebaseAPIPoolWithProxy(proxy)
    
    # 测试请求
    test_email = "test@example.com"
    url = "https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode"
    
    payload = {
        "requestType": "EMAIL_SIGNIN",
        "email": test_email,
        "clientType": "CLIENT_TYPE_WEB",
        "continueUrl": "https://app.warp.dev/login",
        "canHandleCodeInApp": True
    }
    
    try:
        response = pool.make_firebase_request(url, "POST", payload)
        if response.status_code == 200:
            print("✅ 连接成功！")
        else:
            print(f"⚠️ 连接成功但返回错误: {response.status_code}")
            print(f"响应: {response.text[:200]}...")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_with_proxy()