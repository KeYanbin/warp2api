#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
带有 Cloudflare 优选 IP 的独立注册功能
支持通过自定义 DNS 解析使用 Cloudflare 优选 IP 完成 Warp 账号注册
基于 test.txt 的正确实现方式
"""

import json
import time
import random
import requests
import re
import html
import ipaddress
import socket
from typing import Dict, Any, Optional, List, Tuple, Union
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.connection import create_connection
from urllib3.util import connection
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Cloudflare IP API和端口配置
CF_IP_API_URL = "https://ipdb.api.030101.xyz/?type=cfv4;proxy"
CF_HTTPS_PORTS = [443, 2053, 2083, 2087, 2096, 8443]
CF_HTTP_PORTS = [80, 8080, 8880, 2052, 2082, 2086, 2095]

# Cloudflare 优选 IP 段（CIDR格式）
# 来源: https://www.cloudflare.com/ips/
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

# 导入现有模块
try:
    from moemail_client import MoeMailClient
    from simple_domain_selector import get_random_email_domain
    from simple_config import load_config
except ImportError:
    from .moemail_client import MoeMailClient
    from .simple_domain_selector import get_random_email_domain
    from .simple_config import load_config

# 导入主配置
try:
    from config import config as main_config
except ImportError:
    try:
        from ..config import config as main_config
    except ImportError:
        # 如果无法导入主配置，创建一个默认的
        class DefaultConfig:
            MOEMAIL_API_KEY = "3055f451-d038-4e2d-ab70-6b824b2e16a1"
            MOEMAIL_URL = "https://rsgdfb.filegear-sg.me"
        main_config = DefaultConfig()


class CloudflareDNSResolver:
    """
    Cloudflare 优选 IP DNS 解析器
    基于 test.txt 的方法，通过自定义 DNS 解析使用 Cloudflare 优选 IP
    而不是将它们作为代理
    """
    
    def __init__(self, api_url: str = CF_IP_API_URL, use_api: bool = True):
        """
        初始化 DNS 解析器
        
        Args:
            api_url: Cloudflare IP API 地址
            use_api: 是否从 API 获取 IP 列表
        """
        self.api_url = api_url
        self.cf_ips = []
        self.last_refresh_time = 0
        self.refresh_interval = 300  # 5分钟刷新一次（与 test.txt 一致）
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
        """从 API 获取 IP 列表（与 test.txt fetchAndUpdateCfIps 一致）"""
        try:
            print("正在从API获取最新的Cloudflare优选IP列表...")
            response = requests.get(self.api_url, timeout=10)
            
            if response.status_code == 200:
                text = response.text.strip()
                self.cf_ips = [ip.strip() for ip in text.split('\n') if ip.strip()]
                self.last_refresh_time = time.time()
                print(f"成功获取 {len(self.cf_ips)} 个优选IP")
                
                if len(self.cf_ips) == 0:
                    print("警告：获取到的IP列表为空，请检查API或网络连接")
                    return self._generate_ips_from_cidr()  # 回退到 CIDR
                    
                return True
            else:
                print(f"API请求失败: {response.status_code}")
                return self._generate_ips_from_cidr()  # 回退到 CIDR
                
        except Exception as e:
            print(f"获取优选IP列表时出错: {e}")
            # 如果获取失败，尝试使用 CIDR 生成
            return self._generate_ips_from_cidr()
    
    def _generate_ips_from_cidr(self) -> bool:
        """从CIDR段生成IP地址列表"""
        try:
            print(f"🔄 从CIDR段生成IP地址...")
            all_ips = []
            
            for cidr_range in self.cidr_ranges:
                try:
                    # 解析CIDR段
                    network = ipaddress.ip_network(cidr_range, strict=False)
                    
                    # 获取网络中的所有主机地址
                    # 对于大的网段，随机选择一部分IP以避免过多
                    hosts = list(network.hosts())
                    
                    if len(hosts) > 100:
                        # 对于大网段，随机选择100个IP
                        selected_ips = random.sample(hosts, min(100, len(hosts)))
                    else:
                        selected_ips = hosts
                    
                    # 转换为字符串格式
                    for ip in selected_ips:
                        all_ips.append(str(ip))
                    
                    print(f"  ✓ {cidr_range}: 生成 {len(selected_ips)} 个IP")
                    
                except Exception as e:
                    print(f"  ✗ 处理 {cidr_range} 失败: {e}")
            
            # 随机打乱IP列表
            random.shuffle(all_ips)
            self.proxy_ips = all_ips
            self.last_refresh_time = time.time()
            
            print(f"✅ 成功生成 {len(self.proxy_ips)} 个代理IP")
            return True
            
        except Exception as e:
            print(f"❌ 生成IP列表失败: {e}")
            return False
    
    def get_random_endpoint(self, url: str) -> Tuple[str, int]:
        """
        获取随机的 Cloudflare IP 和端口（与 test.txt getRandomCfEndpoint 一致）
        
        Args:
            url: 目标 URL
            
        Returns:
            (IP, 端口) 元组
        """
        # 检查是否需要更新
        if time.time() - self.last_refresh_time > self.refresh_interval:
            self._update_ip_list()
        
        if not self.cf_ips:
            raise Exception("优选IP列表为空，无法创建连接")
        
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
    基于 test.txt 的正确实现方式
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
        self.target_domains = target_domains or [
            "googleapis.com",
            "warp.dev",
            "cloudflare.com"
        ]
        self._original_create_connection = None
    
    def init_poolmanager(self, *args, **kwargs):
        """初始化连接池管理器"""
        # 保存原始的 create_connection
        self._original_create_connection = connection.create_connection
        # 替换为自定义的创建连接函数
        connection.create_connection = self._create_custom_connection
        return super().init_poolmanager(*args, **kwargs)
    
    def _create_custom_connection(self, address, timeout=None, source_address=None, socket_options=None):
        """
        自定义连接创建函数
        如果是目标域名，使用 Cloudflare IP；否则使用原始连接
        """
        host, port = address
        
        # 检查是否是需要使用优选 IP 的域名
        should_use_cf_ip = any(domain in host for domain in self.target_domains)
        
        if should_use_cf_ip:
            try:
                # 获取随机的 Cloudflare IP 和端口
                cf_ip, cf_port = self.dns_resolver.get_random_endpoint(f"https://{host}")
                print(f"🔄 使用优选IP: {cf_ip}:{cf_port} 请求: {host}")
                
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
        
        # 使用原始的连接方法
        if self._original_create_connection:
            return self._original_create_connection(
                address, 
                timeout=timeout, 
                source_address=source_address,
                socket_options=socket_options
            )
        else:
            return socket.create_connection(
                address,
                timeout=timeout,
                source_address=source_address
            )


# 保留兼容性的 ProxyPool 类（现在只是 CloudflareDNSResolver 的别名）
class ProxyPool(CloudflareDNSResolver):
    """保留向后兼容性"""
    def __init__(self, api_url: str = CF_IP_API_URL, use_cidr_ranges: bool = True, 
                 custom_ranges: Optional[List[str]] = None):
        # 将旧参数映射到新参数
        use_api = not use_cidr_ranges
        super().__init__(api_url=api_url, use_api=use_api)
        if custom_ranges:
            self.cidr_ranges = custom_ranges
    
    def get_next_proxy(self, use_https: bool = True) -> Optional[Dict[str, str]]:
        """
        获取下一个可用的代理
        
        Args:
            use_https: 是否使用HTTPS端口
            
        Returns:
            代理配置字典，格式: {'http': 'http://ip:port', 'https': 'http://ip:port'}
        """
        # 检查是否需要刷新代理列表
        if time.time() - self.last_refresh_time > self.refresh_interval:
            if self.use_cidr_ranges:
                self._generate_ips_from_cidr()
            else:
                self._refresh_proxy_list()
        
        if not self.proxy_ips:
            print("⚠️ 代理池为空，尝试刷新...")
            if self.use_cidr_ranges:
                if not self._generate_ips_from_cidr():
                    return None
            else:
                if not self._refresh_proxy_list():
                    return None
        
        # 获取下一个IP
        ip = self.proxy_ips[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxy_ips)
        
        # 随机选择端口
        port = random.choice(CF_HTTPS_PORTS if use_https else CF_HTTP_PORTS)
        
        # 构建代理URL（使用HTTP代理协议）
        proxy_url = f"http://{ip}:{port}"
        
        return {
            'http': proxy_url,
            'https': proxy_url
        }
    
    def get_random_proxy(self, use_https: bool = True) -> Optional[Dict[str, str]]:
        """
        随机获取一个代理
        
        Args:
            use_https: 是否使用HTTPS端口
            
        Returns:
            代理配置字典
        """
        if not self.proxy_ips:
            if self.use_cidr_ranges:
                self._generate_ips_from_cidr()
            else:
                self._refresh_proxy_list()
        
        if not self.proxy_ips:
            return None
        
        ip = random.choice(self.proxy_ips)
        port = random.choice(CF_HTTPS_PORTS if use_https else CF_HTTP_PORTS)
        proxy_url = f"http://{ip}:{port}"
        
        return {
            'http': proxy_url,
            'https': proxy_url
        }
    
    def add_cidr_range(self, cidr: str) -> bool:
        """
        添加新的CIDR IP段到池中
        
        Args:
            cidr: CIDR格式的IP段，如 "173.245.48.0/20"
            
        Returns:
            是否添加成功
        """
        try:
            # 验证CIDR格式
            network = ipaddress.ip_network(cidr, strict=False)
            
            if cidr not in self.cidr_ranges:
                self.cidr_ranges.append(cidr)
                print(f"✅ 已添加CIDR段: {cidr}")
                
                # 重新生成IP列表
                if self.use_cidr_ranges:
                    self._generate_ips_from_cidr()
                
                return True
            else:
                print(f"⚠️ CIDR段已存在: {cidr}")
                return False
                
        except Exception as e:
            print(f"❌ 无效的CIDR格式 {cidr}: {e}")
            return False
    
    def get_ip_count(self) -> int:
        """获取当前池中的IP数量"""
        return len(self.proxy_ips)
    
    def get_current_ip(self) -> Optional[str]:
        """获取当前使用的IP（不切换索引）"""
        if self.proxy_ips and self.current_index < len(self.proxy_ips):
            return self.proxy_ips[self.current_index]
        return None


class ProxyRegistration:
    """使用 Cloudflare 优选 IP 的 Warp 账号注册器"""
    
    def __init__(self, dns_resolver: Optional[CloudflareDNSResolver] = None, 
                 proxy_pool: Optional[ProxyPool] = None, 
                 config: Optional[Dict] = None):
        """
        初始化注册器
        
        Args:
            dns_resolver: DNS 解析器实例
            proxy_pool: 代理池实例（为了兼容性保留）
            config: 配置字典，如果不提供会自动加载
        """
        print("🤖 初始化注册器...")
        
        # 初始化 DNS 解析器（优先使用 dns_resolver，其次是 proxy_pool）
        self.dns_resolver = dns_resolver or proxy_pool or CloudflareDNSResolver()
        
        # 加载配置
        self.config = config or load_config()
        if not self.config:
            raise Exception("无法加载配置")
        
        # 初始化邮箱客户端
        self.moemail_client = MoeMailClient(
            self.config.get('moemail_url'),
            self.config.get('api_key')
        )
        
        # Firebase API密钥
        self.firebase_api_keys = self.config.get('firebase_api_keys', [
            'AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs'
        ])
        self.current_key_index = 0
        
        # 创建优化的会话
        self.session = self._create_optimized_session()
        
        print("✅ 注册器初始化完成")
    
    def _create_optimized_session(self) -> requests.Session:
        """创建配置了自定义 DNS 的会话"""
        session = requests.Session()
        
        # 使用自定义适配器
        adapter = CloudflareHTTPAdapter(
            dns_resolver=self.dns_resolver,
            target_domains=["googleapis.com", "warp.dev", "firebaseapp.com"],
            pool_connections=10,
            pool_maxsize=20,
            max_retries=3
        )
        
        # 为 HTTP 和 HTTPS 都设置适配器
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        return session
    
    def _get_next_firebase_key(self) -> str:
        """获取下一个Firebase API密钥"""
        key = self.firebase_api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.firebase_api_keys)
        return key
    
    def _generate_random_headers(self) -> Dict[str, str]:
        """生成随机浏览器headers"""
        # 随机Chrome版本
        chrome_major = random.randint(120, 131)
        chrome_minor = random.randint(0, 9)
        chrome_build = random.randint(6000, 6999)
        chrome_patch = random.randint(100, 999)
        chrome_version = f"{chrome_major}.{chrome_minor}.{chrome_build}.{chrome_patch}"

        # 随机WebKit版本
        webkit_version = f"537.{random.randint(30, 40)}"

        # 随机操作系统版本
        os_versions = ["10_15_7", "11_0_1", "12_0_1", "13_0_1", "14_0_0"]
        os_version = random.choice(os_versions)

        # 随机语言偏好
        languages = [
            "en-US,en;q=0.9",
            "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "en-US,en;q=0.9,fr;q=0.8",
        ]
        accept_language = random.choice(languages)

        user_agent = f"Mozilla/5.0 (Macintosh; Intel Mac OS X {os_version}) AppleWebKit/{webkit_version} (KHTML, like Gecko) Chrome/{chrome_version} Safari/{webkit_version}"

        # 生成随机的 experiment-id (UUID v4 格式)
        import uuid
        experiment_id = str(uuid.uuid4())

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
            'Sec-Ch-Ua-Platform': '"macOS"',
            'X-Warp-Experiment-Id': experiment_id
        }
    
    def _generate_random_email_prefix(self) -> str:
        """生成随机邮箱前缀"""
        words = [
            'alpha', 'beta', 'gamma', 'delta', 'omega', 'sigma', 'theta',
            'nova', 'star', 'moon', 'sun', 'sky', 'cloud', 'wind', 'fire',
            'water', 'earth', 'light', 'dark', 'swift', 'quick', 'fast',
        ]
        
        word = random.choice(words)
        import string
        length = random.randint(6, 8)
        chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
        
        return f"{word}{chars}"
    
    def _make_firebase_request(self, url: str, data: Dict, max_retries: int = 5) -> requests.Response:
        """
        使用优化会话发起 Firebase 请求
        
        Args:
            url: 请求URL
            data: 请求数据
            max_retries: 最大重试次数
            
        Returns:
            响应对象
        """
        for attempt in range(max_retries):
            try:
                # 获取 Firebase API 密钥
                api_key = self._get_next_firebase_key()
                
                # 构建完整 URL
                separator = '&' if '?' in url else '?'
                full_url = f"{url}{separator}key={api_key}"
                
                # 生成 headers
                headers = self._generate_random_headers()
                
                print(f"🌐 Firebase请求 (尝试 {attempt + 1}/{max_retries})")
                print(f"   使用优选IP DNS解析")
                
                # 使用优化的会话发起请求
                response = self.session.post(
                    full_url,
                    json=data,
                    headers=headers,
                    timeout=30,
                    verify=False  # 禁用 SSL 验证
                )
                
                print(f"   响应: {response.status_code}")
                
                if response.status_code in [200, 400]:  # 400 也可能是有效响应
                    return response
                
            except Exception as e:
                print(f"❌ 请求失败: {str(e)[:100]}")
                if attempt == max_retries - 1:
                    raise
            
            # 等待后重试
            if attempt < max_retries - 1:
                wait_time = min(2 ** attempt, 10)  # 指数退避，最多 10 秒
                print(f"⏳ 等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
        
        raise Exception("所有重试都失败了")
    
    def _create_email(self) -> Optional[Dict[str, Any]]:
        """创建临时邮箱（使用addUser API）"""
        try:
            print("📧 创建临时邮箱...")
            
            # 生成随机邮箱前缀
            email_prefix = self._generate_random_email_prefix()
            
            # 获取随机域名
            domain = get_random_email_domain()
            
            print(f"📧 使用域名: {domain}")
            print(f"📧 使用前缀: {email_prefix}")
            
            # 创建完整的邮箱地址
            email_address = f"{email_prefix}@{domain}"
            
            print(f"📧 使用addUser接口创建用户: {email_address}")
            
            # 准备请求数据
            user_data = {
                "email": email_address
            }
            
            request_payload = {
                "list": [user_data]
            }
            
            # 准备请求头（使用正确的 token）
            headers = {
                "Content-Type": "application/json",
                "Authorization": main_config.MOEMAIL_EMAIL_LIST_TOKEN  # 使用 emailList token
            }
            
            # 发送请求到addUser接口
            import requests
            response = requests.post(
                f"{main_config.MOEMAIL_URL.rstrip('/')}/api/public/addUser",
                json=request_payload,
                headers=headers,
                timeout=30,
                verify=False
            )
            
            print(f"   响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 200:
                    print(f"✅ addUser接口创建成功: {email_address}")
                    
                    # 返回兼容格式的结果
                    return {
                        'email': email_address,
                        'email_id': f"adduser_{email_prefix}_{int(time.time())}",
                        'domain': domain,
                        'prefix': email_prefix
                    }
                else:
                    error_msg = result.get('message', '未知错误')
                    print(f"❌ addUser接口返回错误: {error_msg}")
                    return None
            else:
                print(f"❌ addUser接口HTTP错误 {response.status_code}: {response.text[:200]}")
                return None
                
        except Exception as e:
            print(f"❌ 创建邮箱异常: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _send_signin_link(self, email: str) -> Dict[str, Any]:
        """发送登录链接到邮箱"""
        try:
            print(f"📤 发送登录链接到: {email}")
            
            url = "https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode"
            
            payload = {
                "requestType": "EMAIL_SIGNIN",
                "email": email,
                "clientType": "CLIENT_TYPE_WEB",
                "continueUrl": "https://app.warp.dev/login",
                "canHandleCodeInApp": True
            }
            
            response = self._make_firebase_request(url, payload)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 登录链接已发送")
                return {'success': True, 'data': result}
            else:
                error_text = response.text[:200]
                print(f"❌ 发送登录链接失败: {response.status_code}")
                print(f"   响应: {error_text}")
                return {'success': False, 'error': error_text}
                
        except Exception as e:
            print(f"❌ 发送登录链接异常: {e}")
            return {'success': False, 'error': str(e)}
    
    def _wait_for_email(self, email_info: Dict[str, Any], max_wait_time: int = 120) -> Optional[str]:
        """
        等待并获取验证邮件（参考 complete_registration.py 的实现）
        
        Args:
            email_info: 邮箱信息字典，包含 email 和 email_id
            max_wait_time: 最长等待时间（秒）
        """
        email = email_info['email']
        email_id = email_info['email_id']
        
        print(f"📬 等待验证邮件 (超时: {max_wait_time}秒)...")
        print(f"   邮箱: {email}")
        print(f"   邮箱ID: {email_id}")
        
        start_time = time.time()
        check_count = 0
        check_interval = 5  # 每5秒检查一次
        
        while time.time() - start_time < max_wait_time:
            check_count += 1
            print(f"  第 {check_count} 次检查...")
            
            try:
                # 传递 to_email 参数以使用新的 emailList 接口
                # 指定 send_email 为 Warp 的发件人
                messages = self.moemail_client.get_messages(
                    email_id=email_id,
                    to_email=email,
                    send_email="noreply@auth.app.warp.dev",  # 特定的 Warp 验证邮件发送者
                    limit=10
                )
                
                if messages and len(messages) > 0:
                    print(f"📬 收到 {len(messages)} 封邮件")
                    
                    # 查找来自 Warp/Firebase 的邮件
                    for msg in messages:
                        subject = (msg.subject or '').lower()
                        sender = (msg.from_address or '').lower()
                        
                        # 检查是否是 Warp 验证邮件
                        if 'warp' in subject or 'sign' in subject or 'noreply@auth.app.warp.dev' in sender:
                            print(f"✅ 找到验证邮件")
                            print(f"   主题: {msg.subject}")
                            print(f"   发件人: {msg.from_address}")
                            
                            # 返回邮件HTML内容
                            if msg.html:
                                return msg.html
                            elif msg.content:
                                return msg.content
                
                # 等待后继续检查
                elapsed = int(time.time() - start_time)
                print(f"   已等待 {elapsed} 秒...")
                time.sleep(check_interval)
                
            except Exception as e:
                print(f"⚠️ 检查邮件时出错: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(check_interval)
        
        print(f"❌ 等待验证邮件超时")
        return None
    
    def _extract_oob_code(self, email_html: str) -> Optional[str]:
        """从邮件HTML中提取OOB验证码"""
        try:
            # 解码HTML实体
            decoded_html = html.unescape(email_html)
            
            # 方法1: 直接查找oobCode参数
            match = re.search(r'oobCode=([^&\s"\'<>]+)', decoded_html)
            if match:
                oob_code = match.group(1)
                print(f"✅ 提取到OOB验证码: {oob_code[:20]}...")
                return oob_code
            
            # 方法2: 查找完整的链接
            match = re.search(r'https://[^"\'<>\s]*oobCode=([^&\s"\'<>]+)', decoded_html)
            if match:
                oob_code = match.group(1)
                print(f"✅ 提取到OOB验证码: {oob_code[:20]}...")
                return oob_code
            
            print(f"❌ 未找到OOB验证码")
            return None
            
        except Exception as e:
            print(f"❌ 提取OOB验证码失败: {e}")
            return None
    
    def _complete_signin(self, email: str, oob_code: str) -> Dict[str, Any]:
        """使用OOB码完成登录"""
        try:
            print(f"🔐 使用OOB码完成登录...")
            
            url = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithEmailLink"
            
            payload = {
                "email": email,
                "oobCode": oob_code
            }
            
            response = self._make_firebase_request(url, payload)
            
            if response.status_code == 200:
                result = response.json()
                
                id_token = result.get('idToken')
                refresh_token = result.get('refreshToken')
                local_id = result.get('localId')
                
                print(f"✅ 登录成功!")
                print(f"   Local ID: {local_id}")
                
                return {
                    'success': True,
                    'email': email,
                    'local_id': local_id,
                    'id_token': id_token,
                    'refresh_token': refresh_token
                }
            else:
                error_text = response.text[:200]
                print(f"❌ 完成登录失败: {response.status_code}")
                return {'success': False, 'error': error_text}
                
        except Exception as e:
            print(f"❌ 完成登录异常: {e}")
            return {'success': False, 'error': str(e)}
    
    def _activate_warp_user(self, id_token: str, proxy: Optional[Dict] = None) -> Dict[str, Any]:
        """激活Warp用户"""
        try:
            import uuid
            print("🌐 激活Warp用户...")
            
            url = "https://app.warp.dev/graphql/v2"
            
            query = """
            mutation GetOrCreateUser($input: GetOrCreateUserInput!, $requestContext: RequestContext!) {
              getOrCreateUser(requestContext: $requestContext, input: $input) {
                __typename
                ... on GetOrCreateUserOutput {
                  uid
                  isOnboarded
                  __typename
                }
                ... on UserFacingError {
                  error {
                    message
                    __typename
                  }
                  __typename
                }
              }
            }
            """
            
            # 生成一个随机的 sessionId（UUID 格式）
            session_id = str(uuid.uuid4())
            
            data = {
                "operationName": "GetOrCreateUser",
                "variables": {
                    "input": {
                        "sessionId": session_id
                    },
                    "requestContext": {
                        "osContext": {},
                        "clientContext": {}
                    }
                },
                "query": query
            }
            
            headers = self._generate_random_headers()
            headers["Authorization"] = f"Bearer {id_token}"
            
            # 使用优化的会话（带有 DNS 解析器）而不是代理
            response = self.session.post(
                url,
                params={"op": "GetOrCreateUser"},
                json=data,
                headers=headers,
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                result = response.json()
                get_or_create_user = result.get("data", {}).get("getOrCreateUser", {})
                
                if get_or_create_user.get("__typename") == "GetOrCreateUserOutput":
                    uid = get_or_create_user.get("uid")
                    print(f"✅ Warp用户激活成功: UID={uid}")
                    return {"success": True, "uid": uid}
                else:
                    error = get_or_create_user.get("error", {}).get("message", "Unknown error")
                    print(f"❌ Warp激活失败: {error}")
                    return {"success": False, "error": error}
            else:
                error_text = response.text[:500]
                print(f"❌ Warp激活HTTP错误: {response.status_code}")
                print(f"   响应内容: {error_text}")
                return {"success": False, "error": f"HTTP {response.status_code}", "details": error_text}
                
        except Exception as e:
            print(f"❌ Warp激活异常: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_request_limit(self, id_token: str) -> Dict[str, Any]:
        """获取账户请求额度
        
        调用 GetRequestLimitInfo 接口获取账户的使用限制信息
        
        Args:
            id_token: Firebase ID Token
            
        Returns:
            包含额度信息的字典
        """
        if not id_token:
            return {"success": False, "error": "缺少Firebase ID Token"}
            
        try:
            import platform
            url = "https://app.warp.dev/graphql/v2"
            
            # 正确的查询结构：通过 user.requestLimitInfo 嵌套获取
            query = """
            query GetUser($requestContext: RequestContext!) {
              user(requestContext: $requestContext) {
                __typename
                ... on UserOutput {
                  user {
                    requestLimitInfo {
                      requestLimit
                      requestsUsedSinceLastRefresh
                      nextRefreshTime
                      isUnlimited
                    }
                  }
                }
                ... on UserFacingError {
                  error {
                    message
                  }
                }
              }
            }
            """
            
            # 获取 OS 信息
            os_name = platform.system()
            os_version = platform.release()
            os_category = "Desktop"
            
            data = {
                "operationName": "GetUser",
                "variables": {
                    "requestContext": {
                        "clientContext": {
                            "version": "v0.2025.08.27.08.11.stable_04"
                        },
                        "osContext": {
                            "category": os_category,
                            "linuxKernelVersion": None,
                            "name": os_name,
                            "version": os_version
                        }
                    }
                },
                "query": query
            }
            
            headers = self._generate_random_headers()
            headers["Authorization"] = f"Bearer {id_token}"
            headers["X-Warp-Client-Version"] = "v0.2025.09.03.08.11.stable_03"
            headers["X-Warp-Os-Category"] = "Windows"
            headers["X-Warp-Os-Name"] = "Windows"
            headers["X-Warp-Os-Version"] = "10 (19045)"
            
            print("📊 获取账户额度信息...")
            
            # 使用优化的会话（带有 DNS 解析器）
            response = self.session.post(
                url,
                params={"op": "GetUser"},
                json=data,
                headers=headers,
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # 检查是否有错误
                if "errors" in result:
                    error_msg = result["errors"][0].get("message", "Unknown error")
                    print(f"❌ GraphQL错误: {error_msg}")
                    return {"success": False, "error": error_msg}
                
                # 按照正确的嵌套结构解析：data.user.user.requestLimitInfo
                data_result = result.get("data", {})
                user_data = data_result.get("user", {})
                
                if user_data.get("__typename") == "UserOutput":
                    user_info = user_data.get("user", {})
                    limit_info = user_info.get("requestLimitInfo", {})
                    
                    if limit_info:
                        request_limit = limit_info.get("requestLimit")
                        requests_used = limit_info.get("requestsUsedSinceLastRefresh", 0)
                        next_refresh = limit_info.get("nextRefreshTime")
                        is_unlimited = limit_info.get("isUnlimited", False)
                        
                        remaining = request_limit - requests_used if request_limit else None
                        
                        print(f"✅ 账户额度信息:")
                        print(f"   📊 总额度: {request_limit}")
                        print(f"   📉 已使用: {requests_used}")
                        print(f"   📍 剩余额度: {remaining if remaining is not None else 'N/A'}")
                        print(f"   ♻️  下次刷新: {next_refresh}")
                        print(f"   ♾️  无限额度: {is_unlimited}")
                        
                        return {
                            "success": True,
                            "requestLimit": request_limit,
                            "requestsUsed": requests_used,
                            "requestsRemaining": remaining,
                            "nextRefreshTime": next_refresh,
                            "isUnlimited": is_unlimited
                        }
                elif user_data.get("__typename") == "UserFacingError":
                    error = user_data.get("error", {}).get("message", "Unknown error")
                    print(f"❌ 获取额度失败: {error}")
                    return {"success": False, "error": error}
                else:
                    print(f"❌ 响应中没有找到额度信息")
                    return {"success": False, "error": "未找到额度信息"}
            else:
                error_text = response.text[:500]
                print(f"❌ HTTP错误 {response.status_code}")
                print(f"   响应内容: {error_text}")
                return {"success": False, "error": f"HTTP {response.status_code}", "details": error_text}
                
        except Exception as e:
            print(f"❌ 获取额度异常: {e}")
            return {"success": False, "error": str(e)}
    
    def register_account(self) -> Dict[str, Any]:
        """
        完整的账号注册流程
        
        Returns:
            注册结果字典，包含账号信息或错误信息
        """
        start_time = time.time()
        
        try:
            print("\n" + "=" * 80)
            print("🚀 开始注册新账号（使用代理池）")
            print("=" * 80)
            
            # 步骤1: 创建邮箱
            email_info = self._create_email()
            if not email_info:
                return {
                    'success': False,
                    'error': '创建邮箱失败',
                    'duration': time.time() - start_time
                }
            
            email = email_info['email']
            
            # 步骤2: 发送登录链接
            signin_result = self._send_signin_link(email)
            if not signin_result['success']:
                return {
                    'success': False,
                    'error': f"发送登录链接失败: {signin_result['error']}",
                    'email': email,
                    'duration': time.time() - start_time
                }
            
            # 步骤3: 等待验证邮件
            email_html = self._wait_for_email(email_info)
            if not email_html:
                return {
                    'success': False,
                    'error': '未收到验证邮件',
                    'email': email,
                    'duration': time.time() - start_time
                }
            
            # 步骤4: 提取OOB验证码
            oob_code = self._extract_oob_code(email_html)
            if not oob_code:
                return {
                    'success': False,
                    'error': '提取验证码失败',
                    'email': email,
                    'duration': time.time() - start_time
                }
            
            # 步骤5: 完成登录
            signin_result = self._complete_signin(email, oob_code)
            if not signin_result['success']:
                return {
                    'success': False,
                    'error': f"完成登录失败: {signin_result['error']}",
                    'email': email,
                    'duration': time.time() - start_time
                }
            
            # 步骤6: 激活Warp用户
            activation_result = self._activate_warp_user(signin_result['id_token'])
            if not activation_result['success']:
                print(f"⚠️ Warp激活失败，但账号已创建")
            
            # 步骤7: 获取账户额度
            limit_result = self._get_request_limit(signin_result['id_token'])
            request_limit = None
            if limit_result['success']:
                request_limit = limit_result.get('requestLimit')
            else:
                print(f"⚠️ 获取额度失败，但账号已创建")
            
            # 返回完整结果
            duration = time.time() - start_time
            
            print("\n" + "=" * 80)
            print(f"✅ 账号注册成功! (耗时: {duration:.2f}秒)")
            print(f"   📧 邮箱: {signin_result['email']}")
            print(f"   🔑 Local ID: {signin_result['local_id']}")
            if activation_result['success']:
                print(f"   🌐 Warp UID: {activation_result['uid']}")
            if request_limit:
                if request_limit == 2500:
                    print(f"   🎉 账户额度: {request_limit} (高额度!)")
                else:
                    print(f"   📊 账户额度: {request_limit}")
            print("=" * 80 + "\n")
            
            return {
                'success': True,
                'email': signin_result['email'],
                'local_id': signin_result['local_id'],
                'id_token': signin_result['id_token'],
                'refresh_token': signin_result['refresh_token'],
                'warp_uid': activation_result.get('uid'),
                'request_limit': request_limit,
                'request_limit_info': limit_result if limit_result['success'] else None,
                'duration': duration,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"\n❌ 注册过程异常: {e}")
            return {
                'success': False,
                'error': str(e),
                'duration': time.time() - start_time
            }


def test_dns_registration():
    """测试使用 Cloudflare DNS 解析的注册功能"""
    print("=" * 80)
    print("🧪 测试使用 Cloudflare 优选 IP 的注册功能")
    print("=" * 80)
    
    try:
        # 创建 DNS 解析器
        print("\n1️⃣ 创建 DNS 解析器...")
        dns_resolver = CloudflareDNSResolver(use_api=True)
        print(f"   IP 池大小: {len(dns_resolver.cf_ips)} 个 IP")
        
        # 创建注册器
        print("\n2️⃣ 创建注册器...")
        registrator = ProxyRegistration(dns_resolver=dns_resolver)
        
        # 执行注册
        print("\n3️⃣ 执行注册...")
        result = registrator.register_account()
        
        # 打印结果
        print("\n" + "=" * 80)
        print("📊 注册结果:")
        print("=" * 80)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        return result['success']
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_compatibility():
    """测试向后兼容性"""
    print("=" * 80)
    print("🔧 测试向后兼容性")
    print("=" * 80)
    
    try:
        # 使用旧的 ProxyPool 类
        print("\n使用旧的 ProxyPool API...")
        proxy_pool = ProxyPool(use_cidr_ranges=False)  # 使用 API
        print(f"IP 池大小: {len(proxy_pool.cf_ips)} 个 IP")
        
        # 使用旧的构造参数
        registrator = ProxyRegistration(proxy_pool=proxy_pool)
        
        print("✅ 兼容性测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 兼容性测试失败: {e}")
        return False


if __name__ == "__main__":
    import sys
    
    print("🌟" * 40)
    print("Cloudflare 优选 IP 注册测试")
    print("🌟" * 40)
    
    # 选择测试模式
    if len(sys.argv) > 1 and sys.argv[1] == "--compatibility":
        print("\n执行兼容性测试...")
        test_compatibility()
    else:
        print("\n执行注册测试...")
        test_dns_registration()
    
    print("\n" + "🎉" * 40)
    print("测试完成！")
    print("🎉" * 40)

