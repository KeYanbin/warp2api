#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare 优选 IP 自定义 DNS 解析模块
基于 test.txt 的方法，通过自定义 DNS 解析使用 Cloudflare 优选 IP
而不是将它们作为代理使用
"""

import json
import time
import random
import requests
import socket
import ipaddress
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urlparse
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.connection import create_connection
from urllib3.util import connection
import urllib3
import ssl

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Cloudflare IP API和端口配置（与 test.txt 一致）
CF_IP_API_URL = "https://ipdb.api.030101.xyz/?type=cfv4;proxy"
CF_HTTPS_PORTS = [443, 2053, 2083, 2087, 2096, 8443]
CF_HTTP_PORTS = [80, 8080, 8880, 2052, 2082, 2086, 2095]

# Cloudflare 优选 IP 段（CIDR格式）
CLOUDFLARE_IP_RANGES = [
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22"
]


class CloudflareDNSResolver:
    """
    Cloudflare 优选 IP DNS 解析器
    通过自定义 DNS 解析，将请求直接发送到 Cloudflare IP
    """
    
    def __init__(self, use_api: bool = True):
        """
        初始化 DNS 解析器
        
        Args:
            use_api: 是否从 API 获取 IP 列表
        """
        self.cf_ips = []
        self.last_update_time = 0
        self.update_interval = 300  # 5分钟更新一次
        self.use_api = use_api
        
        print("🌐 初始化 Cloudflare DNS 解析器...")
        self._update_ip_list()
    
    def _update_ip_list(self) -> bool:
        """更新 IP 列表"""
        if self.use_api:
            return self._fetch_ips_from_api()
        else:
            return self._generate_ips_from_cidr()
    
    def _fetch_ips_from_api(self) -> bool:
        """从 API 获取 IP 列表（与 test.txt 一致）"""
        try:
            print(f"正在从API获取最新的Cloudflare优选IP列表...")
            response = requests.get(CF_IP_API_URL, timeout=10)
            
            if response.status_code == 200:
                text = response.text.strip()
                self.cf_ips = [ip.strip() for ip in text.split('\n') if ip.strip()]
                self.last_update_time = time.time()
                print(f"成功获取 {len(self.cf_ips)} 个优选IP")
                return True
            else:
                print(f"API请求失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"获取优选IP列表时出错: {e}")
            # 如果 API 失败，尝试使用 CIDR 生成
            if not self.cf_ips:
                return self._generate_ips_from_cidr()
            return False
    
    def _generate_ips_from_cidr(self) -> bool:
        """从 CIDR 段生成 IP 列表"""
        try:
            print("从 CIDR 段生成 IP 地址...")
            all_ips = []
            
            # 从每个 CIDR 段随机选择一些 IP
            for cidr_range in CLOUDFLARE_IP_RANGES[:5]:  # 只使用前5个段
                try:
                    network = ipaddress.ip_network(cidr_range, strict=False)
                    hosts = list(network.hosts())
                    
                    # 随机选择最多 20 个 IP
                    sample_size = min(20, len(hosts))
                    selected_ips = random.sample(hosts, sample_size)
                    
                    for ip in selected_ips:
                        all_ips.append(str(ip))
                        
                except Exception as e:
                    print(f"处理 CIDR {cidr_range} 失败: {e}")
            
            random.shuffle(all_ips)
            self.cf_ips = all_ips
            self.last_update_time = time.time()
            
            print(f"成功生成 {len(self.cf_ips)} 个 IP")
            return True
            
        except Exception as e:
            print(f"生成 IP 列表失败: {e}")
            return False
    
    def get_random_endpoint(self, url: str) -> Tuple[str, int]:
        """
        获取随机的 Cloudflare IP 和端口
        
        Args:
            url: 目标 URL
            
        Returns:
            (IP, 端口) 元组
        """
        # 检查是否需要更新
        if time.time() - self.last_update_time > self.update_interval:
            self._update_ip_list()
        
        if not self.cf_ips:
            raise Exception("优选 IP 列表为空")
        
        # 随机选择 IP
        random_ip = random.choice(self.cf_ips)
        
        # 根据 URL 协议选择端口
        is_https = url.startswith("https://")
        ports = CF_HTTPS_PORTS if is_https else CF_HTTP_PORTS
        random_port = random.choice(ports)
        
        return random_ip, random_port


class CloudflareHTTPAdapter(HTTPAdapter):
    """
    自定义 HTTP 适配器
    将特定域名的请求解析到 Cloudflare 优选 IP
    """
    
    def __init__(self, dns_resolver: CloudflareDNSResolver, target_domains: List[str] = None, *args, **kwargs):
        """
        初始化适配器
        
        Args:
            dns_resolver: DNS 解析器实例
            target_domains: 需要使用优选 IP 的域名列表
        """
        super().__init__(*args, **kwargs)
        self.dns_resolver = dns_resolver
        self.target_domains = target_domains or []
        self.original_create_connection = connection.create_connection
    
    def init_poolmanager(self, *args, **kwargs):
        """初始化连接池管理器"""
        # 保存原始的 create_connection
        self._original_create_connection = connection.create_connection
        # 替换为自定义的创建连接函数
        connection.create_connection = self._custom_create_connection
        return super().init_poolmanager(*args, **kwargs)
    
    def _custom_create_connection(self, address, timeout=None, source_address=None, socket_options=None):
        """
        自定义连接创建函数
        如果是目标域名，使用 Cloudflare IP；否则使用原始连接
        """
        host, port = address
        
        # 检查是否是需要使用优选 IP 的域名
        should_use_cf_ip = False
        for domain in self.target_domains:
            if domain in host:
                should_use_cf_ip = True
                break
        
        if should_use_cf_ip:
            try:
                # 获取随机的 Cloudflare IP 和端口
                cf_ip, cf_port = self.dns_resolver.get_random_endpoint(f"https://{host}")
                print(f"🔄 DNS 解析: {host} -> {cf_ip}:{cf_port}")
                
                # 创建到 Cloudflare IP 的连接
                sock = socket.create_connection(
                    (cf_ip, cf_port),
                    timeout=timeout,
                    source_address=source_address
                )
                
                # 设置 socket 选项
                if socket_options:
                    for opt in socket_options:
                        sock.setsockopt(*opt)
                
                return sock
                
            except Exception as e:
                print(f"⚠️ 使用优选 IP 失败，回退到默认: {e}")
                # 如果失败，回退到原始连接
        
        # 使用原始的连接方法
        return self._original_create_connection(
            address, 
            timeout=timeout, 
            source_address=source_address,
            socket_options=socket_options
        )


class CloudflareOptimizedSession:
    """
    使用 Cloudflare 优选 IP 的优化会话
    """
    
    def __init__(self, target_domains: List[str] = None, use_api: bool = True):
        """
        初始化优化会话
        
        Args:
            target_domains: 需要使用优选 IP 的域名列表
            use_api: 是否从 API 获取 IP
        """
        self.dns_resolver = CloudflareDNSResolver(use_api=use_api)
        self.target_domains = target_domains or [
            "googleapis.com",
            "warp.dev",
            "cloudflare.com"
        ]
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """创建配置了自定义 DNS 的会话"""
        session = requests.Session()
        
        # 使用自定义适配器
        adapter = CloudflareHTTPAdapter(
            dns_resolver=self.dns_resolver,
            target_domains=self.target_domains,
            pool_connections=10,
            pool_maxsize=20,
            max_retries=3
        )
        
        # 为 HTTP 和 HTTPS 都设置适配器
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        return session
    
    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        发送请求
        
        Args:
            method: HTTP 方法
            url: 请求 URL
            **kwargs: 其他请求参数
            
        Returns:
            响应对象
        """
        # 确保 verify=False 以避免 SSL 证书问题
        if 'verify' not in kwargs:
            kwargs['verify'] = False
        
        return self.session.request(method, url, **kwargs)
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """GET 请求"""
        return self.request('GET', url, **kwargs)
    
    def post(self, url: str, **kwargs) -> requests.Response:
        """POST 请求"""
        return self.request('POST', url, **kwargs)


