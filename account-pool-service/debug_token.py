#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试Token携带情况
"""

import sys
import os
import requests

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def debug_token():
    """调试Token配置和使用"""
    print("🔍 调试Token配置...")
    print("=" * 50)
    
    try:
        # 检查config.py中的配置
        from config import config
        print(f"✅ config.py中的配置:")
        print(f"   MOEMAIL_URL: {config.MOEMAIL_URL}")
        print(f"   MOEMAIL_API_KEY: {config.MOEMAIL_API_KEY}")
        print(f"   API密钥长度: {len(config.MOEMAIL_API_KEY)} 字符")
        
    except Exception as e:
        print(f"❌ 加载config失败: {e}")
        return
    
    print(f"\n🔍 测试手动API调用...")
    print("=" * 30)
    
    # 手动测试API调用
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        session = requests.Session()
        session.verify = False
        
        # 准备请求数据
        data = {
            "list": [
                {
                    "email": "test@rsgdfb.filegear-sg.me"
                }
            ]
        }
        
        # 准备请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.MOEMAIL_API_KEY}"
        }
        
        print(f"📤 请求URL: {config.MOEMAIL_URL}/api/public/addUser")
        print(f"📤 请求数据: {data}")
        print(f"📤 Authorization头: Bearer {config.MOEMAIL_API_KEY[:10]}...{config.MOEMAIL_API_KEY[-10:]}")
        
        # 发送请求
        response = session.post(
            f"{config.MOEMAIL_URL}/api/public/addUser",
            json=data,
            headers=headers,
            timeout=30
        )
        
        print(f"\n📥 响应状态码: {response.status_code}")
        print(f"📥 响应头: {dict(response.headers)}")
        print(f"📥 响应内容: {response.text}")
        
        if response.status_code == 401:
            print("\n❌ 401错误 - Token验证失败")
            print("可能的原因:")
            print("1. API密钥不正确")
            print("2. API密钥已过期")
            print("3. 需要不同的认证格式")
            print("4. 服务器端认证配置问题")
            
    except Exception as e:
        print(f"❌ 手动API调用失败: {e}")
        import traceback
        traceback.print_exc()


def test_different_auth_formats():
    """测试不同的认证格式"""
    print(f"\n🧪 测试不同的认证格式...")
    print("=" * 40)
    
    from config import config
    
    auth_formats = [
        f"Bearer {config.MOEMAIL_API_KEY}",
        config.MOEMAIL_API_KEY,
        f"Token {config.MOEMAIL_API_KEY}",
        f"API-Key {config.MOEMAIL_API_KEY}"
    ]
    
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    for i, auth_header in enumerate(auth_formats, 1):
        print(f"\n测试格式 {i}: {auth_header[:20]}...")
        
        try:
            session = requests.Session()
            session.verify = False
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": auth_header
            }
            
            data = {"list": [{"email": "test@test.com"}]}
            
            response = session.post(
                f"{config.MOEMAIL_URL}/api/public/addUser",
                json=data,
                headers=headers,
                timeout=10
            )
            
            print(f"   状态码: {response.status_code}")
            if response.status_code != 401:
                print(f"   响应: {response.text[:100]}")
                if response.status_code == 200:
                    print("   ✅ 这个认证格式可能有效!")
                    
        except Exception as e:
            print(f"   错误: {type(e).__name__}")


def check_simple_config():
    """检查simple_config中的配置"""
    print(f"\n🔍 检查simple_config配置...")
    print("=" * 35)
    
    try:
        from account_pool.simple_config import load_config
        simple_config = load_config()
        
        print(f"✅ simple_config中的配置:")
        print(f"   api_key: {simple_config.get('api_key', 'N/A')}")
        print(f"   moemail_api_key: {simple_config.get('moemail_api_key', 'N/A')}")
        print(f"   moemail_url: {simple_config.get('moemail_url', 'N/A')}")
        
        # 比较两个配置
        from config import config
        
        print(f"\n🔄 配置对比:")
        print(f"   config.py API Key: {config.MOEMAIL_API_KEY}")
        print(f"   simple_config API Key: {simple_config.get('api_key', 'N/A')}")
        print(f"   是否相同: {config.MOEMAIL_API_KEY == simple_config.get('api_key')}")
        
    except Exception as e:
        print(f"❌ 检查simple_config失败: {e}")


if __name__ == "__main__":
    print("🚀 开始调试Token问题")
    print("=" * 60)
    
    # 调试基本配置
    debug_token()
    
    # 检查simple_config
    check_simple_config()
    
    # 测试不同认证格式
    test_different_auth_formats()
    
    print("\n" + "=" * 60)
    print("🎯 调试完成")
    
    print("\n💡 建议检查的地方:")
    print("1. 确认API密钥是否正确")
    print("2. 确认服务器是否在线")
    print("3. 确认认证格式是否正确")
    print("4. 查看服务器日志获取更多信息")
