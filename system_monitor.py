"""
系统监控器
监控磁盘空间、权限、网络等系统状态
"""

import os
import shutil
import psutil
import requests
from pathlib import Path
from utils import format_file_size, Colors

class SystemMonitor:
    """系统状态监控器"""
    
    def __init__(self):
        self.min_free_space = 1024 * 1024 * 1024  # 1GB 最小剩余空间
        self.warning_threshold = 0.9  # 磁盘使用率警告阈值90%
    
    def check_disk_space(self, path, required_size=0):
        """检查磁盘空间"""
        try:
            # 获取磁盘使用情况
            disk_usage = shutil.disk_usage(path)
            total_space = disk_usage.total
            free_space = disk_usage.free
            used_space = disk_usage.used
            
            usage_percent = used_space / total_space
            
            result = {
                'total_space': total_space,
                'free_space': free_space,
                'used_space': used_space,
                'usage_percent': usage_percent,
                'total_formatted': format_file_size(total_space),
                'free_formatted': format_file_size(free_space),
                'used_formatted': format_file_size(used_space),
                'usage_percent_formatted': f"{usage_percent*100:.1f}%"
            }
            
            # 检查是否有足够空间
            if required_size > 0:
                result['sufficient_space'] = free_space >= required_size
                result['required_size'] = required_size
                result['required_formatted'] = format_file_size(required_size)
            else:
                result['sufficient_space'] = free_space >= self.min_free_space
            
            # 检查警告状态
            result['warning'] = usage_percent >= self.warning_threshold
            result['critical'] = free_space < self.min_free_space
            
            return result
            
        except Exception as e:
            return {
                'error': str(e),
                'sufficient_space': False,
                'critical': True
            }
    
    def check_write_permission(self, path):
        """检查写入权限"""
        try:
            path = Path(path)
            
            # 确保目录存在
            path.mkdir(parents=True, exist_ok=True)
            
            # 测试写入权限
            test_file = path / '.write_test'
            try:
                test_file.write_text('test')
                test_file.unlink()
                return {'writable': True}
            except Exception as e:
                return {'writable': False, 'error': str(e)}
                
        except Exception as e:
            return {'writable': False, 'error': str(e)}
    
    def check_network_connectivity(self, url="https://hf-mirror.com", timeout=10):
        """检查网络连接"""
        try:
            response = requests.head(url, timeout=timeout)
            return {
                'connected': True,
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
        except requests.RequestException as e:
            return {
                'connected': False,
                'error': str(e)
            }
    
    def check_system_resources(self):
        """检查系统资源"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 内存使用情况
            memory = psutil.virtual_memory()
            
            # 负载平均值（Linux/Unix）
            try:
                load_avg = os.getloadavg()
            except:
                load_avg = None
            
            return {
                'cpu_percent': cpu_percent,
                'memory_total': memory.total,
                'memory_available': memory.available,
                'memory_percent': memory.percent,
                'memory_total_formatted': format_file_size(memory.total),
                'memory_available_formatted': format_file_size(memory.available),
                'load_avg': load_avg
            }
        except Exception as e:
            return {'error': str(e)}
    
    def comprehensive_check(self, download_path, required_size=0):
        """全面系统检查"""
        results = {
            'timestamp': None,
            'disk_space': None,
            'write_permission': None,
            'network': None,
            'system_resources': None,
            'overall_status': 'unknown'
        }
        
        try:
            from utils import get_current_timestamp
            results['timestamp'] = get_current_timestamp()
            
            # 检查磁盘空间
            disk_check = self.check_disk_space(download_path, required_size)
            results['disk_space'] = disk_check
            
            # 检查写入权限
            perm_check = self.check_write_permission(download_path)
            results['write_permission'] = perm_check
            
            # 检查网络连接
            net_check = self.check_network_connectivity()
            results['network'] = net_check
            
            # 检查系统资源
            sys_check = self.check_system_resources()
            results['system_resources'] = sys_check
            
            # 综合评估
            if (disk_check.get('critical', False) or 
                not disk_check.get('sufficient_space', False)):
                results['overall_status'] = 'critical'
            elif (not perm_check.get('writable', False) or 
                  not net_check.get('connected', False)):
                results['overall_status'] = 'error'
            elif disk_check.get('warning', False):
                results['overall_status'] = 'warning'
            else:
                results['overall_status'] = 'ok'
                
        except Exception as e:
            results['error'] = str(e)
            results['overall_status'] = 'error'
        
        return results
    
    def print_system_status(self, check_result):
        """打印系统状态"""
        print(f"\n{Colors.BOLD}=== 系统状态检查 ==={Colors.NC}")
        
        # 磁盘空间
        disk = check_result.get('disk_space', {})
        if 'error' in disk:
            print(f"{Colors.RED}✗ 磁盘检查失败: {disk['error']}{Colors.NC}")
        else:
            status_color = Colors.RED if disk.get('critical') else Colors.YELLOW if disk.get('warning') else Colors.GREEN
            print(f"{status_color}● 磁盘空间: {disk.get('free_formatted', 'N/A')} 可用 / {disk.get('total_formatted', 'N/A')} 总计 ({disk.get('usage_percent_formatted', 'N/A')} 已使用){Colors.NC}")
        
        # 写入权限
        perm = check_result.get('write_permission', {})
        if perm.get('writable'):
            print(f"{Colors.GREEN}✓ 写入权限: 正常{Colors.NC}")
        else:
            print(f"{Colors.RED}✗ 写入权限: 失败 - {perm.get('error', 'Unknown error')}{Colors.NC}")
        
        # 网络连接
        net = check_result.get('network', {})
        if net.get('connected'):
            print(f"{Colors.GREEN}✓ 网络连接: 正常 (响应时间: {net.get('response_time', 0):.2f}s){Colors.NC}")
        else:
            print(f"{Colors.RED}✗ 网络连接: 失败 - {net.get('error', 'Unknown error')}{Colors.NC}")
        
        # 系统资源
        sys_info = check_result.get('system_resources', {})
        if 'error' not in sys_info:
            cpu_color = Colors.RED if sys_info.get('cpu_percent', 0) > 80 else Colors.YELLOW if sys_info.get('cpu_percent', 0) > 60 else Colors.GREEN
            mem_color = Colors.RED if sys_info.get('memory_percent', 0) > 80 else Colors.YELLOW if sys_info.get('memory_percent', 0) > 60 else Colors.GREEN
            
            print(f"{cpu_color}● CPU使用率: {sys_info.get('cpu_percent', 0):.1f}%{Colors.NC}")
            print(f"{mem_color}● 内存使用: {sys_info.get('memory_available_formatted', 'N/A')} 可用 / {sys_info.get('memory_total_formatted', 'N/A')} 总计 ({sys_info.get('memory_percent', 0):.1f}% 已使用){Colors.NC}")
        
        # 总体状态
        overall = check_result.get('overall_status', 'unknown')
        status_colors = {
            'ok': Colors.GREEN,
            'warning': Colors.YELLOW,
            'error': Colors.RED,
            'critical': Colors.RED
        }
        status_color = status_colors.get(overall, Colors.GRAY)
        
        print(f"\n{status_color}总体状态: {overall.upper()}{Colors.NC}")
        
        return overall == 'ok' 