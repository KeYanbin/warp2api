#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测试脚本
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from account_pool.proxy_register import CloudflareDNSResolver, ProxyRegistration
import json

print("=" * 80)
print("🧪 快速测试 Cloudflare DNS 解析注册")
print("=" * 80)

try:
    # 创建 DNS 解析器
    print("\n1️⃣ 创建 DNS 解析器...")
    dns_resolver = CloudflareDNSResolver(use_api=True)
    print(f"   IP 池大小: {len(dns_resolver.cf_ips)} 个 IP")
    
    if dns_resolver.cf_ips:
        print(f"   示例 IP: {dns_resolver.cf_ips[0]}")
    
    # 创建注册器
    print("\n2️⃣ 创建注册器...")
    registrator = ProxyRegistration(dns_resolver=dns_resolver)
    
    # 执行注册
    print("\n3️⃣ 开始注册...")
    result = registrator.register_account()
    
    # 输出结果
    print("\n" + "=" * 80)
    print("📊 注册结果:")
    print("=" * 80)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if result['success']:
        print("\n✅ 注册成功！")
        print(f"   邮箱: {result['email']}")
        print(f"   耗时: {result['duration']:.2f} 秒")
    else:
        print(f"\n❌ 注册失败: {result.get('error', '未知错误')}")
    
except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)