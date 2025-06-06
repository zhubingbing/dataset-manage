"""
分批下载管理器
专门处理大数据集的分批下载，支持存储空间限制和换盘场景
"""

import os
import shutil
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from config import get_config
from utils import Colors, format_file_size, get_current_timestamp
from file_tracker import FileTracker
from system_monitor import SystemMonitor
from downloader import DownloadManager

class BatchDownloadManager:
    """分批下载管理器"""
    
    def __init__(self):
        self.config = get_config()
        self.system_monitor = SystemMonitor()
        self.download_manager = DownloadManager()
        
    def analyze_dataset_size(self, repo_id: str, is_dataset: bool = False, 
                           quick_mode: bool = False, 
                           sample_size: int = 100,
                           timeout: int = 30) -> Dict:
        """分析数据集大小和文件分布
        
        Args:
            repo_id: 仓库ID
            is_dataset: 是否为数据集
            quick_mode: 快速模式，仅采样分析
            sample_size: 采样文件数量
            timeout: 超时时间（秒）
        """
        print(f"{Colors.YELLOW}正在分析数据集 {repo_id}...{Colors.NC}")
        
        start_time = time.time()
        
        # 获取文件列表（带超时）
        try:
            print(f"{Colors.BLUE}📡 获取文件列表...{Colors.NC}")
            file_list = self._get_file_list_with_timeout(repo_id, is_dataset, timeout)
            
            if not file_list:
                print(f"{Colors.YELLOW}⚠️  无法获取文件列表，尝试预估分析...{Colors.NC}")
                return self._estimate_analysis(repo_id, is_dataset, start_time)
            
            total_files = len(file_list)
            print(f"{Colors.GREEN}✓ 找到 {total_files} 个文件{Colors.NC}")
            
            # 如果文件数量很大且启用快速模式，使用采样分析
            if quick_mode or total_files > 1000:
                print(f"{Colors.YELLOW}🔄 数据集较大，使用快速采样分析（采样 {min(sample_size, total_files)} 个文件）{Colors.NC}")
                return self._quick_analyze(file_list, sample_size, start_time)
            else:
                print(f"{Colors.BLUE}📊 执行完整分析...{Colors.NC}")
                return self._full_analyze(file_list, start_time)
                
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"{Colors.RED}✗ 分析失败 ({elapsed:.1f}s): {str(e)}{Colors.NC}")
            print(f"{Colors.YELLOW}🔄 尝试预估分析...{Colors.NC}")
            return self._estimate_analysis(repo_id, is_dataset, start_time)
    
    def _get_file_list_with_timeout(self, repo_id: str, is_dataset: bool, timeout: int) -> List[Dict]:
        """带超时的文件列表获取"""
        result = [None]
        error = [None]
        
        def get_files():
            try:
                result[0] = self.download_manager._get_file_list(repo_id, is_dataset)
            except Exception as e:
                error[0] = e
        
        # 创建线程执行获取文件列表
        thread = threading.Thread(target=get_files)
        thread.daemon = True
        thread.start()
        thread.join(timeout)
        
        if thread.is_alive():
            print(f"{Colors.RED}⚠️  获取文件列表超时 ({timeout}s)，建议使用快速模式{Colors.NC}")
            return []
        
        if error[0]:
            raise error[0]
            
        return result[0] or []
    
    def _quick_analyze(self, file_list: List[Dict], sample_size: int, start_time: float) -> Dict:
        """快速采样分析"""
        total_files = len(file_list)
        
        # 智能采样：包含最大文件和随机采样
        sorted_by_size = sorted(file_list, key=lambda x: x.get('size', 0), reverse=True)
        
        # 取前50%的大文件 + 随机采样
        large_files_count = min(sample_size // 2, len(sorted_by_size))
        large_files = sorted_by_size[:large_files_count]
        
        # 从剩余文件中随机采样
        remaining_files = sorted_by_size[large_files_count:]
        import random
        random_sample_count = min(sample_size - large_files_count, len(remaining_files))
        random_files = random.sample(remaining_files, random_sample_count) if remaining_files else []
        
        sample_files = large_files + random_files
        
        # 计算采样统计
        sample_total_size = sum(f.get('size', 0) for f in sample_files)
        sample_avg_size = sample_total_size / len(sample_files) if sample_files else 0
        
        # 估算总大小
        estimated_total_size = int(sample_avg_size * total_files)
        
        # 分析文件类型（基于采样）
        file_types = self._analyze_file_types(sample_files)
        
        elapsed = time.time() - start_time
        
        print(f"{Colors.GREEN}✓ 快速分析完成 ({elapsed:.1f}s){Colors.NC}")
        print(f"  📁 总文件数: {total_files}")
        print(f"  📊 采样文件: {len(sample_files)}")
        print(f"  📏 估算总大小: {format_file_size(estimated_total_size)}")
        
        return {
            'analysis_mode': 'quick',
            'analysis_time': elapsed,
            'total_files': total_files,
            'sample_files': len(sample_files),
            'sample_size': sample_total_size,
            'estimated_total_size': estimated_total_size,
            'total_size_formatted': format_file_size(estimated_total_size),
            'largest_files': sorted_by_size[:10],
            'file_types': file_types,
            'file_list': file_list,  # 完整列表用于后续规划
            'is_estimated': True
        }
    
    def _full_analyze(self, file_list: List[Dict], start_time: float) -> Dict:
        """完整分析"""
        print(f"{Colors.BLUE}📊 分析文件大小和类型...{Colors.NC}")
        
        # 并发计算统计信息
        with ThreadPoolExecutor(max_workers=4) as executor:
            # 提交任务
            futures = {
                'total_size': executor.submit(self._calculate_total_size, file_list),
                'file_types': executor.submit(self._analyze_file_types, file_list),
                'sorted_files': executor.submit(self._sort_files_by_size, file_list)
            }
            
            # 获取结果
            results = {}
            for key, future in futures.items():
                try:
                    results[key] = future.result(timeout=15)  # 15秒超时
                except Exception as e:
                    print(f"{Colors.RED}⚠️  {key} 计算失败: {e}{Colors.NC}")
                    results[key] = None
        
        total_size = results.get('total_size', 0)
        file_types = results.get('file_types', {})
        sorted_files = results.get('sorted_files', [])
        
        elapsed = time.time() - start_time
        
        print(f"{Colors.GREEN}✓ 完整分析完成 ({elapsed:.1f}s){Colors.NC}")
        print(f"  📁 总文件数: {len(file_list)}")
        print(f"  📏 总大小: {format_file_size(total_size)}")
        
        return {
            'analysis_mode': 'full',
            'analysis_time': elapsed,
            'total_files': len(file_list),
            'total_size': total_size,
            'total_size_formatted': format_file_size(total_size),
            'largest_files': sorted_files[:10],
            'file_types': file_types,
            'file_list': file_list,
            'is_estimated': False
        }
    
    def _calculate_total_size(self, file_list: List[Dict]) -> int:
        """计算总大小"""
        return sum(f.get('size', 0) for f in file_list)
    
    def _analyze_file_types(self, file_list: List[Dict]) -> Dict:
        """分析文件类型分布"""
        file_types = {}
        for file_info in file_list:
            ext = Path(file_info['filename']).suffix.lower()
            if not ext:
                ext = 'no_extension'
            if ext not in file_types:
                file_types[ext] = {'count': 0, 'size': 0}
            file_types[ext]['count'] += 1
            file_types[ext]['size'] += file_info.get('size', 0)
        return file_types
    
    def _sort_files_by_size(self, file_list: List[Dict]) -> List[Dict]:
        """按大小排序文件"""
        return sorted(file_list, key=lambda x: x.get('size', 0), reverse=True)
    
    def _estimate_analysis(self, repo_id: str, is_dataset: bool, start_time: float) -> Dict:
        """预估分析模式 - 当无法获取详细文件列表时的fallback"""
        elapsed = time.time() - start_time
        
        print(f"{Colors.CYAN}🔍 使用预估分析模式...{Colors.NC}")
        
        # 基于数据集类型的经验估算
        if is_dataset:
            # 数据集通常较大
            estimated_files = 1000  # 预估文件数
            estimated_avg_size = 50 * 1024 * 1024  # 50MB平均大小
            note = "大型数据集（经验估算）"
        else:
            # 模型通常相对较小
            estimated_files = 100  # 预估文件数
            estimated_avg_size = 10 * 1024 * 1024  # 10MB平均大小
            note = "模型文件（经验估算）"
        
        estimated_total_size = estimated_files * estimated_avg_size
        
        print(f"{Colors.YELLOW}⚠️  预估分析完成 ({elapsed:.1f}s){Colors.NC}")
        print(f"  📁 预估文件数: {estimated_files}")
        print(f"  📏 预估总大小: {format_file_size(estimated_total_size)}")
        print(f"  📝 说明: {note}")
        
        return {
            'analysis_mode': 'estimate',
            'analysis_time': elapsed,
            'total_files': estimated_files,
            'estimated_total_size': estimated_total_size,
            'total_size': estimated_total_size,  # 向后兼容
            'total_size_formatted': format_file_size(estimated_total_size),
            'largest_files': [],
            'file_types': {'unknown': {'count': estimated_files, 'size': estimated_total_size}},
            'file_list': [],  # 空列表，后续需要实际下载时再获取
            'is_estimated': True,
            'estimation_note': note,
            'recommendation': f"对于此超大数据集，建议先使用 plan-batch 命令进行分批规划"
        }
    
    def plan_batch_download(self, repo_id: str, available_space: int, 
                          is_dataset: bool = False, 
                          safety_margin: float = 0.9) -> Dict:
        """规划分批下载策略"""
        
        analysis = self.analyze_dataset_size(repo_id, is_dataset)
        if 'error' in analysis:
            return analysis
        
        file_list = analysis['file_list']
        total_size = analysis['total_size']
        
        # 计算安全可用空间（留出10%安全余量）
        safe_space = int(available_space * safety_margin)
        
        print(f"\n{Colors.BOLD}=== 分批下载规划 ==={Colors.NC}")
        print(f"数据集总大小: {format_file_size(total_size)}")
        print(f"可用空间: {format_file_size(available_space)}")
        print(f"安全可用空间: {format_file_size(safe_space)} (预留{int((1-safety_margin)*100)}%安全余量)")
        
        if total_size <= safe_space:
            print(f"{Colors.GREEN}✓ 空间充足，可以一次性下载{Colors.NC}")
            return {
                'strategy': 'single_batch',
                'batches': [{'files': file_list, 'size': total_size}],
                'total_batches': 1
            }
        
        # 需要分批下载
        batches = self._create_batches(file_list, safe_space)
        
        print(f"{Colors.YELLOW}需要分 {len(batches)} 批次下载{Colors.NC}")
        for i, batch in enumerate(batches, 1):
            print(f"  批次 {i}: {len(batch['files'])} 个文件, {format_file_size(batch['size'])}")
        
        return {
            'strategy': 'multi_batch',
            'batches': batches,
            'total_batches': len(batches),
            'available_space': available_space,
            'safe_space': safe_space
        }
    
    def _create_batches(self, file_list: List[Dict], max_batch_size: int) -> List[Dict]:
        """创建下载批次"""
        batches = []
        current_batch = {'files': [], 'size': 0}
        
        # 按文件大小排序，优先下载大文件
        sorted_files = sorted(file_list, key=lambda x: x.get('size', 0), reverse=True)
        
        for file_info in sorted_files:
            file_size = file_info.get('size', 0)
            
            # 如果单个文件就超过批次限制
            if file_size > max_batch_size:
                # 单独成为一个批次
                if current_batch['files']:
                    batches.append(current_batch)
                    current_batch = {'files': [], 'size': 0}
                
                batches.append({
                    'files': [file_info],
                    'size': file_size,
                    'note': '超大文件单独批次'
                })
                continue
            
            # 检查是否能放入当前批次
            if current_batch['size'] + file_size <= max_batch_size:
                current_batch['files'].append(file_info)
                current_batch['size'] += file_size
            else:
                # 当前批次已满，开始新批次
                if current_batch['files']:
                    batches.append(current_batch)
                current_batch = {'files': [file_info], 'size': file_size}
        
        # 添加最后一个批次
        if current_batch['files']:
            batches.append(current_batch)
        
        return batches
    
    def execute_batch_download(self, task_id: str, plan: Dict, 
                             current_batch: int = 1, 
                             auto_proceed: bool = False) -> bool:
        """执行分批下载"""
        
        if plan['strategy'] == 'single_batch':
            print(f"{Colors.GREEN}执行单批次下载...{Colors.NC}")
            return self.download_manager.start_download(task_id)
        
        # 多批次下载
        total_batches = plan['total_batches']
        
        if current_batch > total_batches:
            print(f"{Colors.GREEN}✓ 所有批次已下载完成{Colors.NC}")
            return True
        
        print(f"\n{Colors.BOLD}=== 执行批次 {current_batch}/{total_batches} ==={Colors.NC}")
        
        batch = plan['batches'][current_batch - 1]
        batch_files = batch['files']
        batch_size = batch['size']
        
        print(f"批次信息: {len(batch_files)} 个文件, {format_file_size(batch_size)}")
        
        # 检查当前可用空间
        task_manager = self.download_manager.task_manager
        task = task_manager.get_task(task_id)
        download_path = self.download_manager._prepare_download_directory(
            task_id, task['repo_id'], task.get('local_dir')
        )
        
        system_check = self.system_monitor.comprehensive_check(download_path, batch_size)
        
        if system_check['disk_space']['status'] in ['critical', 'error']:
            print(f"{Colors.RED}✗ 磁盘空间不足，无法继续下载此批次{Colors.NC}")
            print(f"需要至少 {format_file_size(batch_size)} 空间")
            return False
        
        # 创建当前批次的文件跟踪器
        file_tracker = FileTracker(f"{task_id}_batch_{current_batch}")
        file_tracker.initialize_file_list(batch_files)
        
        # 保存批次信息到任务元数据
        self._save_batch_progress(task_id, current_batch, total_batches, batch_size)
        
        # 执行当前批次下载
        print(f"{Colors.BLUE}开始下载批次 {current_batch}...{Colors.NC}")
        
        success = self._download_batch(task_id, task, batch_files, download_path, file_tracker)
        
        if success:
            print(f"{Colors.GREEN}✓ 批次 {current_batch} 下载完成{Colors.NC}")
            
            if current_batch < total_batches:
                print(f"\n{Colors.YELLOW}=== 准备下一批次 ==={Colors.NC}")
                print(f"批次 {current_batch} 已完成，还有 {total_batches - current_batch} 个批次")
                
                if not auto_proceed:
                    print(f"{Colors.CYAN}请完成以下操作后继续:{Colors.NC}")
                    print(f"1. 备份/移动当前下载的文件（如需要）")
                    print(f"2. 清理磁盘空间为下一批次腾出空间")
                    print(f"3. 运行: python main.py batch-continue {task_id} {current_batch + 1}")
                    return True
                else:
                    # 自动继续下一批次
                    return self.execute_batch_download(task_id, plan, current_batch + 1, auto_proceed)
            else:
                print(f"{Colors.GREEN}🎉 所有批次下载完成！{Colors.NC}")
                return True
        else:
            print(f"{Colors.RED}✗ 批次 {current_batch} 下载失败{Colors.NC}")
            return False
    
    def _download_batch(self, task_id: str, task: Dict, file_list: List[Dict], 
                       download_path: Path, file_tracker: FileTracker) -> bool:
        """下载单个批次"""
        
        if task['tool'] == 'aria2c':
            return self.download_manager._download_with_aria2c(
                task_id, task, file_list, download_path, file_tracker
            )
        else:
            return self.download_manager._download_with_wget(
                task_id, task, file_list, download_path, file_tracker
            )
    
    def _save_batch_progress(self, task_id: str, current_batch: int, 
                           total_batches: int, batch_size: int):
        """保存批次进度信息"""
        batch_metadata = {
            'task_id': task_id,
            'current_batch': current_batch,
            'total_batches': total_batches,
            'batch_size': batch_size,
            'timestamp': get_current_timestamp()
        }
        
        metadata_dir = self.config.get_metadata_dir() / 'tasks' / task_id
        metadata_dir.mkdir(parents=True, exist_ok=True)
        
        batch_file = metadata_dir / 'batch_progress.json'
        
        from utils import save_json_file
        save_json_file(batch_file, batch_metadata)
    
    def get_batch_progress(self, task_id: str) -> Optional[Dict]:
        """获取批次进度信息"""
        metadata_dir = self.config.get_metadata_dir() / 'tasks' / task_id
        batch_file = metadata_dir / 'batch_progress.json'
        
        if batch_file.exists():
            from utils import load_json_file
            return load_json_file(batch_file)
        
        return None
    
    def estimate_disk_usage_over_time(self, plan: Dict) -> List[Dict]:
        """估算分批下载的磁盘使用情况"""
        usage_timeline = []
        cumulative_size = 0
        
        for i, batch in enumerate(plan['batches'], 1):
            cumulative_size += batch['size']
            usage_timeline.append({
                'batch': i,
                'batch_size': batch['size'],
                'cumulative_size': cumulative_size,
                'files_count': len(batch['files']),
                'batch_size_formatted': format_file_size(batch['size']),
                'cumulative_size_formatted': format_file_size(cumulative_size)
            })
        
        return usage_timeline
    
    def suggest_disk_management_strategy(self, plan: Dict, available_space: int) -> Dict:
        """建议磁盘管理策略"""
        
        if plan['strategy'] == 'single_batch':
            return {'strategy': 'no_management_needed'}
        
        timeline = self.estimate_disk_usage_over_time(plan)
        max_batch_size = max(batch['size'] for batch in plan['batches'])
        
        suggestions = []
        
        # 如果最大批次接近可用空间
        if max_batch_size > available_space * 0.8:
            suggestions.append({
                'type': 'warning',
                'message': f"最大批次大小 {format_file_size(max_batch_size)} 接近可用空间限制"
            })
        
        # 建议中间清理策略
        if len(plan['batches']) > 2:
            suggestions.append({
                'type': 'recommendation', 
                'message': "建议每完成2-3个批次后进行一次文件备份和清理"
            })
        
        # 如果有超大文件
        large_batches = [b for b in plan['batches'] if b.get('note') == '超大文件单独批次']
        if large_batches:
            suggestions.append({
                'type': 'info',
                'message': f"检测到 {len(large_batches)} 个超大文件需要单独处理"
            })
        
        return {
            'strategy': 'batch_management',
            'timeline': timeline,
            'suggestions': suggestions,
            'estimated_peak_usage': format_file_size(max_batch_size),
            'total_batches': len(plan['batches'])
        } 