#!/usr/bin/env python3

from hfd_importer import HFDImporter
from pathlib import Path

# 先查看原始文件内容
print("原始文件前40行:")
with open('/mnt/data/code/llm/Recap-DataComp-1B/.hfd/aria2c_urls.txt', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines[:40]):
        print(f"{i+1:2d}: {repr(line)}")

print("\n" + "="*50)

# 创建导入器
importer = HFDImporter(
    '/mnt/data/code/llm/Recap-DataComp-1B/.hfd', 
    '/mnt/data/code/llm/Recap-DataComp-1B'
)

# 解析 aria2c_urls.txt 文件
aria2c_files = importer.parse_aria2c_urls()
print(f"解析到 {len(aria2c_files)} 个aria2c文件")

print("\n前3个aria2c文件的详细信息:")
for i, (path, config) in enumerate(list(aria2c_files.items())[:3]):
    print(f"\n文件 {i+1}: {path}")
    for key, value in config.items():
        if key == 'url':
            # URL太长，只显示末尾部分
            print(f"  {key}: ...{value[-60:]}")
        else:
            print(f"  {key}: {value}")

# 解析 repo_metadata.json
repo_metadata = importer.parse_repo_metadata()
siblings = repo_metadata.get('siblings', [])
print(f"\nrepo_metadata.json 中有 {len(siblings)} 个siblings文件")

# 测试完整文件列表创建
print("\n创建完整文件列表:")
complete_files = importer.create_complete_file_list()
print(f"完整文件列表包含 {len(complete_files)} 个文件")

# 统计信息
with_config = [f for f in complete_files if f.get('has_download_config', False)]
without_config = [f for f in complete_files if not f.get('has_download_config', False)]

print(f"  有下载配置: {len(with_config)} 个")
print(f"  无下载配置: {len(without_config)} 个")

print("\n无下载配置的文件示例:")
for i, f in enumerate(without_config[:3]):
    status_icon = {
        'completed': '✅',
        'downloading': '⏬', 
        'pending': '⏳',
        'missing': '❓'
    }.get(f['status'], '❓')
    print(f"  {i+1}. {f['relative_path']} - 状态: {f['status']} ({status_icon})")

print("\n有下载配置的文件示例:")
for i, f in enumerate(with_config[:3]):
    status_icon = {
        'completed': '✅',
        'downloading': '⏬', 
        'pending': '⏳',
        'missing': '❓'
    }.get(f['status'], '❓')
    gid = f.get('gid', 'N/A')[:8] + '...' if f.get('gid') else 'N/A'
    print(f"  {i+1}. {f['relative_path']} - 状态: {f['status']} ({status_icon}) - gid: {gid}")

# 测试转换过程
print("\n测试转换过程:")
task_info, file_list = importer.convert_to_our_format()
hfd_meta = task_info['hfd_metadata']

print(f"任务信息:")
print(f"  仓库ID: {task_info['repo_id']}")
print(f"  siblings总数: {hfd_meta['total_siblings']}")
print(f"  aria2c文件数: {hfd_meta['aria2c_files_count']}")
print(f"  完整文件数: {hfd_meta['complete_files_count']}") 