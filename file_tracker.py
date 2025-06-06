"""
文件级别跟踪器
负责跟踪每个下载任务中每个文件的详细状态
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from utils import load_json_file, save_json_file, get_current_timestamp, format_file_size
from config import get_config

class FileTracker:
    """文件下载状态跟踪器"""
    
    def __init__(self, task_id):
        self.task_id = task_id
        self.config = get_config()
        self.metadata_dir = self.config.get_metadata_dir() / 'tasks' / task_id
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        self.file_list_path = self.metadata_dir / 'file_list.json'
        self.file_status_path = self.metadata_dir / 'file_status.json'
        self.task_metadata_path = self.metadata_dir / 'task_metadata.json'
        
        self.file_list = self._load_file_list()
        self.file_status = self._load_file_status()
    
    def _load_file_list(self):
        """加载文件列表"""
        return load_json_file(self.file_list_path, default=[])
    
    def _load_file_status(self):
        """加载文件状态"""
        return load_json_file(self.file_status_path, default={})
    
    def _save_file_list(self):
        """保存文件列表"""
        return save_json_file(self.file_list_path, self.file_list)
    
    def _save_file_status(self):
        """保存文件状态"""
        return save_json_file(self.file_status_path, self.file_status)
    
    def save_task_metadata(self, repo_metadata):
        """保存任务的仓库元数据"""
        save_json_file(self.task_metadata_path, {
            'repo_metadata': repo_metadata,
            'saved_at': get_current_timestamp()
        })
    
    def initialize_file_list(self, file_list):
        """初始化文件列表和状态"""
        self.file_list = file_list
        
        # 初始化每个文件的状态
        for file_info in file_list:
            file_key = file_info['filename']
            if file_key not in self.file_status:
                self.file_status[file_key] = {
                    'filename': file_info['filename'],
                    'url': file_info['url'],
                    'expected_size': file_info.get('size', 0),
                    'status': 'pending',  # pending, downloading, completed, failed
                    'downloaded_size': 0,
                    'actual_size': 0,
                    'checksum': None,
                    'error_message': None,
                    'attempts': 0,
                    'created_at': get_current_timestamp(),
                    'started_at': None,
                    'completed_at': None
                }
        
        self._save_file_list()
        self._save_file_status()
    
    def update_file_status(self, filename, status, **kwargs):
        """更新文件状态"""
        if filename not in self.file_status:
            return False
        
        file_info = self.file_status[filename]
        file_info['status'] = status
        
        # 更新时间戳
        if status == 'downloading' and not file_info.get('started_at'):
            file_info['started_at'] = get_current_timestamp()
        elif status in ['completed', 'failed']:
            file_info['completed_at'] = get_current_timestamp()
        
        # 更新其他字段
        for key, value in kwargs.items():
            if key in file_info:
                file_info[key] = value
        
        return self._save_file_status()
    
    def verify_file_integrity(self, download_path):
        """验证文件完整性"""
        results = {}
        
        for filename, file_info in self.file_status.items():
            file_path = download_path / filename
            
            if not file_path.exists():
                results[filename] = {
                    'exists': False,
                    'size_match': False,
                    'status': 'missing'
                }
                continue
            
            # 检查文件大小
            actual_size = file_path.stat().st_size
            expected_size = file_info.get('expected_size', 0)
            size_match = actual_size == expected_size if expected_size > 0 else True
            
            # 更新实际大小
            self.update_file_status(filename, file_info['status'], actual_size=actual_size)
            
            results[filename] = {
                'exists': True,
                'size_match': size_match,
                'actual_size': actual_size,
                'expected_size': expected_size,
                'status': 'valid' if size_match else 'size_mismatch'
            }
        
        return results
    
    def get_download_summary(self):
        """获取下载摘要"""
        total_files = len(self.file_status)
        completed_files = len([f for f in self.file_status.values() if f['status'] == 'completed'])
        failed_files = len([f for f in self.file_status.values() if f['status'] == 'failed'])
        pending_files = len([f for f in self.file_status.values() if f['status'] == 'pending'])
        
        total_size = sum(f.get('expected_size', 0) for f in self.file_status.values())
        downloaded_size = sum(f.get('actual_size', 0) for f in self.file_status.values() if f['status'] == 'completed')
        
        return {
            'total_files': total_files,
            'completed_files': completed_files,
            'failed_files': failed_files,
            'pending_files': pending_files,
            'completion_rate': f"{completed_files/total_files*100:.1f}%" if total_files > 0 else "0%",
            'total_size': total_size,
            'downloaded_size': downloaded_size,
            'total_size_formatted': format_file_size(total_size),
            'downloaded_size_formatted': format_file_size(downloaded_size)
        }
    
    def get_failed_files(self):
        """获取失败的文件列表"""
        return [
            {
                'filename': filename,
                'error': file_info.get('error_message', 'Unknown error'),
                'attempts': file_info.get('attempts', 0)
            }
            for filename, file_info in self.file_status.items()
            if file_info['status'] == 'failed'
        ]
    
    def get_pending_files(self):
        """获取待下载的文件列表"""
        return [
            {
                'filename': filename,
                'url': file_info['url'],
                'size': file_info.get('expected_size', 0)
            }
            for filename, file_info in self.file_status.items()
            if file_info['status'] == 'pending'
        ]
    
    def get_file_status(self, filename):
        """获取单个文件的状态"""
        try:
            file_status = self._load_file_status()
            return file_status.get(filename)
        except Exception as e:
            self.logger.error(f"获取文件状态失败: {filename} - {str(e)}")
            return None
    
    def mark_file_completed(self, filename, download_path):
        """标记文件下载完成并验证"""
        file_path = download_path / filename
        
        if file_path.exists():
            actual_size = file_path.stat().st_size
            self.update_file_status(filename, 'completed', actual_size=actual_size)
            return True
        else:
            self.update_file_status(filename, 'failed', error_message='File not found after download')
            return False
    
    def cleanup_metadata(self):
        """清理元数据（可选）"""
        try:
            if self.metadata_dir.exists():
                import shutil
                shutil.rmtree(self.metadata_dir)
            return True
        except Exception:
            return False 