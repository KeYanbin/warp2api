#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块

负责处理配置文件的加载、验证和依赖检查。
从main.py重构而来，提供独立的配置管理功能。
"""

import os
import json
from typing import Dict, List, Optional, Any
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from remote_config_service import get_remote_config_service
except ImportError:
    try:
        from src.core.remote_config_service import get_remote_config_service
    except ImportError:
        # 兼容性导入
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from core.remote_config_service import get_remote_config_service


class ConfigManager:
    """配置管理器"""
    
    # 必要的模块文件列表
    REQUIRED_MODULES = [
        'src/core/moemail_client.py',
        'src/core/complete_script_registration.py',
        'src/core/machine_id.py',
        'src/core/warp_process.py',
        'src/core/keychain_manager.py',
        'src/core/crypto_utils.py',
        'src/core/user_service.py',
        'src/core/db_singleton.py',
        'src/core/platform_detector.py',
        'src/core/hardware_id.py'
    ]
    
    # 必要的配置键
    REQUIRED_CONFIG_KEYS = ['api_key', 'firebase_api_key']
    
    def __init__(self):
        """
        初始化配置管理器 - 现在使用远程配置服务
        """
        self._config_cache: Optional[Dict[str, Any]] = None
    
    def check_dependencies(self) -> bool:
        """
        检查必要的依赖文件
        
        Returns:
            bool: 所有依赖文件都存在返回True，否则返回False
        """
        missing_files = []
        for module in self.REQUIRED_MODULES:
            if not os.path.exists(module):
                missing_files.append(module)
        
        if missing_files:
            print(f"❌ 缺少必要文件: {', '.join(missing_files)}")
            return False
        
        return True
    
    def check_config(self) -> bool:
        """
        检查远程配置服务是否可用
        
        Returns:
            bool: 远程配置可用返回True
        """
        try:
            remote_service = get_remote_config_service()
            config = remote_service.get_config()
            
            # 检查关键配置
            api_key = config.get('api_key')
            firebase_key = config.get('firebase_api_key')
            
            if not api_key or not firebase_key:
                print("⚠️ 远程配置中缺少必要的API密钥")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ 远程配置服务不可用: {e}")
            return False
    
    def load_config(self, force_reload: bool = False) -> Optional[Dict[str, Any]]:
        """
        加载配置文件 - 现在从远程配置服务获取
        
        Args:
            force_reload: 是否强制重新加载，忽略缓存
            
        Returns:
            Dict[str, Any]: 配置字典，加载失败返回None
        """
        try:
            remote_service = get_remote_config_service()
            config = remote_service.get_config(force_refresh=force_reload)
            self._config_cache = config
            return config
        except Exception as e:
            print(f"❌ 从远程服务加载配置失败: {e}")
            return None
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        获取配置值 - 现在从远程配置服务获取
        
        Args:
            key: 配置键，支持点号分隔的嵌套键如 'database.host'
            default: 默认值
            
        Returns:
            Any: 配置值
        """
        try:
            remote_service = get_remote_config_service()
            return remote_service.get_config_value(key, default)
        except Exception as e:
            print(f"❌ 从远程服务获取配置值失败: {e}")
            return default
    
    def is_valid(self) -> bool:
        """
        检查配置是否完全有效（依赖和远程配置都正常）
        
        Returns:
            bool: 配置有效返回True
        """
        return self.check_dependencies() and self.check_config()
    
    def get_status_info(self) -> Dict[str, Any]:
        """
        获取配置状态信息
        
        Returns:
            Dict[str, Any]: 状态信息字典
        """
        return {
            'dependencies_ok': self.check_dependencies(),
            'remote_config_ok': self.check_config(),
            'using_remote_config': True
        }


# 全局配置管理器实例
_global_config_manager = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例"""
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = ConfigManager()
    return _global_config_manager


# 兼容性函数，保持与原main.py的接口一致
def check_dependencies() -> bool:
    """检查必要的依赖文件（兼容性函数）"""
    return get_config_manager().check_dependencies()


def check_config() -> bool:
    """检查配置文件（兼容性函数）"""
    return get_config_manager().check_config()


def load_config() -> Optional[Dict[str, Any]]:
    """加载配置文件（兼容性函数）"""
    return get_config_manager().load_config()




if __name__ == "__main__":
    # 测试配置管理器
    manager = ConfigManager()
    print("🔍 测试配置管理器（现使用远程配置）...")
    print(f"依赖检查: {'✅' if manager.check_dependencies() else '❌'}")
    
    config = manager.load_config()
    if config:
        print("✅ 远程配置加载成功")
        print(f"API密钥: {'已配置' if manager.get_config_value('api_key') else '未配置'}")
        print(f"Firebase密钥: {'已配置' if manager.get_config_value('firebase_api_key') else '未配置'}")
    else:
        print("❌ 远程配置加载失败")
