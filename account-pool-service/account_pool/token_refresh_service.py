#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Token刷新服务 - 基于warpzhuce的最佳实践
严格遵守1小时刷新限制，防止账号被封
"""

import json
import requests
import time
import base64
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from utils.logger import logger
from .database import get_database, Account


class TokenRefreshService:
    """Token刷新服务"""
    
    def __init__(self, firebase_api_key: str = "AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs"):
        """
        初始化Token刷新服务
        
        Args:
            firebase_api_key: Firebase API密钥
        """
        self.firebase_api_key = firebase_api_key
        self.base_url = "https://securetoken.googleapis.com/v1/token"
        self.db = get_database()
        
        logger.info("🔐 Token刷新服务已初始化 - 严格遵守1小时限制")
    
    def can_refresh_token(self, account: Account) -> Tuple[bool, Optional[str]]:
        """
        检查是否可以刷新token（严格遵守1小时限制）
        
        Args:
            account: 账号信息
            
        Returns:
            (是否可以刷新, 错误消息或None)
        """
        # 使用数据库的刷新检查方法
        can_refresh, error_msg = self.db.can_refresh_token(account.email, min_interval_hours=1)
        
        if can_refresh:
            logger.info(f"🔓 Token刷新检查通过: {account.email}")
        else:
            logger.warning(f"🔒 Token刷新被阻止: {account.email} - {error_msg}")
            
        return can_refresh, error_msg
    
    def is_token_expired(self, id_token: str, buffer_minutes: int = 5) -> bool:
        """
        检查JWT token是否过期
        
        Args:
            id_token: JWT token
            buffer_minutes: 缓冲时间（分钟）
            
        Returns:
            是否过期
        """
        try:
            if not id_token:
                return True
            
            # 解码JWT token
            parts = id_token.split('.')
            if len(parts) != 3:
                logger.warning("无效的JWT格式")
                return True
            
            # 添加填充并解码payload
            payload_part = parts[1]
            payload_part += '=' * (4 - len(payload_part) % 4)
            
            payload_bytes = base64.urlsafe_b64decode(payload_part)
            payload = json.loads(payload_bytes.decode('utf-8'))
            
            # 检查过期时间
            exp_timestamp = payload.get('exp')
            if not exp_timestamp:
                logger.warning("JWT中没有过期时间")
                return True
            
            # 添加缓冲时间
            current_time = time.time()
            buffer_seconds = buffer_minutes * 60
            
            is_expired = (exp_timestamp - current_time) <= buffer_seconds
            
            if is_expired:
                logger.info(f"Token即将过期或已过期: {account.email if 'account' in locals() else 'unknown'}")
            
            return is_expired
            
        except Exception as e:
            logger.error(f"检查Token过期状态失败: {e}")
            return True  # 出错时认为已过期
    
    def refresh_firebase_token(self, refresh_token: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        执行Firebase Token刷新
        
        Args:
            refresh_token: 刷新token
            
        Returns:
            (是否成功, 新的id_token, 错误消息)
        """
        try:
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            }
            
            url = f"{self.base_url}?key={self.firebase_api_key}"
            
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.ok:
                data = response.json()
                new_id_token = data.get('id_token')
                if new_id_token:
                    logger.info("✅ Firebase Token刷新成功")
                    return True, new_id_token, None
                else:
                    error_msg = "Firebase响应中缺少id_token"
                    logger.error(f"❌ {error_msg}")
                    return False, None, error_msg
            else:
                error_msg = f"Firebase刷新失败: HTTP {response.status_code}"
                if response.status_code == 400:
                    try:
                        error_data = response.json()
                        error_detail = error_data.get('error', {}).get('message', '未知错误')
                        error_msg += f" - {error_detail}"
                    except:
                        pass
                
                logger.error(f"❌ {error_msg}")
                return False, None, error_msg
                
        except Exception as e:
            error_msg = f"Token刷新异常: {e}"
            logger.error(f"❌ {error_msg}")
            return False, None, error_msg
    
    def refresh_account_token(self, account: Account, force_refresh: bool = False) -> Tuple[bool, Optional[Account], Optional[str]]:
        """
        刷新账号的token
        
        Args:
            account: 账号信息
            force_refresh: 是否强制刷新（忽略时间限制）- 🚨 谨慎使用
            
        Returns:
            (是否成功, 更新后的账号信息, 错误消息)
        """
        logger.info(f"🔄 开始刷新账号Token: {account.email}")
        
        # 🚨 强制刷新警告
        if force_refresh:
            logger.warning(f"⚠️ 强制刷新模式启用: {account.email} - 可能导致账号被封！")
        else:
            # 检查是否可以刷新
            can_refresh, error_msg = self.can_refresh_token(account)
            if not can_refresh:
                return False, None, error_msg
        
        # 如果token未过期且不是强制刷新，跳过刷新
        if not force_refresh and not self.is_token_expired(account.id_token):
            logger.info(f"⏭️ Token未过期，跳过刷新: {account.email}")
            return True, account, "Token未过期"
        
        # 执行Firebase token刷新
        success, new_id_token, error_msg = self.refresh_firebase_token(account.refresh_token)
        
        if success and new_id_token:
            # 更新数据库中的token信息
            refresh_time = datetime.now()
            update_success = self.db.update_account_token(
                email=account.email,
                id_token=new_id_token, 
                refresh_token=account.refresh_token,  # refresh_token通常不变
                refresh_time=refresh_time
            )
            
            if update_success:
                # 创建更新后的账号对象
                updated_account = Account(
                    id=account.id,
                    email=account.email,
                    local_id=account.local_id,
                    id_token=new_id_token,
                    refresh_token=account.refresh_token,
                    status=account.status,
                    created_at=account.created_at,
                    last_used=account.last_used,
                    last_refresh_time=refresh_time,
                    use_count=account.use_count,
                    session_id=account.session_id
                )
                
                logger.success(f"✅ 账号Token刷新完成: {account.email}")
                return True, updated_account, None
            else:
                error_msg = "更新数据库失败"
                logger.error(f"❌ {error_msg}: {account.email}")
                return False, None, error_msg
        else:
            logger.error(f"❌ Token刷新失败: {account.email} - {error_msg}")
            return False, None, error_msg
    
    def refresh_account_if_needed(self, account: Account, buffer_minutes: int = 5) -> Tuple[bool, Optional[Account], Optional[str]]:
        """
        根据需要刷新账号token（仅在接近过期时）
        
        Args:
            account: 账号信息
            buffer_minutes: 过期缓冲时间（分钟）
            
        Returns:
            (是否成功, 更新后的账号信息或原账号, 错误消息)
        """
        if self.is_token_expired(account.id_token, buffer_minutes):
            logger.info(f"🔄 Token即将过期，开始刷新: {account.email}")
            return self.refresh_account_token(account, force_refresh=False)
        else:
            logger.info(f"✅ Token有效，无需刷新: {account.email}")
            return True, account, "Token有效"
    
    def get_token_info(self, id_token: str) -> Dict[str, Any]:
        """
        获取Token信息（用于调试）
        
        Args:
            id_token: JWT Token
            
        Returns:
            Token信息
        """
        try:
            if not id_token:
                return {"error": "Token为空"}
            
            # 解码JWT token
            parts = id_token.split('.')
            if len(parts) != 3:
                return {"error": "无效的JWT格式"}
            
            # 解码payload
            payload_part = parts[1]
            payload_part += '=' * (4 - len(payload_part) % 4)
            
            payload_bytes = base64.urlsafe_b64decode(payload_part)
            payload = json.loads(payload_bytes.decode('utf-8'))
            
            exp_timestamp = payload.get('exp')
            iat_timestamp = payload.get('iat')
            
            info = {
                'user_id': payload.get('user_id'),
                'email': payload.get('email'),
                'name': payload.get('name'),
                'issued_at': datetime.fromtimestamp(iat_timestamp).isoformat() if iat_timestamp else None,
                'expires_at': datetime.fromtimestamp(exp_timestamp).isoformat() if exp_timestamp else None,
                'is_expired': self.is_token_expired(id_token, buffer_minutes=0) if exp_timestamp else True,
                'remaining_seconds': max(0, exp_timestamp - time.time()) if exp_timestamp else 0
            }
            
            return info
            
        except Exception as e:
            return {"error": f"解析Token失败: {e}"}


# 全局Token刷新服务实例
_token_refresh_service = None

def get_token_refresh_service() -> TokenRefreshService:
    """获取Token刷新服务实例（单例模式）"""
    global _token_refresh_service
    if _token_refresh_service is None:
        _token_refresh_service = TokenRefreshService()
    return _token_refresh_service