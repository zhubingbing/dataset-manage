"""
工具函数和常量定义
"""

import logging
import os
import json
from pathlib import Path
from datetime import datetime
import uuid

class Colors:
    """终端颜色定义"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    GRAY = '\033[0;37m'
    NC = '\033[0m'  # No Color
    BOLD = '\033[1m'

def setup_logging():
    """设置日志"""
    from config import get_config
    config = get_config()
    logs_dir = config.get_logs_dir()
    logs_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(logs_dir / 'dataset_manager.log'),
            logging.StreamHandler()
        ]
    )

def ensure_data_dir():
    """确保数据目录存在"""
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    return data_dir

def load_json_file(file_path, default=None):
    """加载JSON文件"""
    if default is None:
        default = {}
    
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return default
    except (json.JSONDecodeError, IOError) as e:
        logging.warning(f"无法加载JSON文件 {file_path}: {e}")
        return default

def save_json_file(file_path, data):
    """保存JSON文件"""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except (IOError, TypeError) as e:
        logging.error(f"无法保存JSON文件 {file_path}: {e}")
        return False

def generate_task_id():
    """生成任务ID"""
    return str(uuid.uuid4())[:8]

def get_current_timestamp():
    """获取当前时间戳"""
    return datetime.now().isoformat()

def format_file_size(size_bytes):
    """格式化文件大小显示"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def validate_repo_id(repo_id):
    """验证仓库ID格式"""
    if not repo_id:
        return False
    
    # 允许简单名称（如gpt2）或组织/仓库名称（如openai/gpt-2）
    if '/' in repo_id:
        parts = repo_id.split('/')
        if len(parts) != 2 or not all(part.strip() for part in parts):
            return False
    
    # 检查是否包含非法字符
    import re
    if not re.match(r'^[a-zA-Z0-9._-]+(/[a-zA-Z0-9._-]+)?$', repo_id):
        return False
        
    return True

def check_command_exists(command):
    """检查命令是否存在"""
    import shutil
    return shutil.which(command) is not None

def ensure_downloads_dir():
    """确保下载目录存在"""
    downloads_dir = Path('downloads')
    downloads_dir.mkdir(exist_ok=True)
    return downloads_dir 