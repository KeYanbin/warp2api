#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账号批量注册器 - 直接使用warpzhuce的完整注册逻辑
"""

import sys
import os
import time
import random
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import requests

# 添加当前目录到系统路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入warpzhuce的核心模块
from complete_registration import CompleteScriptRegistration
from firebase_api_pool import FirebaseAPIPool, make_firebase_request
from moemail_client import MoeMailClient
from simple_config import load_config

# 导入数据库
try:
    from database import Account, get_database
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from account_pool.database import Account, get_database


class BatchRegister:
    """使用warpzhuce完整逻辑的批量注册器"""
    
    def __init__(self, max_workers: int = 20):
        """初始化注册器

        Args:
            max_workers: 最大并发工作线程数（建议值：3-10）
        """
        self.max_workers = max_workers
        self.db = get_database()
        
        # 加载配置
        self.config = load_config()
        if not self.config:
            print("❌ 无法加载配置，使用默认配置")
            self.config = {
                'moemail_url': 'https://api.emailnb.com',
                'moemail_api_key': 'your_api_key',
                'firebase_api_keys': ['AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs'],
                'email_expiry_hours': 1
            }
        
        print("🤖 批量注册器初始化完成")
        print(f"⚡ 最大并发数: {max_workers}")
        print(f"📧 邮箱服务: {self.config.get('moemail_url', 'N/A')}")
        print(f"🔑 Firebase密钥数: {len(self.config.get('firebase_api_keys', []))}")
    
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
        high_quota_count = 0  # 统计2500额度账号
        normal_quota_count = 0  # 统计150额度账号
        
        # 使用线程池进行并发注册
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有注册任务
            futures = []
            for i in range(count):
                future = executor.submit(self._register_single_account, i + 1)
                futures.append(future)
                # 稍微延迟提交，避免同时发送太多请求
                time.sleep(random.uniform(0.5, 1.5))
            
            # 收集结果
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=300)  # 5分钟超时
                    results.append(result)
                    
                    if result['success']:
                        success_count += 1
                        email = result.get('email', 'N/A')
                        limit = result.get('request_limit', 'N/A')
                        
                        # 统计额度类型
                        if limit == 2500:
                            high_quota_count += 1
                            print(f"✅ 账号 #{result['index']} 注册成功: {email} (🎉 高额度: {limit})")
                        elif limit == 150:
                            normal_quota_count += 1
                            print(f"✅ 账号 #{result['index']} 注册成功: {email} (📊 普通额度: {limit})")
                        else:
                            print(f"✅ 账号 #{result['index']} 注册成功: {email} (📊 额度: {limit})")
                    else:
                        failed_count += 1
                        print(f"❌ 账号 #{result['index']} 注册失败: {result.get('error', 'Unknown')}")
                        
                except Exception as e:
                    failed_count += 1
                    error_result = {
                        'success': False,
                        'index': -1,
                        'error': f'任务异常: {str(e)}',
                        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    results.append(error_result)
                    print(f"❌ 注册任务异常: {e}")
        
        print(f"\n📈 批量注册完成:")
        print(f"   ✅ 成功: {success_count} 个")
        print(f"   ❌ 失败: {failed_count} 个")
        print(f"   📁 总计: {len(results)} 个")
        print(f"\n🎯 额度统计:")
        print(f"   🎉 高额度(2500): {high_quota_count} 个")
        print(f"   📊 普通额度(150): {normal_quota_count} 个")
        if high_quota_count > 0:
            percentage = (high_quota_count / success_count * 100) if success_count > 0 else 0
            print(f"   📈 高额度比例: {percentage:.1f}%")
        
        return results

    def _activate_warp_user(self, id_token: str) -> Dict[str, Any]:
        """激活Warp用户
        
        使用Firebase ID Token调用Warp GraphQL API创建或获取用户
        这是关键步骤，确保账号能够正常使用
        """
        if not id_token:
            return {"success": False, "error": "缺少Firebase ID Token"}
            
        try:
            import uuid
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
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {id_token}",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            
            print("🌐 调用Warp GraphQL API激活用户...")
            
            response = requests.post(
                url,
                params={"op": "GetOrCreateUser"},
                json=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                get_or_create_user = result.get("data", {}).get("getOrCreateUser", {})
                
                if get_or_create_user.get("__typename") == "GetOrCreateUserOutput":
                    uid = get_or_create_user.get("uid")
                    is_onboarded = get_or_create_user.get("isOnboarded", False)
                    
                    print(f"✅ Warp用户激活成功: UID={uid}")
                    
                    return {
                        "success": True,
                        "uid": uid,
                        "isOnboarded": is_onboarded
                    }
                else:
                    error = get_or_create_user.get("error", {}).get("message", "Unknown error")
                    print(f"❌ Warp激活失败: {error}")
                    return {"success": False, "error": error}
            else:
                error_text = response.text[:500]
                print(f"❌ Warp激活HTTP错误 {response.status_code}")
                print(f"📄 错误响应内容: {error_text}")
                try:
                    error_json = response.json()
                    print(f"📋 JSON错误: {error_json}")
                except:
                    pass
                return {"success": False, "error": f"HTTP {response.status_code}: {error_text}"}
                
        except Exception as e:
            print(f"❌ Warp激活错误: {e}")
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
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "X-warp-client-version": "v0.2025.08.27.08.11.stable_04",
                "X-warp-os-category": "Desktop",
                "X-warp-manager-request": "true"
            }
            
            print("📊 获取账户额度信息...")
            
            response = requests.post(
                url,
                params={"op": "GetUser"},
                json=data,
                headers=headers,
                timeout=30
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
                        
                        print(f"✅ 账户额度信息:")
                        print(f"   📊 总额度: {request_limit}")
                        print(f"   📉 已使用: {requests_used}")
                        print(f"   📍 剩余额度: {request_limit - requests_used if request_limit else 'N/A'}")
                        print(f"   ♻️  下次刷新: {next_refresh}")
                        print(f"   ♾️  无限额度: {is_unlimited}")
                        
                        return {
                            "success": True,
                            "requestLimit": request_limit,
                            "requestsUsed": requests_used,
                            "requestsRemaining": request_limit - requests_used if request_limit else None,
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
                return {"success": False, "error": f"HTTP {response.status_code}: {error_text}"}
                
        except Exception as e:
            print(f"❌ 获取额度错误: {e}")
            return {"success": False, "error": str(e)}

    
    def _register_single_account(self, index: int) -> Dict[str, Any]:
        """注册单个账号
        
        Args:
            index: 账号编号
            
        Returns:
            注册结果
        """
        thread_id = threading.get_ident()
        start_time = time.time()
        
        try:
            print(f"🔄 [线程{thread_id}] 开始注册账号 #{index}...")
            
            # 创建CompleteScriptRegistration实例
            registrator = CompleteScriptRegistration()
            
            # 运行完整的注册流程
            result = registrator.run_complete_registration()
            
            if result['success']:
                # 激活Warp用户
                print(f"🔄 激活Warp用户: {result['final_tokens']['email']}")
                activation_result = self._activate_warp_user(result['final_tokens']['id_token'])

                if not activation_result['success']:
                    error_msg = f"Warp用户激活失败: {activation_result.get('error', '未知错误')}"
                    print(error_msg)
                    return {
                        'success': False,
                        'index': index,
                        'email': result['final_tokens']['email'],
                        'error': error_msg,
                        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                        'duration': time.time() - start_time
                    }

                print(f"✅ Warp用户激活成功: {result['final_tokens']['email']}")
                
                # 获取账户额度信息
                limit_info = self._get_request_limit(result['final_tokens']['id_token'])
                request_limit = None
                if limit_info['success']:
                    request_limit = limit_info.get('requestLimit')
                else:
                    print(f"⚠️ 获取额度失败，但不影响注册: {limit_info.get('error', '未知')}")
                
                # 保存到数据库
                try:
                    account = Account(
                        email=result['final_tokens']['email'],
                        local_id=result['final_tokens']['local_id'],
                        id_token=result['final_tokens']['id_token'],
                        refresh_token=result['final_tokens']['refresh_token'],
                        status='available'
                    )
                    self.db.add_account(account)
                    print(f"💾 [线程{thread_id}] 账号已保存到数据库: {account.email}")
                except Exception as e:
                    print(f"⚠️ [线程{thread_id}] 保存账号到数据库失败: {e}")
                
                return {
                    'success': True,
                    'index': index,
                    'email': result['final_tokens']['email'],
                    'local_id': result['final_tokens']['local_id'],
                    'request_limit': request_limit,
                    'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                    'duration': time.time() - start_time
                }
            else:
                error_msg = result.get('error', '未知错误')
                # 尝试从各个步骤中提取错误信息
                if not result.get('email_info'):
                    error_msg = "创建邮箱失败"
                elif not result.get('signin_result', {}).get('success'):
                    error_msg = f"发送登录请求失败: {result.get('signin_result', {}).get('error', '未知')}"
                elif not result.get('email_result'):
                    error_msg = "未收到验证邮件"
                elif not result.get('final_tokens', {}).get('success'):
                    error_msg = f"完成登录失败: {result.get('final_tokens', {}).get('error', '未知')}"
                
                return {
                    'success': False,
                    'index': index,
                    'error': error_msg,
                    'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                    'duration': time.time() - start_time
                }
                
        except Exception as e:
            return {
                'success': False,
                'index': index,
                'error': f'注册异常: {str(e)}',
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'duration': time.time() - start_time
            }
    
    def register_single_account_sync(self) -> Optional[Account]:
        """同步注册单个账号（用于快速测试）"""
        print("\n🔧 开始注册单个账号（同步模式）...")
        
        try:
            # 创建CompleteScriptRegistration实例
            registrator = CompleteScriptRegistration()
            
            # 运行完整的注册流程
            result = registrator.run_complete_registration()
            
            if result['success']:
                # 创建账号对象
                account = Account(
                    email=result['final_tokens']['email'],
                    local_id=result['final_tokens']['local_id'],
                    id_token=result['final_tokens']['id_token'],
                    refresh_token=result['final_tokens']['refresh_token'],
                    status='available'
                )
                
                # 保存到数据库
                self.db.add_account(account)
                print(f"✅ 账号注册成功并保存: {account.email}")
                return account
            else:
                print(f"❌ 账号注册失败")
                return None
                
        except Exception as e:
            print(f"❌ 注册异常: {e}")
            return None


# 测试函数
def test_registration():
    """测试注册功能"""
    print("=" * 80)
    print("🧪 开始测试账号注册功能")
    print("=" * 80)
    
    registrator = BatchRegister(max_workers=1)
    
    # 测试注册单个账号
    account = registrator.register_single_account_sync()
    
    if account:
        print(f"\n✅ 测试成功!")
        print(f"   📧 邮箱: {account.email}")
        print(f"   🔑 ID: {account.local_id}")
        print(f"   ⏰ 创建时间: {account.created_at}")
    else:
        print("\n❌ 测试失败!")
    
    return account is not None


# 全局批量注册器实例
_batch_register_instance = None


def get_batch_register() -> BatchRegister:
    """获取批量注册器单例"""
    global _batch_register_instance
    if _batch_register_instance is None:
        _batch_register_instance = BatchRegister(max_workers=20)  # 并发线程数（建议3-10）
    return _batch_register_instance


if __name__ == "__main__":
    # 运行测试
    test_registration()
