#!/usr/bin/env python3

import json
from pathlib import Path

# 读取文件状态
task_id = 'task_1749208314'
status_file = Path(f'metadata/tasks/{task_id}/file_status.json')

with open(status_file) as f:
    data = json.load(f)

# 统计总数
print(f'📊 文件状态统计')
print(f'总文件数: {len(data)}')

# 统计状态
status_count = {}
for filename, info in data.items():
    status = info.get('status', 'unknown')
    status_count[status] = status_count.get(status, 0) + 1

print('\n状态分布:')
for status, count in status_count.items():
    print(f'  {status}: {count} 个文件')

# 检查文件大小
total_size = 0
for filename, info in data.items():
    if info.get('status') == 'completed':
        size = info.get('actual_size', 0)
        total_size += size

print(f'\n已完成文件总大小: {total_size / (1024**3):.2f} GB')

# 显示一些示例
print('\n已完成文件示例:')
completed = [(k, v) for k, v in data.items() if v.get('status') == 'completed']
for filename, info in completed[:5]:
    print(f'  ✓ {filename} ({info.get("actual_size", 0)} 字节)')
if len(completed) > 5:
    print(f'  ... 还有 {len(completed)-5} 个文件')

print('\n待下载文件示例:')
pending = [(k, v) for k, v in data.items() if v.get('status') == 'pending']
for filename, info in pending[:5]:
    print(f'  ○ {filename}')
if len(pending) > 5:
    print(f'  ... 还有 {len(pending)-5} 个文件') 