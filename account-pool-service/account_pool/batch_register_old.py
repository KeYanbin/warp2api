#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账号批量注册器
严格基于warpzhuce项目的注册逻辑，实现Warp账号的批量注册和激活
"""

import asyncio
import time
import re
import html
import random
import string
import requests
import urllib3
import threading
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from threading import RLock

try:
    from config import config
    from .database import Account, get_database
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import config
    from account_pool.database import Account, get_database

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@dataclass
class TempEmail:
    """临时邮箱数据类"""
    id: str
    address: str
    created_at: str
    expires_at: str = ""


@dataclass
class EmailMessage:
    """邮件消息数据类"""
    id: str
    from_address: str
    subject: str
    content: str
    html: str
    received_at: int


class MoeMailClient:
    """MoeMail API客户端（基于warpzhuce实现）"""
    
    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = (base_url or config.MOEMAIL_URL).rstrip('/')
        self.api_key = api_key or config.MOEMAIL_API_KEY
        self.session = requests.Session()
        
        # 设置请求头
        self.session.headers.update({
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'User-Agent': 'WarpRegister/1.0'
        })
    
    def create_email(self, name: str = None, domain: str = "gllovioo.ggff.net", expiry_hours: int = 1) -> TempEmail:
        """创建临时邮箱"""
        expiry_map = {1: 3600000, 24: 86400000, 168: 604800000, 0: 0}
        expiry_time = expiry_map.get(expiry_hours, 3600000)
        
        data = {"expiryTime": expiry_time, "domain": domain}
        if name:
            data["name"] = name
        
        try:
            response = self.session.post(f"{self.base_url}/api/emails/generate", json=data)
            response.raise_for_status()
            result = response.json()
            
            return TempEmail(
                id=result["id"],
                address=result["email"],
                created_at=time.strftime("%Y-%m-%d %H:%M:%S")
            )
        except Exception as e:
            # 如果API失败，使用备用域名生成邮箱
            if not name:
                name = self._generate_random_prefix()
            return TempEmail(
                id=f"backup_{name}_{int(time.time())}",
                address=f"{name}@{domain}",
                created_at=time.strftime("%Y-%m-%d %H:%M:%S")
            )
    
    def get_messages(self, email_id: str, limit: int = 10) -> List[EmailMessage]:
        """获取邮件列表"""
        try:
            params = {"limit": limit, "sort": "desc"}
            response = self.session.get(f"{self.base_url}/api/emails/{email_id}/messages", params=params)
            
            if response.status_code == 404:
                response = self.session.get(f"{self.base_url}/api/emails/{email_id}")
            
            response.raise_for_status()
            result = response.json()
            
            messages = []
            message_data = result.get("messages", result.get("data", []))
            
            for msg_data in message_data:
                messages.append(EmailMessage(
                    id=msg_data.get("id", msg_data.get("messageId", "")),
                    from_address=msg_data.get("from_address", msg_data.get("from", "")),
                    subject=msg_data.get("subject", ""),
                    content=msg_data.get("content", msg_data.get("text", "")),
                    html=msg_data.get("html", msg_data.get("htmlContent", "")),
                    received_at=msg_data.get("received_at", msg_data.get("timestamp", int(time.time() * 1000)))
                ))
            
            messages.sort(key=lambda x: x.received_at, reverse=True)
            return messages
        except Exception:
            return []
    
    def _generate_random_prefix(self) -> str:
        """生成随机邮箱前缀"""
        words = ['alpha', 'beta', 'gamma', 'nova', 'star', 'moon', 'sun', 'sky', 'wind', 'fire']
        word = random.choice(words)
        chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return f"{word}{chars}"


class FirebaseAPIPool:
    """基于warpzhuce的Firebase API密钥池管理器"""
    
    def __init__(self):
        self.api_keys = config.get_firebase_api_keys()
        self.current_key_index = 0
        self.key_usage_stats = {}
        self.key_cooldowns = {}
        self.lock = threading.Lock()
        
        # 初始化使用统计
        for key in self.api_keys:
            self.key_usage_stats[key] = {
                'total_requests': 0,
                'failed_requests': 0,
                'success_rate': 1.0
            }
            self.key_cooldowns[key] = None
    
    def get_next_api_key(self) -> str:
        """获取下一个可用的API密钥"""
        with self.lock:
            # 查找可用的密钥（不在冷却期）
            current_time = datetime.now()
            available_keys = []
            
            for i, key in enumerate(self.api_keys):
                cooldown_until = self.key_cooldowns.get(key)
                if cooldown_until is None or current_time > cooldown_until:
                    available_keys.append((i, key))
            
            if not available_keys:
                # 如果所有密钥都在冷却期，选择冷却时间最短的
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
                
                if stats['total_requests'] > 0:
                    success_requests = stats['total_requests'] - stats['failed_requests']
                    stats['success_rate'] = success_requests / stats['total_requests']
                
                # 设置冷却时间
                cooldown_minutes = {'rate_limit': 15, 'ssl_error': 5, 'unknown': 1}.get(error_type, 1)
                if cooldown_minutes > 0:
                    self.key_cooldowns[api_key] = datetime.now() + timedelta(minutes=cooldown_minutes)
    
    def mark_key_success(self, api_key: str):
        """标记密钥成功"""
        with self.lock:
            if api_key in self.key_usage_stats:
                stats = self.key_usage_stats[api_key]
                stats['total_requests'] += 1
                
                success_requests = stats['total_requests'] - stats['failed_requests']
                stats['success_rate'] = success_requests / stats['total_requests']
                
                # 清除冷却时间
                self.key_cooldowns[api_key] = None


class BatchRegister:
    """账号批量注册器（基于warpzhuce逻辑，优化并发安全）
    
    特性:
    - 线程安全的会话管理
    - SSL连接池优化
    - 智能重试机制
    - 并发注册支持
    """
    
    def __init__(self, max_workers: int = 3):
        """初始化注册器
        
        Args:
            max_workers: 最大并发工作线程数
        """
        self.firebase_pool = FirebaseAPIPool()
        self.moemail_client = MoeMailClient()
        self.db = get_database()
        self.max_workers = max_workers
        
        # 线程安全锁
        self._session_lock = RLock()
        self._thread_sessions = {}  # 每个线程独立的session
        
        # 创建主session
        self.master_session = self._create_optimized_session()
        
        print("🤖 账号批量注册器初始化完成")
        print(f"⚡ 最大并发数: {max_workers}")
        print(f"🔒 SSL验证已禁用")
        print(f"🔄 优化的重试机制已启用")
    
    def _create_optimized_session(self) -> requests.Session:
        """创建优化的requests会话"""
        session = requests.Session()
        
        # 禁用SSL验证
        session.verify = False
        
        # 配置重试策略
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
        )
        
        # 配置HTTP适配器
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _get_thread_session(self) -> requests.Session:
        """获取当前线程的session"""
        thread_id = threading.get_ident()
        
        with self._session_lock:
            if thread_id not in self._thread_sessions:
                self._thread_sessions[thread_id] = self._create_optimized_session()
            return self._thread_sessions[thread_id]
    
    def _make_firebase_request(self, url: str, method: str = "POST", data: Dict = None, max_retries: int = 3) -> requests.Response:
        """发起Firebase API请求（线程安全优化版）"""
        headers = self._generate_random_headers()
        session = self._get_thread_session()
        thread_id = threading.get_ident()
        
        for attempt in range(max_retries):
            api_key = self.firebase_pool.get_next_api_key()
            separator = '&' if '?' in url else '?'
            full_url = f"{url}{separator}key={api_key}"
            
            try:
                print(f"🌐 Firebase请求 [线程{thread_id}] (尝试 {attempt + 1}/{max_retries}): {method} {url[:50]}...")
                
                if method.upper() == "POST":
                    response = session.post(full_url, json=data, headers=headers, timeout=30)
                else:
                    response = session.get(full_url, headers=headers, timeout=30)
                
                # 处理响应
                if response.status_code == 200:
                    self.firebase_pool.mark_key_success(api_key)
                    print(f"✅ Firebase请求成功 [线程{thread_id}]: {response.status_code}")
                    return response
                    
                elif response.status_code == 400:
                    # 处理400错误（可能是账号已存在或无效请求）
                    error_text = response.text
                    if "EMAIL_EXISTS" in error_text or "WEAK_PASSWORD" in error_text:
                        print(f"⚠️ 账号已存在或密码不符要求 [线程{thread_id}]: {response.status_code}")
                        return response  # 返回400响应以便上层处理
                    else:
                        self.firebase_pool.mark_key_failed(api_key, "bad_request")
                        print(f"⚠️ Firebase请求错误 [线程{thread_id}]: {response.status_code} - {error_text[:100]}...")
                        
                elif response.status_code == 429:
                    self.firebase_pool.mark_key_failed(api_key, "rate_limit")
                    print(f"⚠️ API密钥频率限制 [线程{thread_id}]: {response.status_code}")
                    
                elif response.status_code in [500, 502, 503, 504]:
                    self.firebase_pool.mark_key_failed(api_key, "server_error")
                    print(f"⚠️ 服务器错误 [线程{thread_id}]: {response.status_code}")
                    
                else:
                    self.firebase_pool.mark_key_failed(api_key, "unknown")
                    print(f"⚠️ Firebase请求失败 [线程{thread_id}]: {response.status_code}")
                
                # 重试逻辑
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt + random.uniform(0, 1)
                    print(f"⏳ 等待 {wait_time:.1f} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    return response
                    
            except requests.exceptions.SSLError as e:
                self.firebase_pool.mark_key_failed(api_key, "ssl_error")
                print(f"🔒 SSL错误 [线程{thread_id}] (尝试 {attempt + 1}): {str(e)[:100]}...")
                if attempt == max_retries - 1:
                    print(f"🚫 SSL错误太多，跳过该请求")
                    raise Exception(f"SSL错误: {str(e)[:100]}...")
                    
            except requests.exceptions.ConnectionError as e:
                self.firebase_pool.mark_key_failed(api_key, "connection_error")
                print(f"🌐 连接错误 [线程{thread_id}] (尝试 {attempt + 1}): {str(e)[:100]}...")
                if attempt == max_retries - 1:
                    print(f"🚫 连接错误太多，跳过该请求")
                    raise Exception(f"连接错误: {str(e)[:100]}...")
                    
            except requests.exceptions.Timeout as e:
                self.firebase_pool.mark_key_failed(api_key, "timeout")
                print(f"⏰ 请求超时 [线程{thread_id}] (尝试 {attempt + 1}): {str(e)[:100]}...")
                if attempt == max_retries - 1:
                    print(f"🚫 超时错误太多，跳过该请求")
                    raise Exception(f"请求超时: {str(e)[:100]}...")
                    
            except Exception as e:
                self.firebase_pool.mark_key_failed(api_key, "unexpected_error")
                print(f"❓ 未知错误 [线程{thread_id}] (尝试 {attempt + 1}): {str(e)[:100]}...")
                if attempt == max_retries - 1:
                    print(f"🚫 未知错误太多，跳过该请求")
                    raise Exception(f"未知错误: {str(e)[:100]}...")
        
        raise Exception("所有重试都失败了")
    
    def _generate_random_headers(self) -> Dict[str, str]:
        """生成随机浏览器headers"""
        chrome_version = f"{random.randint(120, 131)}.0.{random.randint(6000, 6999)}.{random.randint(100, 999)}"
        webkit_version = f"537.{random.randint(30, 40)}"
        os_version = random.choice(["10_15_7", "11_0_1", "12_0_1", "13_0_1", "14_0_0"])
        
        user_agent = f"Mozilla/5.0 (Macintosh; Intel Mac OS X {os_version}) AppleWebKit/{webkit_version} (KHTML, like Gecko) Chrome/{chrome_version} Safari/{webkit_version}"
        
        return {
            'Content-Type': 'application/json',
            'User-Agent': user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache'
        }
    
    def register_accounts_concurrent(self, count: int = 5) -> List[Dict[str, Any]]:
        """并发批量注册账号
        
        Args:
            count: 要注册的账号数量
            
        Returns:
            注册结果列表
        """
        print(f"\n🚀 开始并发批量注册 {count} 个账号...")
        
        results = []
        failed_count = 0
        success_count = 0
        
        # 使用线程池进行并发注册
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有注册任务
            futures = []
            for i in range(count):
                future = executor.submit(self._register_single_account, i + 1)
                futures.append(future)
            
            # 收集结果
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=300)  # 5分钟超时
                    results.append(result)
                    
                    if result['success']:
                        success_count += 1
                        print(f"✅ 账号 #{result['index']} 注册成功: {result.get('email', 'N/A')}")
                    else:
                        failed_count += 1
                        print(f"❌ 账号 #{result['index']} 注册失败: {result.get('error', 'Unknown')}")
                        
                except Exception as e:
                    failed_count += 1
                    error_result = {
                        'success': False,
                        'index': -1,
                        'error': f'任务异常: {str(e)}',
                        'timestamp': datetime.now().isoformat()
                    }
                    results.append(error_result)
                    print(f"❌ 注册任务异常: {e}")
        
        print(f"\n📈 批量注册完成:")
        print(f"   ✅ 成功: {success_count} 个")
        print(f"   ❌ 失败: {failed_count} 个")
        print(f"   📁 总计: {len(results)} 个")
        
        return results
    
    def _register_single_account(self, index: int) -> Dict[str, Any]:
        """注册单个账号（线程安全）
        
        Args:
            index: 账号编号
            
        Returns:
            注册结果
        """
        thread_id = threading.get_ident()
        start_time = time.time()
        
        try:
            print(f"🔄 [线程{thread_id}] 开始注册账号 #{index}...")
            
            # 1. 创建临时邮箱（使用配置的前缀）
            email_prefix = f"{config.EMAIL_PREFIX}{random.randint(1000, 9999)}"
            temp_email = self.moemail_client.create_email(name=email_prefix, domain="gllovioo.ggff.net")
            if not temp_email or not temp_email.address:
                return {
                    'success': False,
                    'index': index,
                    'error': '创建临时邮箱失败',
                    'timestamp': datetime.now().isoformat(),
                    'duration': time.time() - start_time
                }
            
            email_address = temp_email.address
            print(f"📧 [线程{thread_id}] 创建邮箱: {email_address}")
            
            # 2. 发送邮箱登录请求
            signin_result = self._send_email_signin_request_sync(email_address)
            if not signin_result['success']:
                return {
                    'success': False,
                    'index': index,
                    'email': email_address,
                    'error': f'发送邮箱登录请求失败: {signin_result["error"]}',
                    'timestamp': datetime.now().isoformat(),
                    'duration': time.time() - start_time
                }
            
            print(f"✅ [线程{thread_id}] 邮箱登录请求已发送: {email_address}")
            
            # 3. 等待验证邮件
            email_result = self.wait_for_verification_email(temp_email.id, timeout=120)
            if not email_result:
                return {
                    'success': False,
                    'index': index,
                    'email': email_address,
                    'error': '未收到验证邮件',
                    'timestamp': datetime.now().isoformat(),
                    'duration': time.time() - start_time
                }
            
            # 4. 处理验证链接
            link_params = self.process_verification_link(email_result["verification_link"])
            if "error" in link_params:
                return {
                    'success': False,
                    'index': index,
                    'email': email_address,
                    'error': f'处理验证链接失败: {link_params["error"]}',
                    'timestamp': datetime.now().isoformat(),
                    'duration': time.time() - start_time
                }
            
            # 5. 完成邮箱登录
            signin_result = self.complete_email_signin(email_address, link_params["oob_code"])
            if not signin_result["success"]:
                return {
                    'success': False,
                    'index': index,
                    'email': email_address,
                    'error': f'完成登录失败: {signin_result.get("error")}',
                    'timestamp': datetime.now().isoformat(),
                    'duration': time.time() - start_time
                }
            
            # 6. 激活Warp用户（关键步骤！）
            print(f"🌐 [线程{thread_id}] 激活Warp用户: {signin_result['email']}")
            warp_activation = self._activate_warp_user(signin_result.get('id_token', ''), thread_id)
            
            # 只有Warp激活成功才保存账号，确保数据库中的账号都是可用的
            if not warp_activation["success"]:
                error_msg = f'Warp用户激活失败: {warp_activation.get("error")}'
                print(f"❌ [线程{thread_id}] {error_msg}")
                return {
                    'success': False,
                    'index': index,
                    'email': email_address,
                    'error': error_msg,
                    'timestamp': datetime.now().isoformat(),
                    'duration': time.time() - start_time
                }
            
            print(f"✅ [线程{thread_id}] Warp用户激活成功: UID {warp_activation.get('uid')}")
            
            # 7. 保存完全激活成功的账号到数据库
            # 注意：Warp UID就是local_id（Firebase用户ID）
            account = Account(
                email=signin_result["email"],
                local_id=signin_result.get('local_id', ''),  # 这个就是Warp UID
                id_token=signin_result.get('id_token', ''),
                refresh_token=signin_result.get('refresh_token', ''),
                status='available'  # 只有激活成功的账号才保存
            )
            
            # 保存到数据库
            saved = self._save_account_to_db(account)
            if not saved:
                return {
                    'success': False,
                    'index': index,
                    'email': email_address,
                    'error': '保存账号到数据库失败',
                    'timestamp': datetime.now().isoformat(),
                    'duration': time.time() - start_time
                }
            
            duration = time.time() - start_time
            print(f"✅ [线程{thread_id}] 账号 #{index} 注册成功！用时: {duration:.1f}秒")
            
            return {
                'success': True,
                'index': index,
                'email': email_address,
                'warp_uid': account.local_id,  # Warp UID
                'timestamp': datetime.now().isoformat(),
                'duration': duration
            }
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            print(f"❌ [线程{thread_id}] 账号 #{index} 注册失败: {error_msg}")
            
            return {
                'success': False,
                'index': index,
                'error': error_msg,
                'timestamp': datetime.now().isoformat(),
                'duration': duration
            }
    
    def _send_email_signin_request_sync(self, email_address: str) -> Dict[str, Any]:
        """同步发送邮箱登录请求"""
        url = "https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode"
        payload = {
            "requestType": "EMAIL_SIGNIN",
            "email": email_address,
            "clientType": "CLIENT_TYPE_WEB",
            "continueUrl": "https://app.warp.dev/login",
            "canHandleCodeInApp": True
        }
        
        try:
            response = self._make_firebase_request(url, "POST", payload)
            
            if response.status_code == 200:
                response_data = response.json()
                return {"success": True, "response": response_data}
            elif response.status_code == 400:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Unknown error')
                if 'EMAIL_NOT_FOUND' in error_message:
                    return {"success": False, "error": "邮箱地址不存在"}
                elif 'INVALID_EMAIL' in error_message:
                    return {"success": False, "error": "邮箱地址无效"}
                else:
                    return {"success": False, "error": f"Firebase错误: {error_message}"}
            else:
                return {"success": False, "error": f"HTTP错误: {response.status_code}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def wait_for_verification_email(self, email_id: str, timeout: int = 120) -> Optional[Dict[str, Any]]:
        """等待验证邮件（基于warpzhuce项目的真实实现）"""
        thread_id = threading.get_ident()
        print(f"📬 [线程{thread_id}] 等待验证邮件 (超时: {timeout}秒)...")
        
        start_time = time.time()
        check_count = 0
        
        while time.time() - start_time < timeout:
            check_count += 1
            print(f"  🔍 [线程{thread_id}] 第 {check_count} 次检查...")
            
            try:
                messages = self.moemail_client.get_messages(email_id)
                
                if messages:
                    for msg in messages:
                        # warpzhuce的匹配逻辑：检查主题中是否包含'warp'或'sign'
                        if 'warp' in msg.subject.lower() or 'sign' in msg.subject.lower():
                            print(f"  ✅ [线程{thread_id}] 找到验证邮件: {msg.subject}")
                            
                            # 使用warpzhuce的链接提取逻辑
                            link_pattern = r'href=["\\\']([^"\\\']+)["\\\']'
                            matches = re.findall(link_pattern, msg.html)
                            
                            verification_link = None
                            for link in matches:
                                if 'firebaseapp.com' in link and 'auth/action' in link:
                                    verification_link = html.unescape(link)
                                    break
                            
                            if verification_link:
                                print(f"  ✅ [线程{thread_id}] 找到验证链接")
                                return {
                                    "success": True,
                                    "subject": msg.subject,
                                    "verification_link": verification_link,
                                    "received_at": msg.received_at
                                }
                
                time.sleep(5)  # warpzhuce使用5秒间隔
                
            except Exception as e:
                print(f"  ⚠️ [线程{thread_id}] 检查邮件时出错: {e}")
                time.sleep(5)
        
        print(f"  ❌ [线程{thread_id}] 等待验证邮件超时")
        return None
    
    def process_verification_link(self, verification_link: str) -> Dict[str, Any]:
        """处理验证链接，提取参数（基于warpzhuce）"""
        thread_id = threading.get_ident()
        print(f"  🔍 [线程{thread_id}] 处理验证链接...")
        
        try:
            parsed = urlparse(verification_link)
            params = parse_qs(parsed.query)
            
            result = {
                "api_key": params.get('apiKey', [None])[0],
                "mode": params.get('mode', [None])[0],
                "oob_code": params.get('oobCode', [None])[0],
                "continue_url": params.get('continueUrl', [None])[0],
                "lang": params.get('lang', [None])[0]
            }
            
            print(f"  ✅ [线程{thread_id}] 验证链接参数提取成功")
            if result['oob_code']:
                print(f"    OOB Code: {result['oob_code'][:20]}...")
            
            return result
            
        except Exception as e:
            print(f"  ❌ [线程{thread_id}] 处理验证链接失败: {e}")
            return {"error": str(e)}
    
    def complete_email_signin(self, email_address: str, oob_code: str) -> Dict[str, Any]:
        """完成邮箱登录流程（基于warpzhuce）"""
        thread_id = threading.get_ident()
        print(f"  🔐 [线程{thread_id}] 完成邮箱登录: {email_address}")
        
        try:
            url = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithEmailLink"
            
            payload = {
                "email": email_address,
                "oobCode": oob_code
            }
            
            print(f"    邮箱: {email_address}")
            print(f"    OOB Code: {oob_code[:20]}...")
            
            # 添加随机延迟模拟真实用户行为（warpzhuce逻辑）
            delay = random.uniform(1.5, 3.5)
            time.sleep(delay)
            
            response = self._make_firebase_request(url, "POST", payload, max_retries=3)
            
            print(f"    响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                response_data = response.json()
                print(f"  ✅ [线程{thread_id}] 邮箱登录完成")
                
                # 提取关键信息（基于warpzhuce逻辑）
                is_new_user = response_data.get("isNewUser", True)
                result = {
                    "success": True,
                    "id_token": response_data.get("idToken"),
                    "refresh_token": response_data.get("refreshToken"),
                    "expires_in": response_data.get("expiresIn"),
                    "local_id": response_data.get("localId"),
                    "email": response_data.get("email"),
                    "is_new_user": is_new_user,
                    "registered": not is_new_user,  # 兼容旧字段
                    "raw_response": response_data
                }
                
                print(f"    用户ID: {result['local_id']}")
                print(f"    邮箱: {result['email']}")
                print(f"    是否新用户: {result['is_new_user']}")
                print(f"    Token过期时间: {result['expires_in']}秒")
                
                return result
            else:
                error_text = response.text
                print(f"  ❌ [线程{thread_id}] 登录失败: {error_text}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": error_text
                }
                
        except Exception as e:
            print(f"  ❌ [线程{thread_id}] 完成登录异常: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _activate_warp_user(self, id_token: str, thread_id: int = None) -> Dict[str, Any]:
        """激活Warp用户（基于warpzhuce的create_warp_user逻辑）
        
        这是关键步骤：使用Firebase ID Token调用Warp GraphQL API创建或获取用户
        解决401 Unauthorized "User not in context"错误
        
        Args:
            id_token: Firebase ID Token
            thread_id: 线程ID（用于日志显示）
            
        Returns:
            包含激活结果的字典
        """
        if not thread_id:
            thread_id = threading.get_ident()
            
        if not id_token:
            return {
                "success": False,
                "error": "缺少Firebase ID Token"
            }
            
        try:
            url = "https://app.warp.dev/graphql/v2"
            
            # Warp GraphQL查询（来自warpzhuce/src/core/warp_user_manager.py）
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
            import uuid
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
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {id_token}",
                "User-Agent": self._generate_warp_user_agent()
            }
            
            print(f"  🌐 [线程{thread_id}] 调用Warp GraphQL API激活用户...")
            
            # 使用线程安全的session发送请求
            session = self._get_thread_session()
            response = session.post(
                url,
                params={"op": "GetOrCreateUser"},
                json=data,
                headers=headers,
                timeout=30
            )
            
            print(f"    响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                get_or_create_user = result.get("data", {}).get("getOrCreateUser", {})
                
                if get_or_create_user.get("__typename") == "GetOrCreateUserOutput":
                    uid = get_or_create_user.get("uid")
                    is_onboarded = get_or_create_user.get("isOnboarded", False)
                    
                    print(f"  ✅ [线程{thread_id}] Warp用户激活成功:")
                    print(f"    Warp UID: {uid} (就是local_id)")
                    print(f"    已入门: {is_onboarded}")
                    
                    return {
                        "success": True,
                        "uid": uid,  # 这个应该和local_id相同
                        "isOnboarded": is_onboarded
                    }
                    
                elif get_or_create_user.get("__typename") == "UserFacingError":
                    error_msg = get_or_create_user.get("error", {}).get("message", "未知GraphQL错误")
                    print(f"  ❌ [线程{thread_id}] Warp GraphQL错误: {error_msg}")
                    return {
                        "success": False,
                        "error": f"GraphQL错误: {error_msg}"
                    }
                else:
                    print(f"  ❌ [线程{thread_id}] 未知的GraphQL响应类型: {get_or_create_user.get('__typename')}")
                    return {
                        "success": False,
                        "error": f"未知响应类型: {get_or_create_user.get('__typename')}"
                    }
                    
            elif response.status_code == 401:
                print(f"  ❌ [线程{thread_id}] Firebase Token已过期或无效 (401)")
                return {
                    "success": False,
                    "error": "Firebase Token已过期或无效"
                }
                
            elif response.status_code == 403:
                print(f"  ❌ [线程{thread_id}] Token权限不足或账户被禁用 (403)")
                return {
                    "success": False,
                    "error": "Token权限不足或账户被禁用"
                }
                
            elif response.status_code >= 500:
                print(f"  ❌ [线程{thread_id}] Warp服务器错误 ({response.status_code})")
                return {
                    "success": False,
                    "error": f"Warp服务器错误 ({response.status_code})"
                }
            else:
                error_text = response.text[:200] if response.text else "无响应内容"
                print(f"  ❌ [线程{thread_id}] Warp API请求失败: {response.status_code}")
                print(f"    响应内容: {error_text}...")
                return {
                    "success": False,
                    "error": f"HTTP错误 {response.status_code}: {error_text}"
                }
                
        except requests.exceptions.Timeout:
            print(f"  ⏰ [线程{thread_id}] Warp API请求超时")
            return {
                "success": False,
                "error": "Warp API请求超时"
            }
            
        except requests.exceptions.ConnectionError as e:
            print(f"  🌐 [线程{thread_id}] 网络连接失败: {str(e)[:100]}...")
            return {
                "success": False,
                "error": f"网络连接失败: {str(e)[:100]}..."
            }
            
        except Exception as e:
            print(f"  ❌ [线程{thread_id}] Warp用户激活异常: {str(e)[:100]}...")
            return {
                "success": False,
                "error": f"激活异常: {str(e)[:100]}..."
            }
    
    def _get_request_limit(self, id_token: str, thread_id: int = None) -> Dict[str, Any]:
        """获取账户请求额度"""
        if not thread_id:
            thread_id = threading.get_ident()
            
        if not id_token:
            return {"success": False, "error": "缺少Firebase ID Token"}
            
        try:
            url = "https://app.warp.dev/graphql/v2"
            
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
            
            import platform
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
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {id_token}",
                "User-Agent": self._generate_warp_user_agent(),
                "X-warp-client-version": "v0.2025.08.27.08.11.stable_04",
                "X-warp-os-category": "Desktop",
                "X-warp-manager-request": "true"
            }
            
            print(f"  📊 [线程{thread_id}] 获取账户额度信息...")
            
            session = self._get_thread_session()
            response = session.post(
                url,
                params={"op": "GetUser"},
                json=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if "errors" in result:
                    error_msg = result["errors"][0].get("message", "Unknown error")
                    return {"success": False, "error": error_msg}
                
                data_result = result.get("data", {})
                user_data = data_result.get("user", {})
                
                if user_data.get("__typename") == "UserOutput":
                    user_info = user_data.get("user", {})
                    limit_info = user_info.get("requestLimitInfo", {})
                    
                    if limit_info:
                        request_limit = limit_info.get("requestLimit")
                        requests_used = limit_info.get("requestsUsedSinceLastRefresh", 0)
                        
                        print(f"  ✅ [线程{thread_id}] 账户额度: {request_limit} (已用: {requests_used})")
                        
                        return {
                            "success": True,
                            "requestLimit": request_limit,
                            "requestsUsed": requests_used
                        }
                elif user_data.get("__typename") == "UserFacingError":
                    error = user_data.get("error", {}).get("message", "Unknown error")
                    return {"success": False, "error": error}
                else:
                    return {"success": False, "error": "未找到额度信息"}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _generate_warp_user_agent(self) -> str:
        """生成Warp专用的User-Agent"""
        # 优先尝试随机生成，失败则使用默认值
        try:
            chrome_version = f"{random.randint(120, 131)}.0.{random.randint(6000, 6999)}.{random.randint(100, 999)}"
            webkit_version = f"537.{random.randint(30, 40)}"
            os_version = random.choice(["10_15_7", "11_0_1", "12_0_1", "13_0_1", "14_0_0"])
            return f"Mozilla/5.0 (Macintosh; Intel Mac OS X {os_version}) AppleWebKit/{webkit_version} (KHTML, like Gecko) Chrome/{chrome_version} Safari/{webkit_version}"
        except:
            return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6000.900 Safari/537.36"
    
    def _save_account_to_db(self, account: Account) -> bool:
        """保存账号到数据库"""
        try:
            # 直接保存Account对象到数据库
            result = self.db.add_account(account)
            if result:
                print(f"✅ 账号已保存: {account.email} (Warp UID: {account.local_id})")
            return result
            
        except Exception as e:
            print(f"⚠️ 保存账号到数据库失败: {e}")
            return False
    
    def cleanup_thread_sessions(self):
        """清理线程会话缓存"""
        with self._session_lock:
            for session in self._thread_sessions.values():
                try:
                    session.close()
                except:
                    pass
            self._thread_sessions.clear()
            print("🗑️ 已清理线程会话缓存")


# 全局注册器实例
_register_instance = None


def get_batch_register() -> BatchRegister:
    """获取批量注册器实例（单例模式）"""
    global _register_instance
    if _register_instance is None:
        _register_instance = BatchRegister(max_workers=3)
    return _register_instance


if __name__ == "__main__":
    # 简单测试
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    registerer = BatchRegister(max_workers=2)
    
    print("\n🧪 开始测试批量注册器...")
    
    try:
        # 测试注册2个账号
        results = registerer.register_accounts_concurrent(2)
        
        print(f"\n📈 测试结果:")
        for result in results:
            if result['success']:
                print(f"  ✅ #{result['index']}: {result.get('email', 'N/A')} (用时: {result.get('duration', 0):.1f}s)")
            else:
                print(f"  ❌ #{result['index']}: {result.get('error', 'Unknown error')}")
    
    except KeyboardInterrupt:
        print("\n🛹 用户中断")
    except Exception as e:
        print(f"\n🚨 测试异常: {e}")
    finally:
        # 清理资源
        registerer.cleanup_thread_sessions()
