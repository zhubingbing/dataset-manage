#!/usr/bin/env python3

from file_tracker import FileTracker

# 测试任务 task_1749207615 的文件状态加载
task_id = 'task_1749207615'
ft = FileTracker(task_id)

print(f'任务ID: {task_id}')
print(f'文件状态数量: {len(ft.file_status)}')

if ft.file_status:
    print('\n前5个文件的状态:')
    for i, (filename, status) in enumerate(list(ft.file_status.items())[:5]):
        print(f'  {i+1}. {filename}')
        print(f'     状态: {status["status"]}')
        print(f'     URL: {status.get("url", "N/A")}')
        print(f'     大小: {status.get("expected_size", 0)} 字节')
        print()
        
    # 统计各种状态的文件数量
    status_counts = {}
    total_size = 0
    for filename, status in ft.file_status.items():
        file_status = status.get('status', 'unknown')
        status_counts[file_status] = status_counts.get(file_status, 0) + 1
        total_size += status.get('expected_size', 0)
    
    print('状态统计:')
    for status, count in status_counts.items():
        print(f'  {status}: {count} 个文件')
    
    print(f'\n总大小: {total_size / (1024**4):.2f} TB')
else:
    print('❌ 没有加载到任何文件状态')
    print('检查文件是否存在:')
    import os
    status_file = f'metadata/tasks/{task_id}/file_status.json'
    print(f'  {status_file}: {"存在" if os.path.exists(status_file) else "不存在"}') 