"""
数据集管理器
负责管理已注册的数据集信息
"""

import logging
from pathlib import Path
from utils import (
    get_current_timestamp, load_json_file, save_json_file,
    validate_repo_id
)
from config import get_config

class DatasetManager:
    """数据集管理器"""
    
    def __init__(self):
        self.config = get_config()
        self.metadata_dir = self.config.get_metadata_dir()
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.datasets_file = self.metadata_dir / 'datasets.json'
        self.datasets = self._load_datasets()
        self.logger = logging.getLogger(__name__)
    
    def _load_datasets(self):
        """加载数据集列表"""
        return load_json_file(self.datasets_file, default=[])
    
    def _save_datasets(self):
        """保存数据集列表"""
        return save_json_file(self.datasets_file, self.datasets)
    
    def add_dataset(self, repo_id, description=None, is_dataset=False, tags=None):
        """添加数据集"""
        if not validate_repo_id(repo_id):
            raise ValueError(f"无效的仓库ID: {repo_id}")
        
        # 检查是否已存在
        if self.get_dataset(repo_id):
            self.logger.warning(f"数据集 {repo_id} 已存在")
            return False
        
        dataset_info = {
            'repo_id': repo_id,
            'description': description or '',
            'is_dataset': is_dataset,
            'tags': tags or [],
            'created_at': get_current_timestamp(),
            'download_count': 0,
            'last_downloaded': None,
            'status': 'available'
        }
        
        self.datasets.append(dataset_info)
        
        if self._save_datasets():
            self.logger.info(f"成功添加数据集: {repo_id}")
            return True
        else:
            # 回滚
            self.datasets.pop()
            self.logger.error(f"保存数据集失败: {repo_id}")
            return False
    
    def get_dataset(self, repo_id):
        """获取数据集信息"""
        for dataset in self.datasets:
            if dataset['repo_id'] == repo_id:
                return dataset
        return None
    
    def update_dataset(self, repo_id, **kwargs):
        """更新数据集信息"""
        dataset = self.get_dataset(repo_id)
        if not dataset:
            return False
        
        # 更新字段
        for key, value in kwargs.items():
            if key in dataset:
                dataset[key] = value
        
        dataset['updated_at'] = get_current_timestamp()
        
        if self._save_datasets():
            self.logger.info(f"成功更新数据集: {repo_id}")
            return True
        else:
            self.logger.error(f"更新数据集失败: {repo_id}")
            return False
    
    def remove_dataset(self, repo_id):
        """删除数据集"""
        dataset = self.get_dataset(repo_id)
        if not dataset:
            return False
        
        self.datasets.remove(dataset)
        
        if self._save_datasets():
            self.logger.info(f"成功删除数据集: {repo_id}")
            return True
        else:
            # 回滚
            self.datasets.append(dataset)
            self.logger.error(f"删除数据集失败: {repo_id}")
            return False
    
    def list_datasets(self, filter_tags=None, is_dataset=None):
        """列出数据集"""
        datasets = self.datasets.copy()
        
        if filter_tags:
            datasets = [ds for ds in datasets if any(tag in ds.get('tags', []) for tag in filter_tags)]
        
        if is_dataset is not None:
            datasets = [ds for ds in datasets if ds.get('is_dataset') == is_dataset]
        
        return datasets
    
    def search_datasets(self, query):
        """搜索数据集"""
        query = query.lower()
        results = []
        
        for dataset in self.datasets:
            # 搜索仓库ID
            if query in dataset['repo_id'].lower():
                results.append(dataset)
                continue
            
            # 搜索描述
            if query in dataset.get('description', '').lower():
                results.append(dataset)
                continue
            
            # 搜索标签
            if any(query in tag.lower() for tag in dataset.get('tags', [])):
                results.append(dataset)
                continue
        
        return results
    
    def get_stats(self):
        """获取统计信息"""
        total = len(self.datasets)
        models = len([ds for ds in self.datasets if not ds.get('is_dataset', False)])
        datasets = len([ds for ds in self.datasets if ds.get('is_dataset', False)])
        
        return {
            'total': total,
            'models': models,
            'datasets': datasets,
            'total_downloads': sum(ds.get('download_count', 0) for ds in self.datasets)
        }
    
    def increment_download_count(self, repo_id):
        """增加下载计数"""
        dataset = self.get_dataset(repo_id)
        if dataset:
            dataset['download_count'] = dataset.get('download_count', 0) + 1
            dataset['last_downloaded'] = get_current_timestamp()
            return self._save_datasets()
        return False 