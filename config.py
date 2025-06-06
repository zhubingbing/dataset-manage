#!/usr/bin/env python3
"""
配置管理模块
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional

class Config:
    """配置管理类"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(config_file)
        self.config = self.load_config()
        
    def load_config(self) -> Dict:
        """加载配置文件"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"警告: 无法加载配置文件 {self.config_file}: {e}")
        
        # 返回默认配置
        return self.get_default_config()
        
    def get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "download": {
                "tool": "aria2c",
                "max_connections": 16,
                "split": 16, 
                "timeout": 60,
                "retry": 3,
                "retry_wait": 3,
                "max_download_limit": "0",
                "continue": True,
                "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            },
            "paths": {
                "downloads_dir": "./downloads",
                "metadata_dir": "./metadata",
                "logs_dir": "./logs"
            },
            "network": {
                "hf_endpoint": "https://hf-mirror.com",
                "proxy": None,
                "timeout": 30,
                "max_retries": 3
            },
            "huggingface": {
                "username": None,
                "token": None
            },
            "system": {
                "max_concurrent_downloads": 3,
                "disk_space_threshold": 1024,  # MB
                "auto_cleanup": False
            }
        }
        
    def save_config(self):
        """保存配置到文件"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"警告: 无法保存配置文件: {e}")
            
    def get(self, key: str, default=None):
        """获取配置值，支持点号路径"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
                
        return value
        
    def set(self, key: str, value):
        """设置配置值，支持点号路径"""
        keys = key.split('.')
        config = self.config
        
        # 导航到最后一层
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
            
        # 设置值
        config[keys[-1]] = value
        
    def get_hf_auth(self) -> tuple[Optional[str], Optional[str]]:
        """获取Hugging Face认证信息"""
        # 优先从环境变量获取
        username = os.environ.get('HF_USERNAME')
        token = os.environ.get('HF_TOKEN')
        
        # 如果环境变量没有，从配置文件获取
        if not username:
            username = self.get('huggingface.username')
        if not token:
            token = self.get('huggingface.token')
            
        return username, token
        
    def set_hf_auth(self, username: Optional[str] = None, token: Optional[str] = None):
        """设置Hugging Face认证信息"""
        if username is not None:
            self.set('huggingface.username', username)
        if token is not None:
            self.set('huggingface.token', token)
            
    def get_auth_headers(self) -> Dict[str, str]:
        """获取认证HTTP头部"""
        headers = {}
        username, token = self.get_hf_auth()
        
        if token:
            headers['Authorization'] = f'Bearer {token}'
            
        # 添加User-Agent
        user_agent = self.get('download.user_agent')
        if user_agent:
            headers['User-Agent'] = user_agent
            
        return headers
        
    def is_hf_auth_available(self) -> bool:
        """检查是否有可用的HF认证信息"""
        username, token = self.get_hf_auth()
        return bool(token)  # 实际上只需要token就够了
        
    def get_hf_endpoint(self) -> str:
        """获取HF endpoint，支持环境变量覆盖"""
        # 优先从环境变量获取
        endpoint = os.environ.get('HF_ENDPOINT')
        if endpoint:
            return endpoint
            
        # 从配置文件获取
        return self.get('network.hf_endpoint', 'https://hf-mirror.com')

# 全局配置实例
config = Config()

# 向后兼容的函数
def get_config():
    """获取全局配置实例"""
    return config

# 向后兼容的传统方法
class LegacyConfigMethods:
    """为了保持向后兼容而添加的传统配置方法"""
    
    def __init__(self, config_instance):
        self.config = config_instance
    
    def get_hf_endpoint(self):
        """获取HF端点"""
        return self.config.get_hf_endpoint()
    
    def get_metadata_dir(self):
        """获取元数据目录"""
        from pathlib import Path
        return Path(self.config.get('paths.metadata_dir', './metadata'))
    
    def get_downloads_dir(self):
        """获取下载目录"""
        from pathlib import Path
        return Path(self.config.get('paths.downloads_dir', './downloads'))
    
    def get_logs_dir(self):
        """获取日志目录"""
        from pathlib import Path
        return Path(self.config.get('paths.logs_dir', './logs'))
    
    def set_metadata_dir(self, path):
        """设置元数据目录"""
        self.config.set('paths.metadata_dir', str(path))
        self.config.save_config()
    
    def set_downloads_dir(self, path):
        """设置下载目录"""
        self.config.set('paths.downloads_dir', str(path))
        self.config.save_config()
    
    def set_logs_dir(self, path):
        """设置日志目录"""
        self.config.set('paths.logs_dir', str(path))
        self.config.save_config()
    
    def get_proxies(self):
        """获取代理配置"""
        proxy = self.config.get('network.proxy')
        if proxy:
            return {
                'http': proxy,
                'https': proxy
            }
        return None

# 为全局配置实例添加传统方法
for method_name in dir(LegacyConfigMethods):
    if not method_name.startswith('_') and method_name != 'config':
        setattr(config, method_name, getattr(LegacyConfigMethods(config), method_name)) 