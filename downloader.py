"""
下载管理器
基于aria2c的高速下载器，类似hfd.sh的简单直接实现
"""

import os
import re
import json
import time
import threading
import subprocess
import requests
from pathlib import Path
from urllib.parse import urljoin

from config import get_config
from utils import get_current_timestamp, Colors, format_file_size
from task_manager import TaskManager
from file_tracker import FileTracker
from system_monitor import SystemMonitor

class DownloadManager:
    def __init__(self):
        self.config = get_config()
        self.task_manager = TaskManager()
        self.system_monitor = SystemMonitor()
        self.running_tasks = {}
        self.moved_files_strategy = 'skip'  # 默认跳过已移走的文件
        
    def set_moved_files_strategy(self, strategy):
        """设置移走文件处理策略
        
        Args:
            strategy (str): 'skip' 跳过已移走文件，'redownload' 重新下载已移走文件
        """
        self.moved_files_strategy = strategy
        
    def _get_hf_api_url(self, repo_id, is_dataset=False):
        """构建HF API URL"""
        base_url = self.config.get_hf_endpoint()
        repo_type = 'datasets' if is_dataset else 'models'
        return urljoin(base_url, f"api/{repo_type}/{repo_id}")
        
    def _get_repo_info(self, repo_id, is_dataset=False):
        """获取仓库基本信息"""
        try:
            api_url = f"{self.config.get_hf_endpoint()}/api/{'datasets' if is_dataset else 'models'}/{repo_id}"
            
            response = requests.get(api_url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                # 提取关键信息
                return {
                    'id': data.get('id', repo_id),
                    'sha': data.get('sha', ''),
                    'last_modified': data.get('lastModified', ''),
                    'private': data.get('private', False),
                    'downloads': data.get('downloads', 0),
                    'likes': data.get('likes', 0),
                    'tags': data.get('tags', []),
                    'description': data.get('description', ''),
                    'siblings': len(data.get('siblings', [])),
                    'library_name': data.get('library_name', ''),
                    'pipeline_tag': data.get('pipeline_tag', ''),
                    'created_at': data.get('createdAt', ''),
                    'updated_at': data.get('updatedAt', '')
                }
            else:
                return {'error': f'API调用失败: {response.status_code}'}
                
        except Exception as e:
            return {'error': f'获取仓库信息失败: {str(e)}'}
    
    def _get_file_list(self, repo_id, is_dataset=False, revision='main'):
        """快速获取文件列表 - 使用递归API调用"""
        try:
            base_url = self.config.get_hf_endpoint()
            repo_type = 'datasets' if is_dataset else 'models'
            
            # 使用递归API - 一次性获取所有文件
            api_url = f"{base_url}/api/{repo_type}/{repo_id}/tree/{revision}?recursive=true"
            
            # 使用新的配置系统获取认证头部
            headers = self.config.get_auth_headers()
            
            print(f"{Colors.BLUE}📡 正在获取文件列表: {repo_id}{Colors.NC}")
            if self.config.is_hf_auth_available():
                print(f"{Colors.CYAN}🔐 使用认证方式访问{Colors.NC}")
            
            response = requests.get(
                api_url, 
                headers=headers,
                proxies=self.config.get_proxies(),
                timeout=60  # 增加超时时间
            )
            response.raise_for_status()
            
            data = response.json()
            
            files = []
            for item in data:
                if item['type'] == 'file':
                    file_url = f"{base_url}/{repo_type}/{repo_id}/resolve/{revision}/{item['path']}"
                    files.append({
                        'filename': item['path'],
                        'url': file_url,
                        'size': item.get('size', 0)
                    })
            
            print(f"{Colors.GREEN}✓ 获取到 {len(files)} 个文件{Colors.NC}")
            return files
            
        except requests.exceptions.Timeout:
            print(f"{Colors.RED}⚠️ API请求超时{Colors.NC}")
            return []
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                print(f"{Colors.RED}❌ 认证失败: 该仓库需要有效的Hugging Face token{Colors.NC}")
                print(f"{Colors.YELLOW}💡 请使用 --hf-token 参数提供访问令牌{Colors.NC}")
            elif e.response.status_code == 403:
                print(f"{Colors.RED}❌ 访问被拒绝: 您可能没有访问该仓库的权限{Colors.NC}")
            else:
                print(f"{Colors.RED}HTTP错误: {e.response.status_code}{Colors.NC}")
            return []
        except Exception as e:
            print(f"{Colors.RED}获取文件列表失败: {str(e)}{Colors.NC}")
            return []
    
    def _prepare_download_directory(self, task_id, repo_id, local_dir=None):
        """准备下载目录"""
        if local_dir:
            download_path = Path(local_dir)
        else:
            # 使用配置的默认下载目录结构
            downloads_dir = self.config.get_downloads_dir()
            download_path = downloads_dir / repo_id
        
        # 确保目录存在
        download_path.mkdir(parents=True, exist_ok=True)
        
        return download_path

    def start_download(self, task_id):
        """开始下载任务 - 统一使用快速下载模式"""
        try:
            # 重新加载任务数据，确保获取最新的任务信息
            self.task_manager.tasks = self.task_manager._load_tasks()
            
            # 获取任务信息
            task = self.task_manager.get_task(task_id)
            if not task:
                print(f"{Colors.RED}任务 {task_id} 不存在{Colors.NC}")
                return False
            
            print(f"{Colors.YELLOW}🚀 开始高速下载 {task['repo_id']}...{Colors.NC}")
            
            # 准备下载目录
            download_path = self._prepare_download_directory(
                task_id, task['repo_id'], task.get('local_dir')
            )
            
            # 基本系统检查（不检查具体大小）
            print(f"{Colors.YELLOW}正在进行基本系统检查...{Colors.NC}")
            system_check = self.system_monitor.comprehensive_check(download_path, 0)
            
            if (system_check.get('disk_space', {}).get('critical', False) or 
                not system_check.get('disk_space', {}).get('sufficient_space', True)):
                print(f"{Colors.RED}✗ 磁盘空间严重不足{Colors.NC}")
                self.task_manager.update_task_status(task_id, 'failed', 
                    error_message="磁盘空间不足")
                return False
            
            # 更新任务状态
            self.task_manager.update_task_status(task_id, 'running')
            
            # 初始化文件追踪器
            file_tracker = FileTracker(task_id)
            
            # 检查是否是恢复下载（已有元数据）
            if file_tracker.file_status:
                print(f"{Colors.BLUE}🔄 检测到已有下载记录，进行智能断点续传...{Colors.NC}")
                return self._resume_smart_download(task_id, task, download_path, file_tracker)
            else:
                print(f"{Colors.BLUE}🆕 首次下载，获取文件列表...{Colors.NC}")
                return self._start_fresh_download(task_id, task, download_path, file_tracker)
                
        except Exception as e:
            print(f"{Colors.RED}下载失败: {str(e)}{Colors.NC}")
            self.task_manager.update_task_status(task_id, 'failed', error_message=str(e))
            return False
    
    def _start_fresh_download(self, task_id, task, download_path, file_tracker):
        """开始全新下载"""
        try:
            print(f"{Colors.BLUE}🔥 正在获取文件列表...{Colors.NC}")
            
            # 获取文件列表
            file_list = self._get_file_list(task['repo_id'], task.get('is_dataset', False), task.get('revision', 'main'))
            
            if not file_list:
                print(f"{Colors.RED}✗ 无法获取文件列表{Colors.NC}")
                return False
            
            # 保存元数据信息
            print(f"{Colors.BLUE}📋 保存仓库元数据...{Colors.NC}")
            self._save_repo_metadata(task_id, task, file_list, file_tracker)
            
            # 开始下载所有文件
            return self._execute_download(task_id, file_list, download_path, file_tracker)
            
        except Exception as e:
            print(f"{Colors.RED}全新下载失败: {str(e)}{Colors.NC}")
            return False
    
    def _resume_smart_download(self, task_id, task, download_path, file_tracker):
        """智能断点续传下载"""
        try:
            print(f"{Colors.BLUE}🔍 正在检查已下载文件状态...{Colors.NC}")
            
            # 重新验证所有文件状态
            pending_files = []
            completed_count = 0
            moved_files = []  # 已完成但被移走的文件
            total_files = len(file_tracker.file_status)
            
            for filename, file_info in file_tracker.file_status.items():
                file_path = download_path / filename
                current_status = file_info.get('status', 'pending')
                
                if file_path.exists():
                    # 文件存在，检查大小
                    actual_size = file_path.stat().st_size
                    expected_size = file_info.get('expected_size', 0)
                    
                    if expected_size == 0 or actual_size == expected_size:
                        # 文件完整，标记为已完成
                        if current_status != 'completed':
                            file_tracker.update_file_status(filename, 'completed', 
                                                          actual_size=actual_size,
                                                          downloaded_size=actual_size)
                        completed_count += 1
                    else:
                        # 文件不完整，需要重新下载
                        file_tracker.update_file_status(filename, 'pending')
                        pending_files.append({
                            'filename': filename,
                            'url': file_info['url'],
                            'size': expected_size
                        })
                else:
                    # 文件不存在，需要判断是否是已完成但被移走的文件
                    if current_status == 'completed':
                        # 文件已完成但不存在，可能被移走了
                        moved_files.append({
                            'filename': filename,
                            'url': file_info['url'],
                            'size': file_info.get('expected_size', 0),
                            'completed_at': file_info.get('completed_at', ''),
                            'actual_size': file_info.get('actual_size', 0)
                        })
                        
                        # 根据策略决定是否重新下载
                        if self.moved_files_strategy == 'redownload':
                            # 重新下载策略：将已移走的文件标记为pending
                            file_tracker.update_file_status(filename, 'pending')
                            pending_files.append({
                                'filename': filename,
                                'url': file_info['url'],
                                'size': file_info.get('expected_size', 0)
                            })
                        else:
                            # 跳过策略：保持completed状态，不重新下载
                            completed_count += 1  # 仍然计为已完成
                    else:
                        # 文件确实缺失，需要下载
                        file_tracker.update_file_status(filename, 'pending')
                        pending_files.append({
                            'filename': filename,
                            'url': file_info['url'],
                            'size': file_info.get('expected_size', 0)
                        })
            
            print(f"{Colors.GREEN}✓ 文件状态检查完成:{Colors.NC}")
            print(f"  总文件数: {total_files}")
            print(f"  已完成: {completed_count} 个文件")
            print(f"  待下载: {len(pending_files)} 个文件")
            
            # 如果有已完成但被移走的文件，给用户提示
            if moved_files:
                print(f"\n{Colors.YELLOW}📁 检测到 {len(moved_files)} 个已完成但不在下载目录的文件:{Colors.NC}")
                for i, moved_file in enumerate(moved_files[:5], 1):  # 只显示前5个
                    size_str = format_file_size(moved_file['actual_size']) if moved_file['actual_size'] > 0 else "未知大小"
                    print(f"  {i}. {moved_file['filename']} ({size_str})")
                if len(moved_files) > 5:
                    print(f"  ... 还有 {len(moved_files) - 5} 个文件")
                
                if self.moved_files_strategy == 'redownload':
                    print(f"\n{Colors.YELLOW}🔄 将重新下载这些文件{Colors.NC}")
                else:
                    print(f"\n{Colors.CYAN}💡 这些文件可能已被移走到其他存储位置{Colors.NC}")
                    print(f"{Colors.CYAN}💡 系统将跳过这些文件，继续下载其余文件{Colors.NC}")
            
            if len(pending_files) == 0:
                print(f"{Colors.GREEN}🎉 所有需要下载的文件已完成！{Colors.NC}")
                if moved_files and self.moved_files_strategy == 'skip':
                    print(f"{Colors.YELLOW}📊 总计: {completed_count} 个文件已完成（其中 {len(moved_files)} 个已移走）{Colors.NC}")
                self.task_manager.update_task_status(task_id, 'completed')
                self.task_manager.update_task_progress(task_id, '100%')
                return True
            
            # 计算实际需要下载的大小
            pending_size = sum(f['size'] for f in pending_files)
            moved_size = sum(f['actual_size'] for f in moved_files)
            
            print(f"\n{Colors.BLUE}📥 开始下载剩余 {len(pending_files)} 个文件...{Colors.NC}")
            print(f"  待下载大小: {format_file_size(pending_size)}")
            if moved_files:
                if self.moved_files_strategy == 'redownload':
                    print(f"  包含重新下载: {len([f for f in pending_files if f['filename'] in [m['filename'] for m in moved_files]])} 个已移走文件")
                else:
                    print(f"  已移走大小: {format_file_size(moved_size)} (已跳过)")
            
            # 只下载待下载的文件
            return self._execute_download(task_id, pending_files, download_path, file_tracker)
            
        except Exception as e:
            print(f"{Colors.RED}智能断点续传失败: {str(e)}{Colors.NC}")
            return False
    
    def _execute_download(self, task_id, file_list, download_path, file_tracker):
        """执行实际的下载操作"""
        try:
            # 生成aria2c输入文件
            input_content = []
            total_size = 0
            file_size_map = {}  # 文件名到大小的映射
            
            for file_info in file_list:
                url = file_info['url']
                filename = file_info['filename']
                size = file_info.get('size', 0)
                total_size += size
                file_size_map[filename] = size
                
                input_content.extend([
                    url,
                    f"  out={filename}",
                    ""  # 空行分隔
                ])
            
            # 写入aria2c输入文件
            input_file = download_path / f'{task_id}_input.txt'
            with open(input_file, 'w') as f:
                f.write('\n'.join(input_content))
            
            print(f"{Colors.CYAN}📊 准备下载 {len(file_list)} 个文件，总计 {format_file_size(total_size)}{Colors.NC}")
            
            # aria2c参数 - 高性能设置
            aria2c_args = [
                'aria2c',
                '--console-log-level=warn',  # 减少输出，专注于下载
                '--summary-interval=10',     # 10秒显示一次摘要
                '--file-allocation=none',
                '--retry-wait=3',
                '--max-tries=5',
                '--split=5',  # 每个文件5个连接
                '--max-concurrent-downloads=8',  # 同时下载8个文件
                '--continue=true',  # 断点续传
                '--auto-file-renaming=false',
                '--conditional-get=true',
                '--allow-overwrite=true',
                '-i', f'{task_id}_input.txt'  # 使用相对路径，不设置dir参数
            ]
            
            # 使用新的配置系统添加认证头
            auth_headers = self.config.get_auth_headers()
            for header_name, header_value in auth_headers.items():
                aria2c_args.extend(['--header', f'{header_name}: {header_value}'])
            
            if self.config.is_hf_auth_available():
                print(f"{Colors.CYAN}🔐 已配置HF认证headers{Colors.NC}")
            
            print(f"{Colors.BLUE}🚀 启动aria2c高速下载...{Colors.NC}")
            print(f"{Colors.CYAN}命令: aria2c -j8 -x5 -i {task_id}_input.txt{Colors.NC}")
            if self.config.is_hf_auth_available():
                print(f"{Colors.CYAN}      (包含认证headers){Colors.NC}")
            print(f"{Colors.YELLOW}💡 提示：如遇网络问题，aria2c会自动重试{Colors.NC}")
            print(f"{Colors.CYAN}💡 正在启动实时文件监控...{Colors.NC}")
            
            # 执行aria2c
            process = subprocess.Popen(
                aria2c_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                cwd=download_path,  # 设置工作目录
                env=dict(os.environ, no_proxy="*")  # 临时禁用代理避免格式问题
            )
            
            # 存储进程用于取消
            self.running_tasks[task_id] = process
            
            # 启动实时文件监控
            import threading
            import time
            
            completed_files = 0
            failed_files = 0
            last_check_time = time.time()
            last_completed_count = 0
            
            def monitor_files():
                nonlocal completed_files, last_completed_count
                while process.poll() is None:
                    try:
                        time.sleep(5)  # 每5秒检查一次
                        completed_files = self._check_and_update_file_status(
                            file_list, download_path, file_tracker, file_size_map
                        )
                        
                        # 如果有新完成的文件，显示进度
                        if completed_files > last_completed_count:
                            completion_rate = (completed_files / len(file_list)) * 100
                            new_completed = completed_files - last_completed_count
                            print(f"{Colors.GREEN}📈 进度更新: {completed_files}/{len(file_list)} ({completion_rate:.1f}%) [+{new_completed} 个文件]{Colors.NC}")
                            
                            # 更新任务进度
                            self.task_manager.update_task_progress(task_id, f"{completion_rate:.1f}%")
                            last_completed_count = completed_files
                            
                    except Exception as e:
                        print(f"{Colors.YELLOW}⚠️ 文件监控异常: {str(e)}{Colors.NC}")
                        break
            
            # 启动文件监控线程
            monitor_thread = threading.Thread(target=monitor_files, daemon=True)
            monitor_thread.start()
            
            print(f"{Colors.CYAN}=== aria2c 下载状态 ==={Colors.NC}")
            
            # 读取aria2c输出（简化版，主要显示速度信息）
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                    
                if output:
                    line = output.strip()
                    if not line:
                        continue
                        
                    # 只显示重要的信息
                    if '[DL:' in line or 'Download complete' in line or 'ERROR' in line:
                        print(f"{Colors.BLUE}📊 {line}{Colors.NC}")
            
            # 等待监控线程结束
            if monitor_thread.is_alive():
                monitor_thread.join(timeout=5)
            
            # 清理
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            
            # 清理输入文件
            if input_file.exists():
                input_file.unlink()
            
            return_code = process.poll()
            success = return_code == 0
            
            # 最后再检查一次所有文件状态
            print(f"{Colors.BLUE}📋 进行最终文件验证...{Colors.NC}")
            final_completed = self._check_and_update_file_status(
                file_list, download_path, file_tracker, file_size_map
            )
            final_failed = len(file_list) - final_completed
            
            if success:
                print(f"{Colors.GREEN}✓ 下载完成！{Colors.NC}")
                print(f"{Colors.GREEN}📁 文件已保存到: {download_path}{Colors.NC}")
                print(f"{Colors.GREEN}📊 成功: {final_completed} 个文件，失败: {final_failed} 个文件{Colors.NC}")
                
                # 生成最终摘要
                self._generate_final_summary(task_id, file_list, file_tracker)
                
                # 更新任务状态
                if final_completed == len(file_list):
                    self.task_manager.update_task_status(task_id, 'completed')
                    self.task_manager.update_task_progress(task_id, '100%')
                else:
                    self.task_manager.update_task_status(task_id, 'failed', 
                        error_message=f"部分下载失败: {final_failed} 个文件")
            else:
                print(f"{Colors.RED}✗ 下载失败，aria2c返回码: {return_code}{Colors.NC}")
                print(f"{Colors.YELLOW}📊 部分完成: {final_completed} 个文件，失败: {final_failed} 个文件{Colors.NC}")
                
                # 更新任务状态
                if final_completed > 0:
                    self.task_manager.update_task_status(task_id, 'failed', 
                        error_message=f"下载失败: {final_failed} 个文件")
                else:
                    self.task_manager.update_task_status(task_id, 'failed', 
                        error_message="下载完全失败")
            
            return success
            
        except Exception as e:
            print(f"{Colors.RED}下载执行异常: {str(e)}{Colors.NC}")
            return False
    
    def _check_and_update_file_status(self, file_list, download_path, file_tracker, file_size_map):
        """检查并更新文件状态"""
        completed_count = 0
        
        try:
            for file_info in file_list:
                filename = file_info['filename']
                file_path = download_path / filename
                
                # 获取当前文件状态
                current_status = file_tracker.get_file_status(filename)
                if not current_status:
                    continue
                    
                # 如果文件已标记为完成，跳过
                if current_status.get('status') == 'completed':
                    completed_count += 1
                    continue
                
                # 检查文件是否存在
                if file_path.exists():
                    actual_size = file_path.stat().st_size
                    expected_size = file_size_map.get(filename, 0)
                    
                    # 检查文件是否下载完成（大小匹配或者有合理的大小）
                    if expected_size == 0 or actual_size == expected_size or actual_size > 0:
                        # 更新为已完成
                        file_tracker.update_file_status(filename, 'completed', 
                                                      actual_size=actual_size,
                                                      downloaded_size=actual_size)
                        completed_count += 1
                    elif actual_size > 0:
                        # 文件正在下载中
                        if current_status.get('status') != 'downloading':
                            file_tracker.update_file_status(filename, 'downloading',
                                                          downloaded_size=actual_size)
                        else:
                            # 更新下载进度
                            file_tracker.update_file_status(filename, 'downloading',
                                                          downloaded_size=actual_size)
                
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️ 状态检查异常: {str(e)}{Colors.NC}")
        
        return completed_count
    
    def _generate_final_summary(self, task_id, file_list, file_tracker):
        """生成最终下载摘要"""
        try:
            completed_files = 0
            failed_files = 0
            total_downloaded_size = 0
            
            for file_info in file_list:
                filename = file_info['filename']
                file_status = file_tracker.get_file_status(filename)
                
                if file_status and file_status.get('status') == 'completed':
                    completed_files += 1
                    total_downloaded_size += file_status.get('actual_size', 0)
                else:
                    failed_files += 1
            
            # 生成并保存下载摘要
            summary = {
                'total_files': len(file_list),
                'completed_files': completed_files,
                'failed_files': failed_files,
                'completion_rate': f"{completed_files/len(file_list)*100:.1f}%",
                'total_downloaded_size': total_downloaded_size,
                'total_downloaded_size_formatted': format_file_size(total_downloaded_size),
                'updated_at': get_current_timestamp()
            }
            
            # 保存摘要
            metadata_dir = self.config.get_metadata_dir() / 'tasks' / task_id
            summary_file = metadata_dir / 'download_summary.json'
            from utils import save_json_file
            save_json_file(summary_file, summary)
            
            print(f"\n{Colors.BOLD}=== 最终下载摘要 ==={Colors.NC}")
            print(f"总文件数: {summary['total_files']}")
            print(f"成功下载: {summary['completed_files']} ({summary['completion_rate']})")
            print(f"失败文件: {summary['failed_files']}")
            print(f"下载大小: {summary['total_downloaded_size_formatted']}")
            
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️ 摘要生成失败: {str(e)}{Colors.NC}")
    
    def _save_repo_metadata(self, task_id, task, file_list, file_tracker):
        """保存仓库元数据信息"""
        try:
            # 获取仓库基本信息
            repo_info = self._get_repo_info(task['repo_id'], task.get('is_dataset', False))
            
            # 构建完整的元数据
            metadata = {
                'repo_id': task['repo_id'],
                'repo_type': 'datasets' if task.get('is_dataset', False) else 'models',
                'revision': task.get('revision', 'main'),
                'task_id': task_id,
                'collected_at': get_current_timestamp(),
                'repo_info': repo_info,
                'total_files': len(file_list),
                'total_size': sum(f.get('size', 0) for f in file_list),
                'total_size_formatted': format_file_size(sum(f.get('size', 0) for f in file_list)),
                'file_list': file_list[:100],  # 保存前100个文件作为示例，避免文件过大
                'download_mode': 'high_speed'
            }
            
            # 保存到file_tracker
            file_tracker.save_task_metadata(metadata)
            
            # 初始化文件列表状态
            file_tracker.initialize_file_list(file_list)
            
            print(f"{Colors.GREEN}✓ 元数据已保存到 metadata/tasks/{task_id}/task_metadata.json{Colors.NC}")
            
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️ 元数据保存失败，但不影响下载: {str(e)}{Colors.NC}")
    
    def _update_download_status(self, task_id, file_list, download_path, file_tracker):
        """更新下载状态和统计信息"""
        try:
            completed_files = 0
            failed_files = 0
            
            print(f"{Colors.BLUE}正在验证下载的文件...{Colors.NC}")
            
            # 检查文件是否存在并验证大小
            for file_info in file_list:
                filename = file_info['filename']
                file_path = download_path / filename
                
                if file_path.exists():
                    # 简单的大小检查
                    actual_size = file_path.stat().st_size
                    expected_size = file_info.get('size', 0)
                    
                    # 如果期望大小为0或者实际大小匹配期望大小，认为下载成功
                    if expected_size == 0 or actual_size == expected_size or actual_size > 0:
                        file_tracker.mark_file_completed(filename, download_path)
                        completed_files += 1
                        print(f"{Colors.GREEN}  ✓ {filename} ({format_file_size(actual_size)}){Colors.NC}")
                    else:
                        file_tracker.update_file_status(filename, 'failed', 
                            error_message=f'大小不匹配: 期望{expected_size}, 实际{actual_size}')
                        failed_files += 1
                        print(f"{Colors.RED}  ✗ {filename} (大小不匹配){Colors.NC}")
                else:
                    file_tracker.update_file_status(filename, 'failed', error_message='文件未下载')
                    failed_files += 1
                    print(f"{Colors.RED}  ✗ {filename} (文件缺失){Colors.NC}")
            
            # 生成并保存下载摘要
            summary = {
                'total_files': len(file_list),
                'completed_files': completed_files,
                'failed_files': failed_files,
                'completion_rate': f"{completed_files/len(file_list)*100:.1f}%",
                'updated_at': get_current_timestamp()
            }
            
            # 保存摘要
            metadata_dir = self.config.get_metadata_dir() / 'tasks' / task_id
            summary_file = metadata_dir / 'download_summary.json'
            from utils import save_json_file
            save_json_file(summary_file, summary)
            
            print(f"{Colors.GREEN}✓ 文件验证完成: {completed_files}/{len(file_list)} 个文件成功{Colors.NC}")
            
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️ 状态更新失败: {str(e)}{Colors.NC}")
    
    def cancel_download(self, task_id):
        """取消下载任务"""
        if task_id in self.running_tasks:
            print(f"{Colors.YELLOW}正在取消任务 {task_id}...{Colors.NC}")
            process = self.running_tasks[task_id]
            process.terminate()
            del self.running_tasks[task_id]
            
        return self.task_manager.cancel_task(task_id)
    
    def resume_download(self, task_id):
        """恢复下载任务"""
        task = self.task_manager.get_task(task_id)
        if not task or task['status'] != 'cancelled':
            return False
        
        return self.start_download(task_id)