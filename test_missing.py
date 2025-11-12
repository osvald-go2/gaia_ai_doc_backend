#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import run_workflow

def test_missing_interface():
    result = run_workflow({
        'feishu_urls': ['https://ecnjtt87q4e5.feishu.cn/wiki/O2NjwrNDCiRDqMkWJyfcNwd5nXe'],
        'user_intent': 'generate_crud',
        'trace_id': 'test-missing'
    })

    interfaces = result.get('ism', {}).get('interfaces', [])

    print('=== 解析结果 ===')
    print(f'总共解析出 {len(interfaces)} 个接口')

    for i, interface in enumerate(interfaces):
        name = interface.get('name', '未知')
        type_name = interface.get('type', 'unknown')
        source = interface.get('source_method', 'unknown')
        print(f'{i+1}. {name} [{type_name}] ({source})')

    expected = ['总筛选项', '消耗波动详情', '素材明细', '消耗趋势', '交易趋势']
    found = [iface.get('name', '') for iface in interfaces]
    missing = [exp for exp in expected if exp not in found]

    print(f'\n期望接口: {expected}')
    print(f'实际接口: {found}')
    print(f'缺失接口: {missing}')

    success_rate = len([f for f in found if f in expected]) / len(expected) * 100
    print(f'成功率: {success_rate:.1f}%')

    if len(missing) == 0:
        print('[SUCCESS] 所有预期接口都已成功解析!')
    else:
        print(f'[ERROR] 仍然缺失 {len(missing)} 个接口: {missing}')

    return len(missing) == 0

if __name__ == '__main__':
    test_missing_interface()