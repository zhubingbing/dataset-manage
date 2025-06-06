#!/usr/bin/env python3
"""
HFD 元数据导入工具
将 hfd 下载的元数据导入到我们的数据集下载管理系统中
"""

import os
import json
import sys
import re
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, List, Optional, Tuple
import argparse

from task_manager import TaskManager


class HFDImporter:
    """HFD 元数据导入器"""
    
    def __init__(self, hfd_dir: str, output_dir: str, base_url: str = "https://hf-mirror.com"):
        self.hfd_dir = Path(hfd_dir)
        self.output_dir = Path(output_dir)  
        self.base_url = base_url
        
        # 检查必要文件
        self.aria2c_urls_file = self.hfd_dir / "aria2c_urls.txt"
        self.repo_metadata_file = self.hfd_dir / "repo_metadata.json"
        self.last_command_file = self.hfd_dir / "last_download_command"
        
        if not self.aria2c_urls_file.exists():
            raise FileNotFoundError(f"aria2c_urls.txt 文件不存在: {self.aria2c_urls_file}")
        if not self.repo_metadata_file.exists():
            raise FileNotFoundError(f"repo_metadata.json 文件不存在: {self.repo_metadata_file}")
            
    def parse_aria2c_urls(self) -> List[Dict]:
        """解析 aria2c_urls.txt 文件"""
        files = []
        current_file = {}
        
        with open(self.aria2c_urls_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('https://'):
                # 如果前面有文件数据，先保存
                if current_file:
                    files.append(current_file.copy())
                
                # 开始新文件，清理URL（移除可能的制表符等）
                url = line.strip()
                current_file = {'url': url}
                
                # 处理后续的配置行
                i += 1
                while i < len(lines):
                    config_line = lines[i].strip()
                    
                    # 如果是下一个URL，退出内层循环
                    if config_line.startswith('https://'):
                        i -= 1  # 回退一行，让外层循环处理
                        break
                    
                    # 解析配置行
                    if config_line.startswith('gid='):
                        current_file['gid'] = config_line.split('=', 1)[1]
                    elif config_line.startswith('dir='):
                        current_file['dir'] = config_line.split('=', 1)[1]
                    elif config_line.startswith('out='):
                        current_file['out'] = config_line.split('=', 1)[1]
                    
                    i += 1
                i -= 1  # 回退一行，因为下次外层循环会+1
                
            i += 1
            
        # 添加最后一个文件
        if current_file:
            files.append(current_file)
            
        return files
        
    def parse_repo_metadata(self) -> Dict:
        """解析 repo_metadata.json 文件"""
        with open(self.repo_metadata_file, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    def parse_last_command(self) -> Dict:
        """解析 last_download_command 文件"""
        command_info = {}
        if self.last_command_file.exists():
            with open(self.last_command_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                # 解析环境变量格式
                for pair in content.split():
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        command_info[key] = value
        return command_info
        
    def get_file_status(self, file_path: Path) -> str:
        """检查文件下载状态"""
        if not file_path.exists():
            return "pending"
            
        # 检查 .aria2 文件（未完成标志）
        aria2_file = Path(str(file_path) + '.aria2')
        if aria2_file.exists():
            return "downloading"
            
        return "completed"
        
    def convert_to_our_format(self) -> Tuple[Dict, List[Dict]]:
        """转换为我们系统的格式"""
        # 解析数据
        aria2c_files = self.parse_aria2c_urls()
        repo_metadata = self.parse_repo_metadata()
        command_info = self.parse_last_command()
        
        # 创建任务信息
        repo_id = command_info.get('REPO_ID', repo_metadata.get('id', 'unknown'))
        
        task_info = {
            'repo_id': repo_id,
            'task_name': f"hfd_import_{repo_id.replace('/', '_')}",
            'base_url': self.base_url,
            'output_dir': str(self.output_dir),
            'created_from_hfd': True,
            'hfd_metadata': {
                'original_hfd_dir': str(self.hfd_dir),
                'repo_metadata': repo_metadata,
                'command_info': command_info,
                'import_time': None  # 会在导入时设置
            }
        }
        
        # 转换文件列表
        file_list = []
        for file_info in aria2c_files:
            url = file_info['url']
            file_dir = file_info.get('dir', '')
            filename = file_info.get('out', '')
            
            # 构建完整的文件路径
            if file_dir:
                relative_path = f"{file_dir}/{filename}"
            else:
                relative_path = filename
                
            full_path = self.output_dir / relative_path
            
            # 获取文件状态
            status = self.get_file_status(full_path)
            
            file_entry = {
                'url': url,
                'relative_path': relative_path,
                'full_path': str(full_path),
                'status': status,
                'gid': file_info.get('gid'),
                'from_hfd': True
            }
            
            file_list.append(file_entry)
            
        return task_info, file_list
        
    def import_to_system(self, task_manager: TaskManager) -> str:
        """导入到系统中"""
        # 转换数据
        task_info, file_list = self.convert_to_our_format()
        
        # 设置导入时间
        import datetime
        task_info['hfd_metadata']['import_time'] = datetime.datetime.now().isoformat()
        
        # 创建任务，使用TaskManager现有的接口
        task_id = task_manager.create_task(
            repo_id=task_info['repo_id'],
            local_dir=task_info['output_dir'],
            is_dataset=True  # HFD通常用于数据集
        )
        
        # 获取任务并添加HFD特有的元数据
        task = task_manager.get_task(task_id)
        if task:
            # 将HFD元数据存储在任务中
            task['hfd_metadata'] = task_info['hfd_metadata']
            task['created_from_hfd'] = True
            task['base_url'] = task_info['base_url']
            task['total_files'] = len(file_list)
            
            # 统计文件状态
            status_counts = {}
            for file_entry in file_list:
                status = file_entry['status']
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # 计算进度
            completed_files = status_counts.get('completed', 0)
            if len(file_list) > 0:
                progress = f"{completed_files * 100 // len(file_list)}%"
                task['progress'] = progress
            
            # 更新任务
            task_manager._save_tasks()
            
            # TODO: 这里应该还需要将文件列表保存到某个地方
            # 目前我们将文件信息保存在任务的metadata中
            task['hfd_files'] = file_list
            task_manager._save_tasks()
            
        return task_id
        
    def print_summary(self):
        """打印导入摘要"""
        task_info, file_list = self.convert_to_our_format()
        
        print(f"📊 HFD 导入摘要")
        print(f"📁 仓库ID: {task_info['repo_id']}")
        print(f"📁 输出目录: {task_info['output_dir']}")
        print(f"🌐 基础URL: {task_info['base_url']}")
        print(f"📁 原始HFD目录: {task_info['hfd_metadata']['original_hfd_dir']}")
        print()
        
        # 统计文件状态
        status_count = {}
        for file_entry in file_list:
            status = file_entry['status']
            status_count[status] = status_count.get(status, 0) + 1
            
        print(f"📋 文件状态统计:")
        for status, count in status_count.items():
            status_name = {
                'completed': '✅ 已完成',
                'downloading': '⏬ 下载中',
                'pending': '⏳ 待下载'
            }.get(status, status)
            print(f"  {status_name}: {count} 个文件")
            
        print(f"📁 总文件数: {len(file_list)}")
        
        # 显示前几个文件的示例
        print(f"\n📋 文件示例 (前5个):")
        for i, file_entry in enumerate(file_list[:5]):
            status_icon = {
                'completed': '✅',
                'downloading': '⏬', 
                'pending': '⏳'
            }.get(file_entry['status'], '❓')
            print(f"  {status_icon} {file_entry['relative_path']}")
            
        if len(file_list) > 5:
            print(f"  ... 还有 {len(file_list) - 5} 个文件")


def main():
    parser = argparse.ArgumentParser(description='HFD 元数据导入工具')
    parser.add_argument('hfd_dir', help='HFD 元数据目录路径 (包含 .hfd 目录)')
    parser.add_argument('output_dir', help='数据集输出目录')
    parser.add_argument('--base-url', default='https://hf-mirror.com', help='基础URL (默认: https://hf-mirror.com)')
    parser.add_argument('--dry-run', action='store_true', help='只显示摘要，不实际导入')
    parser.add_argument('--db-path', default='downloads.db', help='数据库文件路径')
    
    args = parser.parse_args()
    
    try:
        # 查找 .hfd 目录
        hfd_dir = Path(args.hfd_dir)
        if hfd_dir.name == '.hfd':
            hfd_metadata_dir = hfd_dir
        else:
            hfd_metadata_dir = hfd_dir / '.hfd'
            
        if not hfd_metadata_dir.exists():
            print(f"❌ 错误: 找不到 .hfd 目录: {hfd_metadata_dir}")
            sys.exit(1)
            
        # 创建导入器
        importer = HFDImporter(
            hfd_dir=str(hfd_metadata_dir),
            output_dir=args.output_dir,
            base_url=args.base_url
        )
        
        # 显示摘要
        importer.print_summary()
        
        if args.dry_run:
            print("\n🔍 这是试运行模式，未实际导入数据")
            return
            
        # 确认导入
        print(f"\n❓ 是否要将这个 HFD 任务导入到数据库？ (y/N): ", end='')
        response = input().strip().lower()
        
        if response in ['y', 'yes']:
            # 执行导入
            task_manager = TaskManager(args.db_path)
            task_id = importer.import_to_system(task_manager)
            
            print(f"\n✅ 导入成功！")
            print(f"📋 任务ID: {task_id}")
            print(f"💾 数据库: {args.db_path}")
            print(f"\n🚀 你现在可以使用以下命令继续下载:")
            print(f"   python main.py --resume --task-id {task_id}")
            
        else:
            print("\n❌ 导入已取消")
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 