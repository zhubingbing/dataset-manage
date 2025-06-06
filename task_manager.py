"""
任务管理器
负责下载任务的创建、跟踪和管理
"""

import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from utils import (
    ensure_data_dir, load_json_file, save_json_file, 
    get_current_timestamp, generate_task_id, Colors
)
from config import get_config
import time

class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        self.config = get_config()
        self.metadata_dir = self.config.get_metadata_dir()
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_file = self.metadata_dir / 'tasks.json'
        self.tasks = self._load_tasks()
        self.logger = logging.getLogger(__name__)
    
    def _load_tasks(self):
        """加载任务列表"""
        return load_json_file(self.tasks_file, default=[])
    
    def _save_tasks(self):
        """保存任务列表"""
        return save_json_file(self.tasks_file, self.tasks)
    
    def create_task(self, repo_id, local_dir=None, revision='main', is_dataset=False):
        """创建下载任务"""
        task_id = f"task_{int(time.time())}"
        
        task = {
            'id': task_id,
            'repo_id': repo_id,
            'tool': 'aria2c',  # 固定使用aria2c
            'threads': 5,      # 固定高性能参数
            'concurrent': 8,   # 固定高性能参数
            'local_dir': local_dir,
            'revision': revision,
            'is_dataset': is_dataset,
            'status': 'pending',
            'progress': '0%',
            'created_at': get_current_timestamp(),
            'started_at': None,
            'completed_at': None,
            'error_message': None,
            'download_size': 0,
            'downloaded_size': 0,
            'download_speed': 0,
            'eta': None,
            'retry_count': 0,
            'max_retries': 3
        }
        
        self.tasks.append(task)
        
        if self._save_tasks():
            self.logger.info(f"成功创建任务: {task_id} - {repo_id}")
            return task_id
        else:
            # 回滚
            self.tasks.pop()
            self.logger.error(f"创建任务失败: {repo_id}")
            raise Exception("创建任务失败")
    
    def get_task(self, task_id):
        """获取任务信息"""
        for task in self.tasks:
            if task['id'] == task_id:
                return task
        return None
    
    def update_task(self, task_id, **kwargs):
        """更新任务信息"""
        task = self.get_task(task_id)
        if not task:
            return False
        
        # 更新字段
        for key, value in kwargs.items():
            if key in task:
                task[key] = value
        
        return self._save_tasks()
    
    def update_task_status(self, task_id, status, error_message=None):
        """更新任务状态"""
        task = self.get_task(task_id)
        if not task:
            return False
        
        task['status'] = status
        
        if status == 'running' and not task.get('started_at'):
            task['started_at'] = get_current_timestamp()
        elif status in ['completed', 'failed', 'cancelled']:
            task['completed_at'] = get_current_timestamp()
        
        if error_message:
            task['error_message'] = error_message
        
        return self._save_tasks()
    
    def update_task_progress(self, task_id, progress, downloaded_size=None, 
                           download_speed=None, eta=None):
        """更新任务进度"""
        task = self.get_task(task_id)
        if not task:
            return False
        
        task['progress'] = progress
        if downloaded_size is not None:
            task['downloaded_size'] = downloaded_size
        if download_speed is not None:
            task['download_speed'] = download_speed
        if eta is not None:
            task['eta'] = eta
        
        return self._save_tasks()
    
    def cancel_task(self, task_id):
        """取消任务"""
        task = self.get_task(task_id)
        if not task:
            return False
        
        if task['status'] in ['completed', 'failed', 'cancelled']:
            self.logger.warning(f"任务 {task_id} 已完成，无法取消")
            return False
        
        return self.update_task_status(task_id, 'cancelled')
    
    def retry_task(self, task_id):
        """重试任务"""
        task = self.get_task(task_id)
        if not task:
            return False
        
        if task['status'] != 'failed':
            self.logger.warning(f"任务 {task_id} 状态不是失败，无法重试")
            return False
        
        if task['retry_count'] >= task['max_retries']:
            self.logger.warning(f"任务 {task_id} 已达到最大重试次数")
            return False
        
        task['retry_count'] += 1
        task['status'] = 'pending'
        task['error_message'] = None
        task['started_at'] = None
        task['completed_at'] = None
        
        return self._save_tasks()
    
    def list_tasks(self, status=None, repo_id=None):
        """列出任务"""
        tasks = self.tasks.copy()
        
        if status:
            tasks = [task for task in tasks if task['status'] == status]
        
        if repo_id:
            tasks = [task for task in tasks if task['repo_id'] == repo_id]
        
        # 按创建时间倒序排序
        tasks.sort(key=lambda x: x['created_at'], reverse=True)
        
        return tasks
    
    def get_pending_tasks(self):
        """获取待处理任务"""
        return [task for task in self.tasks if task['status'] == 'pending']
    
    def get_running_tasks(self):
        """获取运行中任务"""
        return [task for task in self.tasks if task['status'] == 'running']
    
    def clean_completed_tasks(self, keep_days=7):
        """清理完成的任务记录"""
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        initial_count = len(self.tasks)
        
        # 保留未完成的任务和最近完成的任务
        self.tasks = [
            task for task in self.tasks
            if task['status'] not in ['completed', 'failed', 'cancelled'] or
            (task.get('completed_at') and 
             datetime.fromisoformat(task['completed_at']) > cutoff_date)
        ]
        
        cleaned_count = initial_count - len(self.tasks)
        
        if cleaned_count > 0:
            self._save_tasks()
            self.logger.info(f"清理了 {cleaned_count} 个任务记录")
        
        return cleaned_count
    
    def get_task_stats(self):
        """获取任务统计信息"""
        stats = {
            'total': len(self.tasks),
            'pending': 0,
            'running': 0,
            'completed': 0,
            'failed': 0,
            'cancelled': 0
        }
        
        for task in self.tasks:
            status = task['status']
            if status in stats:
                stats[status] += 1
        
        return stats
    
    def remove_task(self, task_id):
        """删除任务"""
        task = self.get_task(task_id)
        if not task:
            return False
        
        self.tasks.remove(task)
        
        if self._save_tasks():
            self.logger.info(f"成功删除任务: {task_id}")
            return True
        else:
            # 回滚
            self.tasks.append(task)
            self.logger.error(f"删除任务失败: {task_id}")
            return False
    
    def delete_task(self, task_id):
        """删除任务"""
        try:
            # 处理不同的数据结构
            if isinstance(self.tasks, dict):
                if task_id in self.tasks:
                    del self.tasks[task_id]
                    found = True
                else:
                    found = False
            elif isinstance(self.tasks, list):
                # 如果是列表，找到并删除对应的任务
                original_length = len(self.tasks)
                self.tasks = [task for task in self.tasks if task.get('id') != task_id]
                found = len(self.tasks) < original_length
            else:
                found = False
            
            if found:
                # 保存到文件
                if self._save_tasks():
                    print(f"{Colors.GREEN}任务 {task_id} 已从任务列表中删除{Colors.NC}")
                    return True
                else:
                    print(f"{Colors.RED}保存任务列表失败{Colors.NC}")
                    return False
            else:
                print(f"{Colors.YELLOW}任务 {task_id} 不存在{Colors.NC}")
                return False
                
        except Exception as e:
            print(f"{Colors.RED}删除任务失败: {str(e)}{Colors.NC}")
            return False
            
    def get_all_tasks(self):
        """获取所有任务列表"""
        if isinstance(self.tasks, dict):
            return list(self.tasks.values())
        elif isinstance(self.tasks, list):
            return self.tasks
        else:
            return [] 