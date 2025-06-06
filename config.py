"""
配置管理模块
"""

import os
from pathlib import Path

class Config:
    """配置管理类"""
    
    def __init__(self):
        # Hugging Face 端点配置
        self.hf_endpoint = os.getenv('HF_ENDPOINT', 'https://hf-mirror.com')
        
        # 代理配置
        self.http_proxy = os.getenv('HTTP_PROXY', None)
        self.https_proxy = os.getenv('HTTPS_PROXY', None)
        
        # 路径配置
        self.metadata_dir = Path(os.getenv('METADATA_DIR', 'metadata'))
        self.downloads_dir = Path(os.getenv('DOWNLOADS_DIR', 'downloads'))
        self.logs_dir = Path(os.getenv('LOGS_DIR', 'logs'))
        
        # 下载配置
        self.default_threads = 4
        self.default_concurrent = 5
        self.request_timeout = 30
        
        # 如果检测到在中国，自动使用镜像
        if not os.getenv('HF_ENDPOINT'):
            self.hf_endpoint = 'https://hf-mirror.com'
    
    def get_hf_endpoint(self):
        """获取Hugging Face端点"""
        return self.hf_endpoint
    
    def get_proxies(self):
        """获取代理配置"""
        proxies = {}
        if self.http_proxy:
            proxies['http'] = self.http_proxy
        if self.https_proxy:
            proxies['https'] = self.https_proxy
        return proxies if proxies else None
    
    def get_metadata_dir(self):
        """获取元数据目录"""
        return self.metadata_dir
    
    def get_downloads_dir(self):
        """获取下载目录"""
        return self.downloads_dir
    
    def get_logs_dir(self):
        """获取日志目录"""
        return self.logs_dir
    
    def set_hf_endpoint(self, endpoint):
        """设置Hugging Face端点"""
        self.hf_endpoint = endpoint
        os.environ['HF_ENDPOINT'] = endpoint
    
    def set_metadata_dir(self, path):
        """设置元数据目录"""
        self.metadata_dir = Path(path)
        os.environ['METADATA_DIR'] = str(path)
        # 确保目录存在
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
    
    def set_downloads_dir(self, path):
        """设置下载目录"""
        self.downloads_dir = Path(path)
        os.environ['DOWNLOADS_DIR'] = str(path)
        # 确保目录存在
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
    
    def set_logs_dir(self, path):
        """设置日志目录"""
        self.logs_dir = Path(path)
        os.environ['LOGS_DIR'] = str(path)
        # 确保目录存在
        self.logs_dir.mkdir(parents=True, exist_ok=True)
    
    def set_proxy(self, http_proxy=None, https_proxy=None):
        """设置代理"""
        if http_proxy:
            self.http_proxy = http_proxy
            os.environ['HTTP_PROXY'] = http_proxy
        if https_proxy:
            self.https_proxy = https_proxy
            os.environ['HTTPS_PROXY'] = https_proxy

# 全局配置实例
config = Config()

def get_config():
    """获取全局配置实例"""
    return config 