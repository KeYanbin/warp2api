#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
释放所有使用中的账号
将所有status='in_use'的账号重置为'available'
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# 配置
DATABASE_PATH = "accounts.db"
LOG_FILE = "release_accounts.log"

class AccountReleaser:
    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = db_path
        self.connection = None
        self.released_count = 0
        
    def connect_db(self):
        """连接到数据库"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
            print(f"✅ 成功连接到数据库: {self.db_path}")
            return True
        except Exception as e:
            print(f"❌ 连接数据库失败: {e}")
            return False
    
    def get_in_use_accounts(self):
        """获取所有使用中的账号"""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT id, email, session_id, last_used 
            FROM accounts 
            WHERE status = 'in_use'
        """)
        return cursor.fetchall()
    
    def release_all_accounts(self):
        """释放所有使用中的账号"""
        cursor = self.connection.cursor()
        
        # 先获取使用中的账号信息
        in_use_accounts = self.get_in_use_accounts()
        
        if not in_use_accounts:
            print("📋 没有找到使用中的账号，无需释放")
            return 0
        
        print(f"\n🔍 找到 {len(in_use_accounts)} 个使用中的账号:")
        for account in in_use_accounts:
            print(f"  - Email: {account['email']}, Session: {account['session_id']}")
        
        # 批量释放账号
        cursor.execute("""
            UPDATE accounts 
            SET status = 'available', session_id = NULL 
            WHERE status = 'in_use'
        """)
        
        self.released_count = cursor.rowcount
        self.connection.commit()
        
        return self.released_count
    
    def log_release(self):
        """记录释放操作到日志"""
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().isoformat()
            f.write(f"[{timestamp}] 释放了 {self.released_count} 个账号\n")
    
    def get_statistics(self):
        """获取账号池统计信息"""
        cursor = self.connection.cursor()
        
        # 各状态账号数量
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM accounts 
            GROUP BY status
        """)
        stats = cursor.fetchall()
        
        # 总账号数
        cursor.execute("SELECT COUNT(*) FROM accounts")
        total = cursor.fetchone()[0]
        
        return stats, total
    
    def run(self):
        """执行释放操作"""
        print("=" * 60)
        print("🚀 账号池批量释放工具")
        print("=" * 60)
        
        # 连接数据库
        if not self.connect_db():
            return False
        
        try:
            # 显示释放前状态
            print("\n📊 释放前账号池状态:")
            stats_before, total_before = self.get_statistics()
            for stat in stats_before:
                print(f"  {stat['status']}: {stat['count']} 个")
            print(f"  总计: {total_before} 个")
            
            # 执行释放
            released = self.release_all_accounts()
            
            if released > 0:
                # 记录日志
                self.log_release()
                
                # 显示释放后状态
                print(f"\n✅ 成功释放 {released} 个账号!")
                print("\n📊 释放后账号池状态:")
                stats_after, total_after = self.get_statistics()
                for stat in stats_after:
                    print(f"  {stat['status']}: {stat['count']} 个")
                print(f"  总计: {total_after} 个")
                
                print(f"\n📝 操作已记录到日志: {LOG_FILE}")
            
            print("\n✨ 操作完成!")
            return True
            
        except Exception as e:
            print(f"\n❌ 操作失败: {e}")
            return False
        finally:
            if self.connection:
                self.connection.close()
                print("\n🔒 数据库连接已关闭")

def main():
    """主函数"""
    releaser = AccountReleaser()
    success = releaser.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()