#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的随机域名选择器
从MoeMail API配置中获取可用域名并随机选择
"""

import random
import json
import os
import time
from typing import List, Optional
try:
    from moemail_client import MoeMailClient
except ImportError:
    from src.core.moemail_client import MoeMailClient


class SimpleDomainSelector:
    """简单域名选择器"""
    
    def __init__(self, cache_file: str = "data/domains_cache.json"):
        self.cache_file = cache_file
        self.domains_cache: List[str] = []
        self.last_update = 0
        self.cache_duration = 3600  # 1小时缓存
        
        # 默认域名（备用）
        self.default_domains = ["gllovioo.ggff.net", "rsgdfb.filegear-sg.me"]
        
        # 加载缓存
        self._load_cache()
    
    def _load_cache(self):
        """加载域名缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self.domains_cache = cache_data.get('domains', [])
                    self.last_update = cache_data.get('last_update', 0)
                    print(f"📂 加载域名缓存: {len(self.domains_cache)} 个域名")
        except Exception as e:
            print(f"⚠️ 加载域名缓存失败: {e}")
            self.domains_cache = []
    
    def _save_cache(self):
        """保存域名缓存"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            
            cache_data = {
                'domains': self.domains_cache,
                'last_update': time.time(),
                'total_count': len(self.domains_cache)
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 保存域名缓存: {len(self.domains_cache)} 个域名")
        except Exception as e:
            print(f"⚠️ 保存域名缓存失败: {e}")
    def update_domains_from_config(self, moemail_client: MoeMailClient, force_update: bool = False, skip_on_cache: bool = False):
        """更新域名列表（已禁用API获取功能，使用固定域名）
        
        Args:
            moemail_client: MoeMail客户端（已不使用）
            force_update: 强制更新（已不使用）
            skip_on_cache: 如果有缓存则跳过更新（已不使用）
        """
        # 直接使用默认域名，不再从API获取
        print("ℹ️ 使用固定域名配置，不再从API获取域名列表")
        if not self.domains_cache:
            self.domains_cache = self.default_domains.copy()
            print(f"✅ 使用固定域名: {self.domains_cache}")
    
    def get_random_domain(self, moemail_client: MoeMailClient = None, skip_config_update: bool = False) -> str:
        """
        获取随机域名
        
        Args:
            moemail_client: MoeMail客户端，用于获取配置
            skip_config_update: 跳过配置更新（用于批量操作）
            
        Returns:
            str: 随机选择的域名
        """
        # 确保使用固定域名列表
        if not self.domains_cache:
            self.domains_cache = self.default_domains.copy()
        
        # 使用缓存的域名或默认域名
        available_domains = self.domains_cache if self.domains_cache else self.default_domains
        
        # 随机选择
        selected_domain = random.choice(available_domains)
        
        print(f"🎯 随机选择域名: {selected_domain} (从 {len(available_domains)} 个域名中选择)")
        
        return selected_domain
    
    def get_available_domains(self) -> List[str]:
        """获取所有可用域名"""
        return self.domains_cache if self.domains_cache else self.default_domains
    
    def print_stats(self):
        """打印统计信息"""
        print("📊 域名选择器统计")
        print("=" * 50)
        print(f"缓存文件: {self.cache_file}")
        print(f"缓存域名数: {len(self.domains_cache)}")
        
        if self.last_update > 0:
            update_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_update))
            print(f"最后更新: {update_time}")
        else:
            print("最后更新: 从未更新")
        
        available_domains = self.get_available_domains()
        if available_domains:
            print(f"\n📋 可用域名 ({len(available_domains)} 个):")
            for i, domain in enumerate(available_domains, 1):
                print(f"  {i:2d}. {domain}")


# 全局实例
_domain_selector = None


def get_domain_selector() -> SimpleDomainSelector:
    """获取域名选择器单例"""
    global _domain_selector
    if _domain_selector is None:
        _domain_selector = SimpleDomainSelector()
    return _domain_selector


def get_random_email_domain(moemail_client: MoeMailClient = None, skip_config_update: bool = False) -> str:
    """
    获取随机邮箱域名（便捷函数）
    
    Args:
        moemail_client: MoeMail客户端
        skip_config_update: 跳过配置更新（用于批量操作）
        
    Returns:
        str: 随机域名
    """
    selector = get_domain_selector()
    return selector.get_random_domain(moemail_client, skip_config_update)


if __name__ == "__main__":
    # 测试代码
    print("🧪 测试简单域名选择器")
    print("=" * 50)
    
    selector = SimpleDomainSelector()
    selector.print_stats()
    
    print("\n🎯 测试随机选择:")
    for i in range(5):
        domain = selector.get_random_domain()
        print(f"  第{i+1}次: {domain}")
