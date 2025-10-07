#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查询数据库配额统计"""

import sys
sys.path.insert(0, '.')

from account_pool.database import get_database

def main():
    db = get_database()
    cursor = db._get_connection().cursor()
    
    # 统计各配额类型的数量
    cursor.execute('SELECT COUNT(*) FROM accounts WHERE quota_type = 2500')
    count_2500 = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM accounts WHERE quota_type = 150')
    count_150 = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM accounts')
    total = cursor.fetchone()[0]
    
    print('📊 数据库配额统计:')
    print(f'   🎉 高额度(2500): {count_2500} 个')
    print(f'   📊 普通额度(150): {count_150} 个')
    print(f'   📁 总计: {total} 个')
    
    if count_2500 > 0:
        percentage = (count_2500 / total * 100) if total > 0 else 0
        print(f'\n   📈 高额度占比: {percentage:.1f}%')
    
    # 显示高额度账号列表
    if count_2500 > 0:
        print('\n🎉 高额度账号列表:')
        cursor.execute('SELECT email, status, created_at FROM accounts WHERE quota_type = 2500 ORDER BY created_at DESC')
        for row in cursor.fetchall():
            print(f'   📧 {row[0]}')
            print(f'      状态: {row[1]} | 创建时间: {row[2]}')

if __name__ == '__main__':
    main()
