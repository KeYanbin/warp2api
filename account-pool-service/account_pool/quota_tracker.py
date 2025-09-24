#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配额跟踪模块
跟踪和管理账号的API配额使用情况
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List
from utils.logger import logger
from config import config


class QuotaTracker:
    """配额跟踪器"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        # Warp API配额重置周期为30天
        self.quota_reset_days = 30
        
    def mark_account_quota_exhausted(self, email: str) -> bool:
        """
        标记账号配额用尽
        
        Args:
            email: 账号邮箱
            
        Returns:
            是否标记成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 更新账号状态为quota_exhausted，并记录时间
            cursor.execute('''
                UPDATE accounts 
                SET status = 'quota_exhausted', 
                    quota_exhausted_at = ?,
                    session_id = NULL
                WHERE email = ?
            ''', (datetime.now(), email))
            
            affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            if affected > 0:
                logger.warning(f"🚫 账号 {email} 的配额已用尽，标记为quota_exhausted")
                return True
            else:
                logger.error(f"未找到账号: {email}")
                return False
                
        except Exception as e:
            logger.error(f"标记账号配额用尽失败: {e}")
            return False
    
    def reset_expired_quotas(self) -> int:
        """
        重置过期的配额（30天后）
        
        Returns:
            重置的账号数量
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 计算30天前的时间
            reset_threshold = datetime.now() - timedelta(days=self.quota_reset_days)
            
            # 查找需要重置的账号
            cursor.execute('''
                SELECT email FROM accounts 
                WHERE status = 'quota_exhausted' 
                AND quota_exhausted_at < ?
            ''', (reset_threshold,))
            
            accounts_to_reset = cursor.fetchall()
            
            if accounts_to_reset:
                # 重置这些账号的状态
                cursor.execute('''
                    UPDATE accounts 
                    SET status = 'available', 
                        quota_exhausted_at = NULL
                    WHERE status = 'quota_exhausted' 
                    AND quota_exhausted_at < ?
                ''', (reset_threshold,))
                
                reset_count = cursor.rowcount
                conn.commit()
                
                if reset_count > 0:
                    logger.info(f"✅ 重置了 {reset_count} 个账号的配额（已过期30天）")
                    for (email,) in accounts_to_reset:
                        logger.info(f"  - {email} 配额已重置")
                        
                conn.close()
                return reset_count
            else:
                conn.close()
                return 0
                
        except Exception as e:
            logger.error(f"重置配额失败: {e}")
            return 0
    
    def get_quota_status(self, email: str) -> dict:
        """
        获取账号的配额状态
        
        Args:
            email: 账号邮箱
            
        Returns:
            配额状态信息
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT status, quota_exhausted_at 
                FROM accounts 
                WHERE email = ?
            ''', (email,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                status, quota_exhausted_at = row
                
                if status == 'quota_exhausted' and quota_exhausted_at:
                    # 计算重置时间
                    exhausted_time = datetime.fromisoformat(quota_exhausted_at)
                    reset_time = exhausted_time + timedelta(days=self.quota_reset_days)
                    time_until_reset = reset_time - datetime.now()
                    
                    return {
                        'email': email,
                        'status': status,
                        'is_exhausted': True,
                        'exhausted_at': quota_exhausted_at,
                        'reset_at': reset_time.isoformat(),
                        'days_until_reset': max(0, time_until_reset.days)
                    }
                else:
                    return {
                        'email': email,
                        'status': status,
                        'is_exhausted': False,
                        'exhausted_at': None,
                        'reset_at': None,
                        'days_until_reset': None
                    }
            else:
                return {
                    'email': email,
                    'status': 'not_found',
                    'is_exhausted': False
                }
                
        except Exception as e:
            logger.error(f"获取配额状态失败: {e}")
            return {
                'email': email,
                'status': 'error',
                'error': str(e)
            }
    
    def get_exhausted_accounts(self) -> List[dict]:
        """
        获取所有配额用尽的账号
        
        Returns:
            配额用尽的账号列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT email, quota_exhausted_at 
                FROM accounts 
                WHERE status = 'quota_exhausted'
                ORDER BY quota_exhausted_at DESC
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            accounts = []
            for email, exhausted_at in rows:
                exhausted_time = datetime.fromisoformat(exhausted_at)
                reset_time = exhausted_time + timedelta(days=self.quota_reset_days)
                time_until_reset = reset_time - datetime.now()
                
                accounts.append({
                    'email': email,
                    'exhausted_at': exhausted_at,
                    'reset_at': reset_time.isoformat(),
                    'days_until_reset': max(0, time_until_reset.days)
                })
            
            return accounts
            
        except Exception as e:
            logger.error(f"获取配额用尽账号列表失败: {e}")
            return []


# 全局配额跟踪器实例
_quota_tracker = None


def get_quota_tracker() -> QuotaTracker:
    """获取配额跟踪器实例"""
    global _quota_tracker
    if _quota_tracker is None:
        _quota_tracker = QuotaTracker()
    return _quota_tracker
