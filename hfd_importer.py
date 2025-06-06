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
from typing import Dict, List, Optional, Tuple, Set
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
            
    def parse_aria2c_urls(self) -> Dict[str, Dict]:
        """解析 aria2c_urls.txt 文件，返回文件路径到下载配置的映射"""
        aria2c_files = {}
        current_file = {}
        
        with open(self.aria2c_urls_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('https://'):
                # 如果前面有文件数据，先保存
                if current_file and 'out' in current_file and 'dir' in current_file:
                    # 构建相对路径作为key
                    relative_path = f"{current_file['dir']}/{current_file['out']}"
                    aria2c_files[relative_path] = current_file.copy()
                
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
                    if '=' in config_line:
                        key, value = config_line.split('=', 1)
                        current_file[key] = value
                    
                    i += 1
                i -= 1  # 回退一行，因为下次外层循环会+1
                
            i += 1
            
        # 添加最后一个文件
        if current_file and 'out' in current_file and 'dir' in current_file:
            relative_path = f"{current_file['dir']}/{current_file['out']}"
            aria2c_files[relative_path] = current_file
            
        return aria2c_files
        
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
        
    def get_file_status(self, file_path: Path, is_in_aria2c_urls: bool) -> str:
        """检查文件下载状态
        
        Args:
            file_path: 文件路径
            is_in_aria2c_urls: 文件是否在aria2c_urls.txt中（等待下载列表）
        """
        # 如果文件在aria2c_urls.txt中，说明它是等待下载的
        if is_in_aria2c_urls:
            # 检查文件是否存在
            if not file_path.exists():
                return "pending"
            
            # 检查 .aria2 文件（下载中标志）
            aria2_file = Path(str(file_path) + '.aria2')
            if aria2_file.exists():
                return "downloading"
            
            # 文件存在且没有.aria2文件，但仍在等待列表中，可能是刚完成但aria2c_urls.txt还没更新
            return "completed"
        else:
            # 不在aria2c_urls.txt中，说明已经下载完成或不需要下载
            if file_path.exists():
                return "completed"
            else:
                # 这种情况比较特殊：不在等待列表中但文件不存在
                # 可能是小文件（如.gitattributes）或者有其他问题
                return "missing"
        
    def create_complete_file_list(self) -> List[Dict]:
        """创建完整的文件列表，结合 aria2c_urls.txt 和 repo_metadata.json"""
        # 解析两个文件
        aria2c_files = self.parse_aria2c_urls()
        repo_metadata = self.parse_repo_metadata()
        
        # 获取所有文件列表
        all_siblings = repo_metadata.get('siblings', [])
        
        # 构建完整文件列表
        complete_file_list = []
        aria2c_file_paths = set(aria2c_files.keys())
        
        for sibling in all_siblings:
            rfilename = sibling.get('rfilename', '')
            if not rfilename:
                continue
                
            # 构建完整路径
            full_path = self.output_dir / rfilename
            
            # 检查这个文件是否在 aria2c_urls.txt 中
            has_download_config = rfilename in aria2c_file_paths
            
            if has_download_config:
                # 有下载配置的文件
                aria2c_config = aria2c_files[rfilename]
                file_entry = {
                    'relative_path': rfilename,
                    'full_path': str(full_path),
                    'url': aria2c_config.get('url', ''),
                    'status': self.get_file_status(full_path, True),
                    'gid': aria2c_config.get('gid'),
                    'aria2c_config': aria2c_config,
                    'from_hfd': True,
                    'has_download_config': True,
                    'in_aria2c_urls': True
                }
            else:
                # 没有下载配置的文件（可能是 .gitattributes, README.md 等）
                # 构造一个基本的URL
                repo_id = repo_metadata.get('id', 'unknown')
                url = f"{self.base_url}/datasets/{repo_id}/resolve/main/{rfilename}"
                
                file_entry = {
                    'relative_path': rfilename,
                    'full_path': str(full_path),
                    'url': url,
                    'status': self.get_file_status(full_path, False),
                    'gid': None,
                    'aria2c_config': None,
                    'from_hfd': True,
                    'has_download_config': False,
                    'in_aria2c_urls': False
                }
            
            complete_file_list.append(file_entry)
            
        # 检查是否有 aria2c_urls.txt 中的文件没有在 siblings 中
        sibling_paths = {s.get('rfilename', '') for s in all_siblings}
        missing_from_siblings = aria2c_file_paths - sibling_paths
        
        if missing_from_siblings:
            print(f"⚠️  警告: 发现 {len(missing_from_siblings)} 个文件在 aria2c_urls.txt 中但不在 repo_metadata.json 的 siblings 中:")
            for missing_path in list(missing_from_siblings)[:5]:  # 只显示前5个
                print(f"   - {missing_path}")
            if len(missing_from_siblings) > 5:
                print(f"   - ... 还有 {len(missing_from_siblings) - 5} 个")
                
            # 添加这些缺失的文件
            for missing_path in missing_from_siblings:
                aria2c_config = aria2c_files[missing_path]
                full_path = self.output_dir / missing_path
                
                file_entry = {
                    'relative_path': missing_path,
                    'full_path': str(full_path),
                    'url': aria2c_config.get('url', ''),
                    'status': self.get_file_status(full_path, True),
                    'gid': aria2c_config.get('gid'),
                    'aria2c_config': aria2c_config,
                    'from_hfd': True,
                    'has_download_config': True,
                    'in_aria2c_urls': True,
                    'missing_from_siblings': True
                }
                complete_file_list.append(file_entry)
        
        return complete_file_list
        
    def convert_to_our_format(self) -> Tuple[Dict, List[Dict]]:
        """转换为我们系统的格式"""
        # 解析数据
        repo_metadata = self.parse_repo_metadata()
        command_info = self.parse_last_command()
        complete_file_list = self.create_complete_file_list()
        
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
                'import_time': None,  # 会在导入时设置
                'total_siblings': len(repo_metadata.get('siblings', [])),
                'aria2c_files_count': len(self.parse_aria2c_urls()),
                'complete_files_count': len(complete_file_list)
            }
        }
        
        return task_info, complete_file_list
        
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
            download_config_counts = {'with_config': 0, 'without_config': 0}
            
            for file_entry in file_list:
                status = file_entry['status']
                status_counts[status] = status_counts.get(status, 0) + 1
                
                if file_entry.get('has_download_config', False):
                    download_config_counts['with_config'] += 1
                else:
                    download_config_counts['without_config'] += 1
            
            # 计算进度
            completed_files = status_counts.get('completed', 0)
            if len(file_list) > 0:
                progress = f"{completed_files * 100 // len(file_list)}%"
                task['progress'] = progress
            
            # 添加统计信息
            task['file_status_counts'] = status_counts
            task['download_config_counts'] = download_config_counts
            
            # 更新任务
            task_manager._save_tasks()
            
            # 保存完整的文件列表到任务中
            task['hfd_complete_files'] = file_list
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
        
        hfd_meta = task_info['hfd_metadata']
        print(f"📋 文件统计:")
        print(f"  🗂️  repo_metadata.json 中的 siblings: {hfd_meta['total_siblings']} 个")
        print(f"  📥 aria2c_urls.txt 中的下载文件: {hfd_meta['aria2c_files_count']} 个")
        print(f"  📁 合并后的完整文件列表: {hfd_meta['complete_files_count']} 个")
        print()
        
        # 统计文件状态
        status_count = {}
        download_config_count = {'with_config': 0, 'without_config': 0}
        
        for file_entry in file_list:
            status = file_entry['status']
            status_count[status] = status_count.get(status, 0) + 1
            
            if file_entry.get('has_download_config', False):
                download_config_count['with_config'] += 1
            else:
                download_config_count['without_config'] += 1
            
        print(f"📋 文件状态统计:")
        for status, count in status_count.items():
            status_name = {
                'completed': '✅ 已完成',
                'downloading': '⏬ 下载中',
                'pending': '⏳ 待下载',
                'missing': '❓ 缺失文件'
            }.get(status, status)
            print(f"  {status_name}: {count} 个文件")
        
        print()
        print(f"💡 状态说明:")
        print(f"  📥 aria2c_urls.txt 中的文件 = 等待下载的文件")
        print(f"  📁 siblings 中但不在 aria2c_urls.txt 中 = 已下载完成的文件")
        print(f"  ⏬ 下载中 = 存在 .aria2 临时文件")
        print(f"  ❓ 缺失文件 = 应该已完成但文件不存在")
        
        print()
        print(f"📋 下载配置统计:")
        print(f"  🔧 有下载配置的文件: {download_config_count['with_config']} 个")
        print(f"  📄 无下载配置的文件: {download_config_count['without_config']} 个")
        
        # 显示无下载配置的文件示例
        no_config_files = [f for f in file_list if not f.get('has_download_config', False)]
        if no_config_files:
            print(f"\n📋 无下载配置的文件示例:")
            for i, file_entry in enumerate(no_config_files[:5]):
                status_icon = {
                    'completed': '✅',
                    'downloading': '⏬', 
                    'pending': '⏳'
                }.get(file_entry['status'], '❓')
                print(f"  {status_icon} {file_entry['relative_path']}")
                
            if len(no_config_files) > 5:
                print(f"  ... 还有 {len(no_config_files) - 5} 个文件")
        
        # 显示有下载配置的文件示例
        config_files = [f for f in file_list if f.get('has_download_config', False)]
        if config_files:
            print(f"\n📋 有下载配置的文件示例:")
            for i, file_entry in enumerate(config_files[:5]):
                status_icon = {
                    'completed': '✅',
                    'downloading': '⏬', 
                    'pending': '⏳'
                }.get(file_entry['status'], '❓')
                gid = file_entry.get('gid', 'N/A')[:8] + '...' if file_entry.get('gid') else 'N/A'
                print(f"  {status_icon} {file_entry['relative_path']} (gid: {gid})")
                
            if len(config_files) > 5:
                print(f"  ... 还有 {len(config_files) - 5} 个文件")


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