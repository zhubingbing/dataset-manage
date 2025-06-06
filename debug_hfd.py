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

# 解析文件
files = importer.parse_aria2c_urls()

print(f"解析到 {len(files)} 个文件")
print("\n前3个文件的详细信息:")
for i, f in enumerate(files[:3]):
    print(f"\n文件 {i+1}:")
    for key, value in f.items():
        print(f"  {key}: {value}")

# 测试转换过程
print("\n测试转换过程:")
task_info, file_list = importer.convert_to_our_format()

print("\n前3个转换后的文件:")
for i, f in enumerate(file_list[:3]):
    print(f"\n文件 {i+1}:")
    print(f"  url: {f['url']}")
    print(f"  relative_path: {f['relative_path']}")
    print(f"  status: {f['status']}") 