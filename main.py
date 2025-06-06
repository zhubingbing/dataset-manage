#!/usr/bin/env python3
"""
大模型数据集下载管理工具
基于aria2c和wget的简单下载管理器
"""

import argparse
import sys
import os
from pathlib import Path
import time

from dataset_manager import DatasetManager
from downloader import DownloadManager
from task_manager import TaskManager
from utils import setup_logging, Colors, format_file_size
from system_monitor import SystemMonitor
from file_tracker import FileTracker
from config import get_config
from batch_downloader import BatchDownloadManager

def setup_delete_parser(subparsers):
    """设置删除任务解析器"""
    parser = subparsers.add_parser('delete-task', help='删除任务')
    parser.add_argument('task_id', help='任务ID')
    parser.add_argument('--force', action='store_true', help='强制删除，不询问确认')
    parser.add_argument('--keep-files', action='store_true', help='保留下载的文件，只删除任务记录')

def setup_cleanup_parser(subparsers):
    """设置清理所有任务解析器"""
    parser = subparsers.add_parser('cleanup', help='清理所有任务')
    parser.add_argument('--status', choices=['completed', 'failed', 'running', 'cancelled'], 
                       help='只清理指定状态的任务')
    parser.add_argument('--force', action='store_true', help='强制清理，不询问确认')
    parser.add_argument('--keep-files', action='store_true', help='保留下载的文件，只删除任务记录')

def handle_delete_task(args):
    """处理删除任务"""
    from utils import Colors
    
    task_manager = TaskManager()
    task = task_manager.get_task(args.task_id)
    
    if not task:
        print(f"{Colors.RED}任务 {args.task_id} 不存在{Colors.NC}")
        return
    
    # 显示任务信息
    print(f"{Colors.BLUE}准备删除任务:{Colors.NC}")
    print(f"  ID: {args.task_id}")
    print(f"  数据集: {task['repo_id']}")
    print(f"  状态: {task['status']}")
    print(f"  创建时间: {task.get('created_at', 'Unknown')}")
    
    # 检查任务是否正在运行
    if task['status'] == 'running' and not args.force:
        print(f"{Colors.YELLOW}警告：任务正在运行中！{Colors.NC}")
        response = input("是否要强制删除正在运行的任务？(y/N): ")
        if response.lower() != 'y':
            print("取消删除")
            return
    
    # 确认删除
    if not args.force:
        action = "删除任务记录" if args.keep_files else "删除任务和相关文件"
        response = input(f"确认{action}？(y/N): ")
        if response.lower() != 'y':
            print("取消删除")
            return
    
    # 执行删除
    success = delete_task_data(args.task_id, keep_files=args.keep_files)
    
    if success:
        print(f"{Colors.GREEN}✓ 任务 {args.task_id} 删除成功{Colors.NC}")
    else:
        print(f"{Colors.RED}✗ 任务删除失败{Colors.NC}")

def handle_cleanup(args):
    """处理清理所有任务"""
    from utils import Colors
    
    task_manager = TaskManager()
    all_tasks = task_manager.get_all_tasks()
    
    if not all_tasks:
        print(f"{Colors.YELLOW}没有找到任何任务{Colors.NC}")
        return
    
    # 过滤任务
    tasks_to_delete = []
    if args.status:
        tasks_to_delete = [task for task in all_tasks if task['status'] == args.status]
    else:
        tasks_to_delete = all_tasks
    
    if not tasks_to_delete:
        print(f"{Colors.YELLOW}没有找到符合条件的任务{Colors.NC}")
        return
    
    print(f"{Colors.BLUE}准备清理 {len(tasks_to_delete)} 个任务:{Colors.NC}")
    for task in tasks_to_delete:
        task_id = task.get('id') or task.get('task_id')  # 兼容不同的ID字段名
        repo_id = task.get('repo_id', 'Unknown')
        status = task.get('status', 'Unknown')
        print(f"  {task_id} - {repo_id} ({status})")
    
    # 确认清理
    if not args.force:
        action = "删除任务记录" if args.keep_files else "删除任务和相关文件"
        response = input(f"确认{action}？(y/N): ")
        if response.lower() != 'y':
            print("取消清理")
            return
    
    # 执行清理
    success_count = 0
    for task in tasks_to_delete:
        task_id = task.get('id') or task.get('task_id')  # 兼容不同的ID字段名
        if delete_task_data(task_id, keep_files=args.keep_files):
            success_count += 1
            print(f"{Colors.GREEN}✓ 删除 {task_id}{Colors.NC}")
        else:
            print(f"{Colors.RED}✗ 删除 {task_id} 失败{Colors.NC}")
    
    print(f"{Colors.GREEN}清理完成: {success_count}/{len(tasks_to_delete)} 个任务删除成功{Colors.NC}")