def test_cloudflare_dns():
    """测试 Cloudflare DNS 解析功能"""
    print("=" * 80)
    print("🧪 测试 Cloudflare DNS 解析")
    print("=" * 80)
    
    # 创建优化的会话
    print("\n1️⃣ 创建优化会话...")
    session = CloudflareOptimizedSession(
        target_domains=["googleapis.com", "httpbin.org"],
        use_api=True
    )
    
    # 测试请求
    print("\n2️⃣ 测试请求...")
    test_urls = [
        "https://httpbin.org/ip",
        "https://httpbin.org/headers"
    ]
    
    for url in test_urls:
        try:
            print(f"\n测试: {url}")
            response = session.get(url, timeout=10)
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)[:200]}...")
            
        except Exception as e:
            print(f"❌ 请求失败: {e}")
    
    print("\n" + "=" * 80)
    print("测试完成!")


def demo_usage():
    """演示如何在实际场景中使用"""
    print("\n" + "🌟" * 40)
    print("Cloudflare DNS 解析使用示例")
    print("🌟" * 40)
    
    # 示例1：用于 Firebase API
    print("\n示例1: Firebase API 请求")
    session = CloudflareOptimizedSession(
        target_domains=["googleapis.com"],
        use_api=True
    )
    
    # 模拟 Firebase 请求
    firebase_url = "https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    }
    
    print(f"目标 URL: {firebase_url}")
    print("这将使用 Cloudflare 优选 IP 进行 DNS 解析")
    
    # 示例2：普通请求
    print("\n示例2: 普通请求（不使用优选 IP）")
    response = session.get("https://example.com", timeout=10)
    print(f"example.com 状态码: {response.status_code}")


if __name__ == "__main__":
    # 运行测试
    test_cloudflare_dns()
    
    print("\n" + "-" * 80)
    
    # 运行示例
    demo_usage()