def delete_task_data(task_id, keep_files=False):
    """删除任务数据"""
    import shutil
    from pathlib import Path
    from utils import Colors
    
    try:
        config = get_config()
        task_manager = TaskManager()
        
        # 获取任务信息
        task = task_manager.get_task(task_id)
        if not task:
            return False
        
        # 删除任务记录
        if task_manager.delete_task(task_id):
            print(f"{Colors.GREEN}✓ 任务记录删除成功{Colors.NC}")
        else:
            print(f"{Colors.YELLOW}⚠️ 任务记录删除失败{Colors.NC}")
        
        # 删除元数据目录
        metadata_dir = config.get_metadata_dir() / 'tasks' / task_id
        if metadata_dir.exists():
            shutil.rmtree(metadata_dir)
            print(f"{Colors.GREEN}✓ 元数据删除成功{Colors.NC}")
        
        # 删除下载文件（如果不保留）
        if not keep_files:
            repo_id = task['repo_id']
            download_path = None
            
            # 尝试从任务中获取自定义路径
            if task.get('local_dir'):
                download_path = Path(task['local_dir'])
            else:
                # 使用默认下载路径
                download_path = config.get_downloads_dir() / repo_id
            
            if download_path and download_path.exists():
                response = input(f"确认删除下载文件夹 {download_path}？(y/N): ")
                if response.lower() == 'y':
                    shutil.rmtree(download_path)
                    print(f"{Colors.GREEN}✓ 下载文件删除成功{Colors.NC}")
                else:
                    print(f"{Colors.YELLOW}保留下载文件: {download_path}{Colors.NC}")
        
        return True
        
    except Exception as e:
        print(f"{Colors.RED}删除任务数据失败: {str(e)}{Colors.NC}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description='大模型数据集下载管理工具 - 支持分批下载',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基本下载
  python main.py download gpt2 --tool aria2c -x 8
  
  # 指定自定义路径
  python main.py --metadata-dir /path/to/metadata --downloads-dir /path/to/downloads download gpt2
  
  # 分批下载大数据集 (30TB数据集, 10TB可用空间)
  python main.py analyze-dataset large-model/30tb-dataset --dataset
  python main.py plan-batch large-model/30tb-dataset --available-space 10737418240000 --dataset
  python main.py batch-download large-model/30tb-dataset --available-space 10737418240000 --dataset
  
  # 换盘后继续下载
  python main.py batch-continue task_abc123 2
  
  # 导入HFD任务
  python main.py import-hfd /path/to/dataset-dir /path/to/output
  python main.py import-hfd /path/to/dataset-dir/.hfd /path/to/output --dry-run
  
  # 查看任务状态
  python main.py list-tasks
  python main.py batch-status task_abc123
        """
    )
    
    # 全局配置选项
    parser.add_argument('--metadata-dir', help='元数据存储目录（默认: metadata）')
    parser.add_argument('--downloads-dir', help='下载文件存储目录（默认: downloads）')
    parser.add_argument('--logs-dir', help='日志文件存储目录（默认: logs）')
    
    # HF认证参数
    parser.add_argument('--hf-username', type=str, help='Hugging Face 用户名 (用于需要认证的仓库)')
    parser.add_argument('--hf-token', type=str, help='Hugging Face 访问令牌 (用于需要认证的仓库)')

    # 任务管理参数
    parser.add_argument('--create-task', action='store_true', help='创建新的下载任务')
    parser.add_argument('--list-tasks', action='store_true', help='列出所有任务')
    parser.add_argument('--resume', action='store_true', help='恢复下载任务')
    parser.add_argument('--status', action='store_true', help='显示下载状态')
    parser.add_argument('--task-id', type=str, help='指定任务ID')
    parser.add_argument('--cancel', action='store_true', help='取消任务')
    parser.add_argument('--delete-task', action='store_true', help='删除任务')
    parser.add_argument('--task-detail', action='store_true', help='显示任务详情')
    parser.add_argument('--clean-completed', action='store_true', help='清理已完成的任务')
    parser.add_argument('--clean-failed', action='store_true', help='清理失败的任务')
    parser.add_argument('--fix-progress', action='store_true', help='修复进度显示问题')

    # 下载参数
    parser.add_argument('--output-dir', type=str, help='下载输出目录')
    parser.add_argument('--base-url', type=str, help='基础URL (默认: https://hf-mirror.com)')
    parser.add_argument('--dataset', action='store_true', help='下载数据集 (默认下载模型)')
    parser.add_argument('--tool', choices=['aria2c', 'wget'], help='下载工具')
    parser.add_argument('--threads', type=int, help='并发线程数')
    parser.add_argument('--exclude', nargs='*', help='排除文件模式')
    parser.add_argument('--include', nargs='*', help='包含文件模式')
    
    # 系统管理参数
    parser.add_argument('--check-system', action='store_true', help='检查系统状态')
    parser.add_argument('--verify', action='store_true', help='验证已下载文件的完整性')
    
    # 批量操作参数  
    parser.add_argument('--batch-file', type=str, help='批量下载配置文件')
    parser.add_argument('--batch-create', action='store_true', help='批量创建任务')
    parser.add_argument('--batch-start', action='store_true', help='批量开始下载')
    parser.add_argument('--batch-status', action='store_true', help='批量状态查询')
    parser.add_argument('--batch-stop', action='store_true', help='批量停止下载')
    
    # 配置参数
    parser.add_argument('--config', type=str, default='config.json', help='配置文件路径')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 添加数据集命令
    add_parser = subparsers.add_parser('add-dataset', help='添加数据集信息')
    add_parser.add_argument('repo_id', help='数据集仓库ID (如: gpt2, bigscience/bloom-560m)')
    add_parser.add_argument('--description', help='数据集描述')
    add_parser.add_argument('--dataset', action='store_true', help='标记为数据集（默认为模型）')
    add_parser.add_argument('--tags', nargs='*', help='标签列表')
    
    # HFD导入命令
    import_parser = subparsers.add_parser('import-hfd', help='导入HFD下载的任务')
    import_parser.add_argument('hfd_dir', help='HFD目录路径（包含.hfd子目录，或直接指向.hfd目录）')
    import_parser.add_argument('output_dir', help='数据集输出目录（文件的实际位置）')
    import_parser.add_argument('--base-url', default='https://hf-mirror.com', help='基础URL (默认: https://hf-mirror.com)')
    import_parser.add_argument('--dry-run', action='store_true', help='只显示摘要，不实际导入')
    
    # 下载命令
    download_parser = subparsers.add_parser('download', help='下载数据集/模型')
    download_parser.add_argument('repo_id', help='要下载的数据集/模型ID')
    download_parser.add_argument('--local-dir', help='本地下载目录')
    download_parser.add_argument('--revision', default='main', help='版本/分支')
    download_parser.add_argument('--dataset', action='store_true', help='标记为数据集（而非模型）')
    
    # 任务管理命令
    subparsers.add_parser('list-datasets', help='列出所有数据集')
    
    status_parser = subparsers.add_parser('status', help='查看任务状态')
    status_parser.add_argument('task_id', help='任务ID')
    
    cancel_parser = subparsers.add_parser('cancel', help='取消任务')
    cancel_parser.add_argument('task_id', help='任务ID')
    
    resume_parser = subparsers.add_parser('resume', help='恢复任务')
    resume_parser.add_argument('task_id', help='任务ID')
    resume_parser.add_argument('--skip-moved-files', action='store_true', 
                              help='自动跳过已完成但被移走的文件（默认行为）')
    resume_parser.add_argument('--redownload-moved-files', action='store_true',
                              help='重新下载已完成但被移走的文件')
    
    # 清理命令  
    subparsers.add_parser('clean', help='清理完成的任务记录')
    
    # 修复进度命令
    subparsers.add_parser('fix-progress', help='修复已完成任务的进度显示')
    
    # 系统检查命令
    check_parser = subparsers.add_parser('check-system', help='检查系统状态')
    check_parser.add_argument('--path', default='.', help='检查路径（默认当前目录）')
    check_parser.add_argument('--size', type=int, default=0, help='预计下载大小（字节）')
    
    # 文件验证命令
    verify_parser = subparsers.add_parser('verify', help='验证下载文件完整性')
    verify_parser.add_argument('task_id', help='任务ID')
    
    # 详细任务信息命令
    detail_parser = subparsers.add_parser('task-detail', help='查看任务详细信息')
    detail_parser.add_argument('task_id', help='任务ID')
    
    # 配置信息命令
    subparsers.add_parser('config', help='显示当前配置信息')
    
    # 分批下载相关命令
    analyze_parser = subparsers.add_parser('analyze-dataset', help='分析数据集大小和结构')
    analyze_parser.add_argument('repo_id', help='数据集仓库ID')
    analyze_parser.add_argument('--dataset', action='store_true', help='标记为数据集')
    analyze_parser.add_argument('--quick', action='store_true', help='快速模式，使用采样分析（适用于大数据集）')
    analyze_parser.add_argument('--sample-size', type=int, default=100, help='快速模式的采样文件数量（默认100）')
    analyze_parser.add_argument('--timeout', type=int, default=30, help='获取文件列表的超时时间（秒，默认30）')
    
    plan_parser = subparsers.add_parser('plan-batch', help='规划分批下载策略')
    plan_parser.add_argument('repo_id', help='数据集仓库ID') 
    plan_parser.add_argument('--available-space', type=int, required=True, help='可用空间（字节）')
    plan_parser.add_argument('--dataset', action='store_true', help='标记为数据集')
    plan_parser.add_argument('--safety-margin', type=float, default=0.9, help='安全余量比例（默认0.9）')
    
    batch_download_parser = subparsers.add_parser('batch-download', help='执行分批下载')
    batch_download_parser.add_argument('repo_id', help='数据集仓库ID')
    batch_download_parser.add_argument('--available-space', type=int, required=True, help='可用空间（字节）')
    batch_download_parser.add_argument('--dataset', action='store_true', help='标记为数据集')
    batch_download_parser.add_argument('--auto-proceed', action='store_true', help='自动继续下一批次')
    batch_download_parser.add_argument('--tool', choices=['aria2c', 'wget'], default='aria2c', help='下载工具')
    
    batch_continue_parser = subparsers.add_parser('batch-continue', help='继续分批下载')
    batch_continue_parser.add_argument('task_id', help='任务ID')
    batch_continue_parser.add_argument('batch_number', type=int, help='继续的批次号')
    
    batch_status_parser = subparsers.add_parser('batch-status', help='查看分批下载状态')
    batch_status_parser.add_argument('task_id', help='任务ID')
    
    delete_parser = subparsers.add_parser('delete-task', help='删除任务')
    delete_parser.add_argument('task_id', help='任务ID')
    delete_parser.add_argument('--force', action='store_true', help='强制删除，不询问确认')
    delete_parser.add_argument('--keep-files', action='store_true', help='保留下载的文件，只删除任务记录')
    
    cleanup_parser = subparsers.add_parser('cleanup', help='清理所有任务')
    cleanup_parser.add_argument('--status', choices=['completed', 'failed', 'running', 'cancelled'], 
                               help='只清理指定状态的任务')
    cleanup_parser.add_argument('--force', action='store_true', help='强制清理，不询问确认')
    cleanup_parser.add_argument('--keep-files', action='store_true', help='保留下载的文件，只删除任务记录')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 初始化配置
    config = get_config()
    
    # 处理HF认证参数
    if hasattr(args, 'hf_username') and args.hf_username:
        config.set_hf_auth(username=args.hf_username)
    if hasattr(args, 'hf_token') and args.hf_token:
        config.set_hf_auth(token=args.hf_token)
    
    # 保存配置更新
    if (hasattr(args, 'hf_username') and args.hf_username) or (hasattr(args, 'hf_token') and args.hf_token):
        config.save_config()
        print("✅ HF认证信息已保存到配置文件")
    
    # 检查并显示认证状态
    if config.is_hf_auth_available():
        username, token = config.get_hf_auth()
        print(f"🔐 HF认证: 用户名={username or 'N/A'}, Token={'已设置' if token else '未设置'}")
    
    # 设置配置路径
    if hasattr(args, 'metadata_dir') and args.metadata_dir:
        config.set('paths.metadata_dir', args.metadata_dir)
    if hasattr(args, 'downloads_dir') and args.downloads_dir:
        config.set('paths.downloads_dir', args.downloads_dir)  
    if hasattr(args, 'logs_dir') and args.logs_dir:
        config.set('paths.logs_dir', args.logs_dir)
    
    # 设置HF端点
    if hasattr(args, 'base_url') and args.base_url:
        config.set('network.hf_endpoint', args.base_url)
    
    # 设置日志
    setup_logging()
    
    # 初始化管理器
    dataset_manager = DatasetManager()
    download_manager = DownloadManager()
    task_manager = TaskManager()
    system_monitor = SystemMonitor()
    batch_manager = BatchDownloadManager()
    
    try:
        if args.command == 'add-dataset':
            dataset_manager.add_dataset(
                repo_id=args.repo_id,
                description=args.description,
                is_dataset=args.dataset,
                tags=args.tags or []
            )
            print(f"{Colors.GREEN}✓ 数据集 '{args.repo_id}' 添加成功{Colors.NC}")
            
        elif args.command == 'import-hfd':
            # 导入 HFD 任务
            try:
                from hfd_importer import HFDImporter
                
                # 查找 .hfd 目录
                hfd_dir = Path(args.hfd_dir)
                if hfd_dir.name == '.hfd':
                    hfd_metadata_dir = hfd_dir
                else:
                    hfd_metadata_dir = hfd_dir / '.hfd'
                    
                if not hfd_metadata_dir.exists():
                    print(f"{Colors.RED}❌ 错误: 找不到 .hfd 目录: {hfd_metadata_dir}{Colors.NC}")
                    return
                    
                # 创建导入器
                importer = HFDImporter(
                    hfd_dir=str(hfd_metadata_dir),
                    output_dir=args.output_dir,
                    base_url=args.base_url
                )
                
                # 显示摘要
                print(f"{Colors.BLUE}正在分析 HFD 任务...{Colors.NC}")
                importer.print_summary()
                
                if args.dry_run:
                    print(f"\n{Colors.CYAN}🔍 这是试运行模式，未实际导入数据{Colors.NC}")
                    return
                    
                # 确认导入
                print(f"\n{Colors.YELLOW}❓ 是否要将这个 HFD 任务导入到数据库？ (y/N): {Colors.NC}", end='')
                response = input().strip().lower()
                
                if response in ['y', 'yes']:
                    # 执行导入
                    print(f"{Colors.BLUE}正在导入任务...{Colors.NC}")
                    task_id = importer.import_to_system(task_manager)
                    
                    print(f"\n{Colors.GREEN}✅ 导入成功！{Colors.NC}")
                    print(f"{Colors.CYAN}📋 任务ID: {task_id}{Colors.NC}")
                    print(f"{Colors.CYAN}💾 任务文件: {task_manager.tasks_file}{Colors.NC}")
                    print(f"\n{Colors.BLUE}🚀 你现在可以使用以下命令继续下载:{Colors.NC}")
                    print(f"   {Colors.NC}python main.py resume {task_id}{Colors.NC}")
                    print(f"   {Colors.NC}python main.py status {task_id}{Colors.NC}")
                    
                else:
                    print(f"\n{Colors.YELLOW}❌ 导入已取消{Colors.NC}")
                    
            except ImportError:
                print(f"{Colors.RED}❌ 错误: 无法导入 HFDImporter，请检查模块{Colors.NC}")
            except Exception as e:
                print(f"{Colors.RED}❌ 导入失败: {e}{Colors.NC}")
                
        elif args.command == 'download':
            # 检查数据集是否存在，如果不存在则自动添加
            if not dataset_manager.get_dataset(args.repo_id):
                print(f"{Colors.YELLOW}数据集 '{args.repo_id}' 不存在，自动添加...{Colors.NC}")
                dataset_manager.add_dataset(args.repo_id, is_dataset=getattr(args, 'dataset', False))
            
            task_id = task_manager.create_task(
                repo_id=args.repo_id,
                local_dir=args.local_dir,
                revision=args.revision,
                is_dataset=getattr(args, 'dataset', False)
            )
            
            print(f"{Colors.GREEN}✓ 下载任务已创建，任务ID: {task_id}{Colors.NC}")
            print(f"{Colors.YELLOW}开始下载...{Colors.NC}")
            
            # 开始下载
            success = download_manager.start_download(task_id)
            if success:
                # 等待下载完成 - 添加超时和更好的状态检测
                max_iterations = 300  # 最多等待10分钟（300 * 2秒）
                iteration = 0
                
                while iteration < max_iterations:
                    # 重新加载任务数据，确保获取最新状态
                    task_manager.tasks = task_manager._load_tasks()
                    task = task_manager.get_task(task_id)
                    
                    if not task:
                        print(f"{Colors.RED}✗ 任务 {task_id} 不存在{Colors.NC}")
                        break
                        
                    if task['status'] in ['completed', 'failed', 'cancelled']:
                        break
                        
                    print(f"{Colors.BLUE}下载中... 进度: {task.get('progress', '0%')} | 状态: {task['status']}{Colors.NC}")
                    time.sleep(2)
                    iteration += 1
                
                # 最终状态检查
                task_manager.tasks = task_manager._load_tasks()
                final_task = task_manager.get_task(task_id)
                
                if not final_task:
                    print(f"{Colors.RED}✗ 任务丢失{Colors.NC}")
                elif iteration >= max_iterations:
                    print(f"{Colors.YELLOW}⚠ 下载超时，请检查任务状态{Colors.NC}")
                elif final_task['status'] == 'completed':
                    print(f"{Colors.GREEN}✓ 下载完成{Colors.NC}")
                else:
                    print(f"{Colors.RED}✗ 下载失败: {final_task.get('error_message', '未知错误')}{Colors.NC}")
            else:
                print(f"{Colors.RED}✗ 下载启动失败{Colors.NC}")
                
        elif args.command == 'list-tasks':
            tasks = task_manager.list_tasks()
            if not tasks:
                print(f"{Colors.YELLOW}暂无任务{Colors.NC}")
            else:
                print(f"\n{'ID':<8} {'数据集':<30} {'状态':<10} {'工具':<8} {'进度':<10} {'创建时间':<20}")
                print("-" * 90)
                for task in tasks:
                    status_color = {
                        'pending': Colors.YELLOW,
                        'running': Colors.BLUE,
                        'completed': Colors.GREEN,
                        'failed': Colors.RED,
                        'cancelled': Colors.GRAY
                    }.get(task['status'], Colors.NC)
                    
                    print(f"{task['id']:<8} {task['repo_id']:<30} {status_color}{task['status']:<10}{Colors.NC} "
                          f"{task['tool']:<8} {task.get('progress', 'N/A'):<10} {task['created_at'][:16]:<20}")
                    
        elif args.command == 'list-datasets':
            datasets = dataset_manager.list_datasets()
            if not datasets:
                print(f"{Colors.YELLOW}暂无数据集{Colors.NC}")
            else:
                print(f"\n{'仓库ID':<40} {'类型':<8} {'描述':<50}")
                print("-" * 100)
                for ds in datasets:
                    ds_type = "数据集" if ds.get('is_dataset') else "模型"
                    desc = ds.get('description', '')[:47] + '...' if len(ds.get('description', '')) > 50 else ds.get('description', '')
                    print(f"{ds['repo_id']:<40} {ds_type:<8} {desc:<50}")
                    
        elif args.command == 'status':
            task = task_manager.get_task(args.task_id)
            if not task:
                print(f"{Colors.RED}✗ 任务 {args.task_id} 不存在{Colors.NC}")
                return
                
            print(f"\n任务详情:")
            print(f"ID: {task['id']}")
            print(f"数据集: {task['repo_id']}")
            print(f"状态: {task['status']}")
            print(f"工具: {task['tool']}")
            print(f"创建时间: {task['created_at']}")
            if task.get('completed_at'):
                print(f"完成时间: {task['completed_at']}")
            if task.get('error_message'):
                print(f"错误信息: {task['error_message']}")
                
        elif args.command == 'cancel':
            success = task_manager.cancel_task(args.task_id)
            if success:
                print(f"{Colors.GREEN}✓ 任务 {args.task_id} 已取消{Colors.NC}")
            else:
                print(f"{Colors.RED}✗ 无法取消任务 {args.task_id}{Colors.NC}")
                
        elif args.command == 'resume':
            # 获取任务信息
            task = task_manager.get_task(args.task_id)
            if not task:
                print(f"{Colors.RED}✗ 任务 {args.task_id} 不存在{Colors.NC}")
                return
            
            # 检查参数冲突
            if args.skip_moved_files and args.redownload_moved_files:
                print(f"{Colors.RED}✗ --skip-moved-files 和 --redownload-moved-files 不能同时使用{Colors.NC}")
                return
            
            print(f"{Colors.BLUE}准备恢复下载任务:{Colors.NC}")
            print(f"  ID: {args.task_id}")
            print(f"  数据集: {task['repo_id']}")
            print(f"  当前状态: {task['status']}")
            print(f"  当前进度: {task.get('progress', '0%')}")
            
            # 显示移走文件处理策略
            if args.redownload_moved_files:
                print(f"  移走文件策略: {Colors.YELLOW}重新下载已移走的文件{Colors.NC}")
            else:
                print(f"  移走文件策略: {Colors.GREEN}跳过已移走的文件（推荐）{Colors.NC}")
            
            # 检查任务状态
            if task['status'] == 'completed':
                print(f"{Colors.GREEN}任务已完成，无需恢复{Colors.NC}")
                
                # 但是让用户选择是否要重新验证文件
                response = input("是否要重新验证文件完整性？(y/N): ")
                if response.lower() == 'y':
                    print(f"{Colors.YELLOW}正在重新验证文件...{Colors.NC}")
                    # 重置任务状态为pending，让系统重新检查
                    task_manager.update_task_status(args.task_id, 'pending')
                else:
                    return
            elif task['status'] == 'running':
                print(f"{Colors.YELLOW}⚠️ 任务显示为运行中，但可能已中断{Colors.NC}")
                response = input("是否强制重新开始下载？(y/N): ")
                if response.lower() != 'y':
                    print("取消恢复")
                    return
                # 重置任务状态为pending
                task_manager.update_task_status(args.task_id, 'pending')
            else:
                # 对于其他状态（failed, cancelled等），直接重置为pending
                task_manager.update_task_status(args.task_id, 'pending')
            
            print(f"{Colors.YELLOW}正在恢复下载...{Colors.NC}")
            
            # 设置移走文件处理选项
            download_manager.set_moved_files_strategy(
                'redownload' if args.redownload_moved_files else 'skip'
            )
            
            # 开始下载（支持智能断点续传）
            success = download_manager.start_download(args.task_id)
            if success:
                print(f"{Colors.GREEN}✓ 下载恢复成功{Colors.NC}")
                
                # 等待下载完成
                max_iterations = 300  # 最多等待10分钟
                iteration = 0
                
                while iteration < max_iterations:
                    # 重新加载任务数据
                    task_manager.tasks = task_manager._load_tasks()
                    current_task = task_manager.get_task(args.task_id)
                    
                    if not current_task:
                        print(f"{Colors.RED}✗ 任务丢失{Colors.NC}")
                        break
                        
                    if current_task['status'] in ['completed', 'failed', 'cancelled']:
                        break
                        
                    print(f"{Colors.BLUE}下载中... 进度: {current_task.get('progress', '0%')} | 状态: {current_task['status']}{Colors.NC}")
                    time.sleep(2)
                    iteration += 1
                
                # 最终状态检查
                task_manager.tasks = task_manager._load_tasks()
                final_task = task_manager.get_task(args.task_id)
                
                if not final_task:
                    print(f"{Colors.RED}✗ 任务丢失{Colors.NC}")
                elif iteration >= max_iterations:
                    print(f"{Colors.YELLOW}⚠ 下载超时，请检查任务状态{Colors.NC}")
                elif final_task['status'] == 'completed':
                    print(f"{Colors.GREEN}✓ 恢复下载完成{Colors.NC}")
                else:
                    print(f"{Colors.RED}✗ 恢复下载失败: {final_task.get('error_message', '未知错误')}{Colors.NC}")
            else:
                print(f"{Colors.RED}✗ 无法恢复任务 {args.task_id}{Colors.NC}")
                
        elif args.command == 'clean':
            count = task_manager.clean_completed_tasks()
            print(f"{Colors.GREEN}✓ 已清理 {count} 个完成的任务记录{Colors.NC}")
            
        elif args.command == 'fix-progress':
            # 修复已完成任务的进度显示
            tasks = task_manager.list_tasks(status='completed')
            fixed_count = 0
            
            for task in tasks:
                if task.get('progress', '0%') != '100%':
                    task_manager.update_task_progress(task['id'], '100%')
                    fixed_count += 1
                    print(f"{Colors.YELLOW}修复任务 {task['id']} ({task['repo_id']}) 进度: {task.get('progress')} -> 100%{Colors.NC}")
            
            if fixed_count > 0:
                print(f"{Colors.GREEN}✓ 已修复 {fixed_count} 个任务的进度显示{Colors.NC}")
            else:
                print(f"{Colors.YELLOW}没有需要修复的任务{Colors.NC}")
                
        elif args.command == 'check-system':
            # 系统检查
            print(f"{Colors.BLUE}正在检查系统状态...{Colors.NC}")
            check_result = system_monitor.comprehensive_check(args.path, args.size)
            system_status_ok = system_monitor.print_system_status(check_result)
            
            if not system_status_ok:
                print(f"\n{Colors.RED}⚠ 系统检查发现问题，建议解决后再进行下载{Colors.NC}")
                sys.exit(1)
            else:
                print(f"\n{Colors.GREEN}✓ 系统状态正常，可以进行下载{Colors.NC}")
                
        elif args.command == 'verify':
            # 验证文件完整性
            task = task_manager.get_task(args.task_id)
            if not task:
                print(f"{Colors.RED}✗ 任务 {args.task_id} 不存在{Colors.NC}")
                return
            
            try:
                file_tracker = FileTracker(args.task_id)
                
                # 确定下载路径
                if task.get('local_dir'):
                    download_path = Path(task['local_dir'])
                else:
                    download_path = Path('downloads') / task['repo_id']
                
                print(f"{Colors.YELLOW}正在验证任务 {args.task_id} 的文件完整性...{Colors.NC}")
                integrity_results = file_tracker.verify_file_integrity(download_path)
                
                # 统计结果
                total_files = len(integrity_results)
                valid_files = len([r for r in integrity_results.values() if r['status'] == 'valid'])
                missing_files = len([r for r in integrity_results.values() if not r['exists']])
                mismatch_files = len([r for r in integrity_results.values() if r['exists'] and not r['size_match']])
                
                print(f"\n{Colors.BOLD}=== 文件完整性验证结果 ==={Colors.NC}")
                print(f"总文件数: {total_files}")
                print(f"完整文件: {Colors.GREEN}{valid_files}{Colors.NC}")
                print(f"缺失文件: {Colors.RED}{missing_files}{Colors.NC}")
                print(f"大小不匹配: {Colors.YELLOW}{mismatch_files}{Colors.NC}")
                
                # 显示问题文件详情
                problem_files = [(f, r) for f, r in integrity_results.items() if r['status'] != 'valid']
                if problem_files:
                    print(f"\n{Colors.RED}问题文件详情:{Colors.NC}")
                    for filename, result in problem_files[:10]:  # 只显示前10个
                        if not result['exists']:
                            print(f"  ✗ {filename}: 文件缺失")
                        elif not result['size_match']:
                            print(f"  ⚠ {filename}: 大小不匹配 (实际: {result['actual_size']}, 期望: {result['expected_size']})")
                    
                    if len(problem_files) > 10:
                        print(f"  ... 还有 {len(problem_files) - 10} 个问题文件")
                else:
                    print(f"\n{Colors.GREEN}✓ 所有文件验证通过{Colors.NC}")
                    
            except Exception as e:
                print(f"{Colors.RED}✗ 验证失败: {str(e)}{Colors.NC}")
                
        elif args.command == 'task-detail':
            # 查看任务详细信息
            task = task_manager.get_task(args.task_id)
            if not task:
                print(f"{Colors.RED}✗ 任务 {args.task_id} 不存在{Colors.NC}")
                return
            
            try:
                file_tracker = FileTracker(args.task_id)
                summary = file_tracker.get_download_summary()
                failed_files = file_tracker.get_failed_files()
                pending_files = file_tracker.get_pending_files()
                
                print(f"\n{Colors.BOLD}=== 任务详细信息 ==={Colors.NC}")
                print(f"任务ID: {task['id']}")
                print(f"仓库: {task['repo_id']}")
                print(f"状态: {task['status']}")
                print(f"工具: {task['tool']}")
                print(f"创建时间: {task['created_at']}")
                if task.get('completed_at'):
                    print(f"完成时间: {task['completed_at']}")
                if task.get('error_message'):
                    print(f"错误信息: {task['error_message']}")
                
                print(f"\n{Colors.BOLD}=== 文件统计 ==={Colors.NC}")
                print(f"总文件数: {summary['total_files']}")
                print(f"已完成: {summary['completed_files']} ({summary['completion_rate']})")
                print(f"失败: {summary['failed_files']}")
                print(f"待下载: {summary['pending_files']}")
                print(f"下载大小: {summary['downloaded_size_formatted']} / {summary['total_size_formatted']}")
                
                # 显示失败的文件
                if failed_files:
                    print(f"\n{Colors.RED}失败文件:{Colors.NC}")
                    for file_info in failed_files[:5]:
                        print(f"  ✗ {file_info['filename']}: {file_info['error']}")
                    if len(failed_files) > 5:
                        print(f"  ... 还有 {len(failed_files) - 5} 个失败文件")
                
                # 显示待下载的文件
                if pending_files:
                    print(f"\n{Colors.YELLOW}待下载文件:{Colors.NC}")
                    for file_info in pending_files[:5]:
                        size_str = f" ({format_file_size(file_info['size'])})" if file_info['size'] > 0 else ""
                        print(f"  ○ {file_info['filename']}{size_str}")
                    if len(pending_files) > 5:
                        print(f"  ... 还有 {len(pending_files) - 5} 个待下载文件")
                        
            except Exception as e:
                print(f"{Colors.YELLOW}无法获取详细文件信息: {str(e)}{Colors.NC}")
                # 至少显示基本任务信息
                print(f"\n任务详情:")
                print(f"ID: {task['id']}")
                print(f"数据集: {task['repo_id']}")
                print(f"状态: {task['status']}")
                print(f"工具: {task['tool']}")
                print(f"创建时间: {task['created_at']}")
                if task.get('completed_at'):
                    print(f"完成时间: {task['completed_at']}")
                if task.get('error_message'):
                    print(f"错误信息: {task['error_message']}")
            
        elif args.command == 'config':
            # 显示配置信息
            print(f"\n{Colors.BOLD}=== 当前配置信息 ==={Colors.NC}")
            print(f"元数据目录: {config.get_metadata_dir()}")
            print(f"下载目录: {config.get_downloads_dir()}")
            print(f"日志目录: {config.get_logs_dir()}")
            print(f"HF端点: {config.get_hf_endpoint()}")
            
            proxies = config.get_proxies()
            if proxies:
                print(f"代理设置:")
                for key, value in proxies.items():
                    print(f"  {key}: {value}")
            else:
                print(f"代理设置: 未设置")
            
            print(f"\n{Colors.BOLD}=== 环境变量配置 ==={Colors.NC}")
            env_vars = [
                ('METADATA_DIR', config.metadata_dir),
                ('DOWNLOADS_DIR', config.downloads_dir),
                ('LOGS_DIR', config.logs_dir),
                ('HF_ENDPOINT', config.hf_endpoint),
                ('HTTP_PROXY', config.http_proxy),
                ('HTTPS_PROXY', config.https_proxy),
                ('HF_TOKEN', '***已设置***' if os.getenv('HF_TOKEN') else '未设置')
            ]
            
            for var_name, value in env_vars:
                if value:
                    print(f"{var_name}: {value}")
                else:
                    print(f"{var_name}: 未设置")
            
        elif args.command == 'analyze-dataset':
            # 分析数据集大小和结构
            print(f"{Colors.BLUE}正在分析数据集 {args.repo_id}...{Colors.NC}")
            
            # 检查是否启用快速模式
            if args.quick:
                print(f"{Colors.YELLOW}🚀 启用快速模式（采样 {args.sample_size} 个文件，超时 {args.timeout}s）{Colors.NC}")
            elif not args.quick:
                # 自动检测是否需要快速模式的提示
                print(f"{Colors.CYAN}💡 提示：如果分析很慢，可以使用 --quick 参数启用快速模式{Colors.NC}")
            
            analysis = batch_manager.analyze_dataset_size(
                args.repo_id, 
                args.dataset,
                quick_mode=args.quick,
                sample_size=args.sample_size,
                timeout=args.timeout
            )
            
            if 'error' in analysis:
                print(f"{Colors.RED}✗ 分析失败: {analysis['error']}{Colors.NC}")
                return
            
            print(f"\n{Colors.BOLD}=== 数据集分析结果 ==={Colors.NC}")
            print(f"分析模式: {analysis.get('analysis_mode', 'unknown')}")
            print(f"分析时间: {analysis.get('analysis_time', 0):.1f}s")
            print(f"总文件数: {analysis['total_files']}")
            
            if analysis.get('is_estimated'):
                size_label = "预估总大小" if analysis.get('analysis_mode') == 'estimate' else "估算总大小"
                print(f"{size_label}: {analysis['total_size_formatted']} {Colors.YELLOW}（估算值）{Colors.NC}")
                if analysis.get('sample_files'):
                    print(f"采样文件数: {analysis.get('sample_files', 0)}")
                if analysis.get('estimation_note'):
                    print(f"估算说明: {analysis['estimation_note']}")
            else:
                print(f"总大小: {analysis['total_size_formatted']}")
            
            if analysis.get('file_types') and analysis.get('analysis_mode') != 'estimate':
                print(f"\n{Colors.BOLD}=== 文件类型分布 ==={Colors.NC}")
                for ext, info in sorted(analysis['file_types'].items(), key=lambda x: x[1]['size'], reverse=True)[:10]:
                    if not ext or ext == 'no_extension':
                        ext = '<无扩展名>'
                    print(f"{ext:<15} {info['count']:>6} 个文件 {format_file_size(info['size']):>12}")
            
            if analysis.get('largest_files'):
                print(f"\n{Colors.BOLD}=== 最大的10个文件 ==={Colors.NC}")
                for i, file_info in enumerate(analysis['largest_files'][:10], 1):
                    size = format_file_size(file_info.get('size', 0))
                    print(f"{i:>2}. {file_info['filename']:<50} {size:>12}")
            
            # 给出优化建议
            analysis_mode = analysis.get('analysis_mode')
            if analysis_mode == 'estimate':
                print(f"\n{Colors.BOLD}=== 预估分析说明 ==={Colors.NC}")
                print(f"{Colors.CYAN}🔍 由于数据集过大，无法快速获取详细文件列表{Colors.NC}")
                print(f"{Colors.CYAN}📊 以上为基于数据集类型的预估值，实际大小可能差异较大{Colors.NC}")
                print(f"{Colors.CYAN}💡 {analysis.get('recommendation', '建议使用分批下载功能')}{Colors.NC}")
                print(f"\n{Colors.BOLD}=== 建议操作 ==={Colors.NC}")
                print(f"{Colors.YELLOW}🚀 直接进行分批规划: python main.py plan-batch {args.repo_id} --available-space YOUR_SPACE {'--dataset' if args.dataset else ''}{Colors.NC}")
                print(f"{Colors.YELLOW}📖 查看分批下载指南: 参考 BATCH_DOWNLOAD_GUIDE.md{Colors.NC}")
            elif analysis_mode == 'quick':
                print(f"\n{Colors.BOLD}=== 快速分析说明 ==={Colors.NC}")
                print(f"{Colors.CYAN}📋 这是基于采样的快速分析结果{Colors.NC}")
                print(f"{Colors.CYAN}📊 总大小为估算值（基于 {analysis.get('sample_files', 0)} 个文件的平均大小）{Colors.NC}")
                print(f"{Colors.CYAN}💡 如需精确分析，请去掉 --quick 参数重新执行{Colors.NC}")
            elif analysis.get('total_files', 0) > 1000:
                print(f"\n{Colors.BOLD}=== 性能建议 ==={Colors.NC}")
                print(f"{Colors.YELLOW}📈 检测到大型数据集（{analysis['total_files']} 个文件）{Colors.NC}")
                print(f"{Colors.YELLOW}🚀 下次可使用 --quick 参数进行快速分析{Colors.NC}")
                print(f"{Colors.YELLOW}⏱️  命令示例: python main.py analyze-dataset {args.repo_id} --quick {'--dataset' if args.dataset else ''}{Colors.NC}")
                
        elif args.command == 'plan-batch':
            # 规划分批下载策略
            print(f"{Colors.BLUE}正在规划分批下载策略...{Colors.NC}")
            
            plan = batch_manager.plan_batch_download(
                args.repo_id, 
                args.available_space,
                args.dataset,
                args.safety_margin
            )
            
            if 'error' in plan:
                print(f"{Colors.RED}✗ 规划失败: {plan['error']}{Colors.NC}")
                return
            
            # 显示管理策略建议
            strategy = batch_manager.suggest_disk_management_strategy(plan, args.available_space)
            
            if strategy['strategy'] != 'no_management_needed':
                print(f"\n{Colors.BOLD}=== 磁盘管理建议 ==={Colors.NC}")
                
                for suggestion in strategy['suggestions']:
                    if suggestion['type'] == 'warning':
                        print(f"{Colors.RED}⚠ {suggestion['message']}{Colors.NC}")
                    elif suggestion['type'] == 'recommendation':
                        print(f"{Colors.YELLOW}💡 {suggestion['message']}{Colors.NC}")
                    elif suggestion['type'] == 'info':
                        print(f"{Colors.CYAN}ℹ {suggestion['message']}{Colors.NC}")
                
                print(f"\n{Colors.BOLD}=== 磁盘使用时间线 ==={Colors.NC}")
                timeline = strategy['timeline']
                for entry in timeline:
                    print(f"批次 {entry['batch']:>2}: {entry['files_count']:>4} 文件, "
                          f"当前批次 {entry['batch_size_formatted']:>8}, "
                          f"累计 {entry['cumulative_size_formatted']:>8}")
                
                print(f"\n预计峰值磁盘使用: {strategy['estimated_peak_usage']}")
            
            # 保存规划结果供后续使用
            plan_file = config.get_metadata_dir() / f"batch_plan_{args.repo_id.replace('/', '_')}.json"
            from utils import save_json_file
            save_json_file(plan_file, plan)
            print(f"\n{Colors.GREEN}✓ 分批规划已保存到: {plan_file}{Colors.NC}")
                
        elif args.command == 'batch-download':
            # 执行分批下载
            print(f"{Colors.BLUE}开始执行分批下载...{Colors.NC}")
            
            # 首先规划下载策略
            plan = batch_manager.plan_batch_download(
                args.repo_id,
                args.available_space, 
                args.dataset
            )
            
            if 'error' in plan:
                print(f"{Colors.RED}✗ 规划失败: {plan['error']}{Colors.NC}")
                return
            
            # 创建下载任务
            if not dataset_manager.get_dataset(args.repo_id):
                print(f"{Colors.YELLOW}数据集 '{args.repo_id}' 不存在，自动添加...{Colors.NC}")
                dataset_manager.add_dataset(args.repo_id, is_dataset=args.dataset)
            
            task_id = task_manager.create_task(
                repo_id=args.repo_id,
                is_dataset=args.dataset
            )
            
            print(f"{Colors.GREEN}✓ 下载任务已创建，任务ID: {task_id}{Colors.NC}")
            
            # 执行分批下载
            success = batch_manager.execute_batch_download(
                task_id, plan, current_batch=1, auto_proceed=args.auto_proceed
            )
            
            if success:
                print(f"{Colors.GREEN}✓ 分批下载执行完成{Colors.NC}")
            else:
                print(f"{Colors.RED}✗ 分批下载执行失败{Colors.NC}")
                
        elif args.command == 'batch-continue':
            # 继续分批下载
            print(f"{Colors.BLUE}继续分批下载，任务ID: {args.task_id}, 批次: {args.batch_number}{Colors.NC}")
            
            # 获取批次进度
            progress = batch_manager.get_batch_progress(args.task_id)
            if not progress:
                print(f"{Colors.RED}✗ 未找到任务 {args.task_id} 的批次信息{Colors.NC}")
                return
            
            # 加载原有的规划
            task = task_manager.get_task(args.task_id)
            if not task:
                print(f"{Colors.RED}✗ 任务 {args.task_id} 不存在{Colors.NC}")
                return
            
            plan_file = config.get_metadata_dir() / f"batch_plan_{task['repo_id'].replace('/', '_')}.json"
            
            if not plan_file.exists():
                print(f"{Colors.RED}✗ 未找到批次规划文件{Colors.NC}")
                return
            
            from utils import load_json_file
            plan = load_json_file(plan_file)
            
            # 继续执行下载
            success = batch_manager.execute_batch_download(
                args.task_id, plan, current_batch=args.batch_number, auto_proceed=False
            )
            
            if success:
                print(f"{Colors.GREEN}✓ 批次继续执行完成{Colors.NC}")
            else:
                print(f"{Colors.RED}✗ 批次继续执行失败{Colors.NC}")
                
        elif args.command == 'batch-status':
            # 查看分批下载状态
            print(f"{Colors.BLUE}查看分批下载状态，任务ID: {args.task_id}{Colors.NC}")
            
            progress = batch_manager.get_batch_progress(args.task_id)
            if not progress:
                print(f"{Colors.RED}✗ 未找到任务 {args.task_id} 的批次信息{Colors.NC}")
                return
                
            task = task_manager.get_task(args.task_id)
            if not task:
                print(f"{Colors.RED}✗ 任务 {args.task_id} 不存在{Colors.NC}")
                return
            
            print(f"\n{Colors.BOLD}=== 分批下载状态 ==={Colors.NC}")
            print(f"任务ID: {progress['task_id']}")
            print(f"数据集: {task['repo_id']}")
            print(f"当前批次: {progress['current_batch']}/{progress['total_batches']}")
            print(f"当前批次大小: {format_file_size(progress['batch_size'])}")
            print(f"最后更新: {progress['timestamp']}")
            
            completion_rate = (progress['current_batch'] - 1) / progress['total_batches'] * 100
            print(f"总体进度: {completion_rate:.1f}%")
            
            if progress['current_batch'] <= progress['total_batches']:
                remaining_batches = progress['total_batches'] - progress['current_batch'] + 1
                print(f"剩余批次: {remaining_batches}")
                
        elif args.command == 'delete-task':
            handle_delete_task(args)
            
        elif args.command == 'cleanup':
            handle_cleanup(args)
    
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}操作被用户中断{Colors.NC}")
        sys.exit(1)
    except Exception as e:
        print(f"{Colors.RED}✗ 错误: {str(e)}{Colors.NC}")
        sys.exit(1)

if __name__ == '__main__':
    main() 