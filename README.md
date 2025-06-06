# 大模型数据集下载管理工具

一个基于aria2c和wget的简单而强大的数据集下载管理器，专为大语言模型和数据集下载设计。

## ✨ 主要特性

- 🚀 **多下载器支持** - 集成aria2c和wget，自动选择最优下载工具
- 📊 **文件级别跟踪** - 精确跟踪每个文件的下载状态和完整性
- 🔍 **系统异常检测** - 自动检测磁盘空间、权限、网络等问题
- 📁 **元数据分离存储** - 独立的元数据管理，避免与下载文件混合
- 🔄 **断点续传** - 支持下载中断后的恢复
- 🌐 **镜像支持** - 自动使用hf-mirror.com（中国用户）
- 🎯 **文件过滤** - 支持include/exclude模式过滤文件
- 📈 **实时进度监控** - 实时显示下载进度和状态
- 🛡️ **完整性验证** - 自动验证文件大小和完整性
- 🔧 **可配置的存储路径**
- 📦 **分批下载管理** - 智能处理大数据集的分批下载 🆕

## 🏗️ 架构设计

### 📂 目录结构
```
dataset-manage/
├── main.py                 # 主程序入口
├── config.py              # 配置管理
├── utils.py               # 工具函数
├── dataset_manager.py     # 数据集元数据管理
├── task_manager.py        # 任务管理
├── downloader.py          # 下载器核心
├── file_tracker.py        # 文件级别跟踪器 🆕
├── system_monitor.py      # 系统监控器 🆕
├── requirements.txt       # 依赖
├── README.md             # 说明文档
│
├── downloads/            # 📥 下载文件存储目录
│   ├── gpt2/
│   ├── databricks--databricks-dolly-15k/
│   └── ...
│
├── metadata/             # 📋 元数据独立存储目录 🆕
│   ├── datasets.json    # 数据集元数据
│   ├── tasks.json       # 任务元数据
│   └── tasks/           # 详细任务跟踪
│       ├── task_001/
│       │   ├── file_list.json      # 文件列表
│       │   ├── file_status.json    # 文件状态
│       │   └── task_metadata.json  # 任务元数据
│       └── ...
│
└── logs/                 # 📝 日志目录
    └── download.log
```

### 🔧 核心组件

1. **FileTracker** - 文件级别状态跟踪
   - 跟踪每个文件的下载状态（pending/downloading/completed/failed）
   - 记录文件大小、下载时间、错误信息
   - 支持完整性验证

2. **SystemMonitor** - 系统状态监控
   - 磁盘空间检查（警告阈值90%，最小1GB剩余）
   - 写入权限验证
   - 网络连接测试
   - 系统资源监控（CPU、内存）

3. **DownloadManager** - 增强的下载管理
   - 预下载系统检查
   - 文件列表生成和过滤
   - 多工具下载执行
   - 实时进度监控

4. **BatchDownloadManager** - 分批下载管理器 🆕
   - 智能分析数据集大小和结构
   - 根据可用空间自动规划分批策略
   - 支持换盘场景的无缝衔接
   - 批次级进度跟踪和恢复

## 🚀 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 基本用法

#### 1. 系统检查
```bash
# 检查当前目录的系统状态
python main.py check-system

# 检查指定目录，预计下载1GB
python main.py check-system --path /data/downloads --size 1073741824
```

#### 2. 添加数据集
```bash
# 添加模型
python main.py add-dataset gpt2 --description "GPT-2模型"

# 添加数据集
python main.py add-dataset databricks/databricks-dolly-15k --dataset --description "Dolly数据集"
```

#### 3. 下载数据集
```bash
# 基本下载
python main.py download gpt2

# 指定参数下载
python main.py download databricks/databricks-dolly-15k --tool aria2c -x 8 -j 5 --dataset

# 文件过滤下载
python main.py download gpt2 --include "*.json" "*.txt" --exclude "*.bin"
```

#### 4. 任务管理
```bash
# 查看所有任务
python main.py list-tasks

# 查看任务详情
python main.py task-detail task_001

# 查看任务状态
python main.py status task_001

# 取消/恢复任务
python main.py cancel task_001
python main.py resume task_001
```

#### 5. 文件验证
```bash
# 验证下载文件完整性
python main.py verify task_001
```

#### 6. 清理管理
```bash
# 清理完成的任务记录
python main.py clean

# 修复进度显示
python main.py fix-progress
```

## 🛡️ 异常检测与处理

### 系统检查项目
- ✅ **磁盘空间** - 检查可用空间是否足够
- ✅ **写入权限** - 验证目标目录写入权限
- ✅ **网络连接** - 测试HF镜像连接
- ✅ **系统资源** - 监控CPU和内存使用

### 异常处理机制
- 🚨 **磁盘空间不足** - 自动停止下载，保护系统
- 🚨 **权限问题** - 提前检测，避免下载失败
- 🚨 **网络异常** - 智能重试，自动切换策略
- 🚨 **文件损坏** - 自动检测大小不匹配



## 📊 文件级别跟踪

### 文件状态
- `pending` - 等待下载
- `downloading` - 正在下载
- `completed` - 下载完成
- `failed` - 下载失败

### 跟踪信息
```json
{
  "filename": "config.json",
  "url": "https://hf-mirror.com/gpt2/resolve/main/config.json",
  "expected_size": 665,
  "actual_size": 665,
  "status": "completed",
  "attempts": 1,
  "created_at": "2024-01-01 10:00:00",
  "completed_at": "2024-01-01 10:00:05"
}
```

## 🌐 网络配置

## 📁 路径配置

### 默认路径结构
```
dataset-manage/
├── metadata/           # 元数据存储（任务信息、文件状态等）
├── downloads/          # 下载文件存储
└── logs/              # 日志文件
```

### 自定义路径配置

#### 方法1: 命令行参数
```bash
# 指定自定义路径
python main.py --metadata-dir /path/to/metadata --downloads-dir /path/to/downloads download gpt2

# 查看当前配置
python main.py config
```

#### 方法2: 环境变量
```bash
# 设置环境变量
export METADATA_DIR=/custom/metadata/path
export DOWNLOADS_DIR=/custom/downloads/path
export LOGS_DIR=/custom/logs/path

# 运行程序将使用自定义路径
python main.py download gpt2
```

#### 方法3: 在脚本中设置
```python
from config import get_config

config = get_config()
config.set_metadata_dir("/custom/metadata")
config.set_downloads_dir("/custom/downloads")
config.set_logs_dir("/custom/logs")
```

### 路径配置的优先级
1. 命令行参数 `--metadata-dir`、`--downloads-dir`、`--logs-dir`
2. 环境变量 `METADATA_DIR`、`DOWNLOADS_DIR`、`LOGS_DIR`
3. 默认值 `metadata`、`downloads`、`logs`

### 路径配置示例

#### 生产环境配置
```bash
# 设置专用的存储路径
export METADATA_DIR=/data/hf-downloader/metadata
export DOWNLOADS_DIR=/data/hf-downloader/downloads
export LOGS_DIR=/var/log/hf-downloader

# 启动下载
python main.py download large-model
```

#### 开发环境配置
```bash
# 使用临时目录
python main.py --metadata-dir /tmp/metadata --downloads-dir /tmp/downloads download test-model
```

#### 多项目隔离
```bash
# 项目A
export METADATA_DIR=/projects/projectA/metadata
export DOWNLOADS_DIR=/projects/projectA/models
python main.py download modelA

# 项目B
export METADATA_DIR=/projects/projectB/metadata  
export DOWNLOADS_DIR=/projects/projectB/models
python main.py download modelB
```

## 🌐 网络配置

### 镜像支持
工具自动检测中国用户并使用hf-mirror.com：
```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### 代理支持
```bash
export HTTP_PROXY=http://proxy:8080
export HTTPS_PROXY=http://proxy:8080
```

## 📋 完整命令列表

| 命令 | 说明 | 示例 |
|------|------|------|
| `add-dataset` | 添加数据集 | `python main.py add-dataset gpt2` |
| `download` | 下载数据集 | `python main.py download gpt2 --tool aria2c` |
| `list-tasks` | 列出所有任务 | `python main.py list-tasks` |
| `list-datasets` | 列出所有数据集 | `python main.py list-datasets` |
| `status` | 查看任务状态 | `python main.py status task_001` |
| `task-detail` | 查看详细信息 🆕 | `python main.py task-detail task_001` |
| `verify` | 验证文件完整性 🆕 | `python main.py verify task_001` |
| `check-system` | 系统状态检查 🆕 | `python main.py check-system --path /data` |
| `config` | 显示配置信息 🆕 | `python main.py config` |
| `analyze-dataset` | 分析数据集结构 🆕 | `python main.py analyze-dataset repo/dataset --dataset` |
| `plan-batch` | 规划分批下载 🆕 | `python main.py plan-batch repo/dataset --available-space SIZE --dataset` |
| `batch-download` | 执行分批下载 🆕 | `python main.py batch-download repo/dataset --available-space SIZE --dataset` |
| `batch-continue` | 继续分批下载 🆕 | `python main.py batch-continue task_001 2` |
| `batch-status` | 分批下载状态 🆕 | `python main.py batch-status task_001` |
| `cancel` | 取消任务 | `python main.py cancel task_001` |
| `resume` | 恢复任务 | `python main.py resume task_001` |
| `clean` | 清理任务记录 | `python main.py clean` |
| `fix-progress` | 修复进度显示 | `python main.py fix-progress` |

## 🔧 高级配置

### 下载参数
```bash
python main.py download repo_id \
  --tool aria2c \           # 下载工具
  -x 8 \                   # 每个文件的连接数
  -j 5 \                   # 并发下载数
  --include "*.json" \     # 包含模式
  --exclude "*.bin" \      # 排除模式
  --local-dir /data/models # 本地目录
```

### 系统检查参数
```bash
python main.py check-system \
  --path /data/downloads \  # 检查路径
  --size 5368709120        # 预计大小(5GB)
```

## 🆘 故障排除

### 常见问题

1. **磁盘空间不足**
   ```bash
   # 检查磁盘空间
   python main.py check-system --path /data
   # 清理空间或更换目录
   ```

2. **权限问题**
   ```bash
   # 检查并修复权限
   sudo chown -R $USER:$USER /data/downloads
   chmod -R 755 /data/downloads
   ```

3. **网络连接问题**
   ```bash
   # 测试连接
   curl -I https://hf-mirror.com
   # 设置代理
   export HTTP_PROXY=http://proxy:8080
   ```

4. **文件验证失败**
   ```bash
   # 验证具体文件
   python main.py verify task_001
   # 重新下载失败文件
   python main.py resume task_001
   ```

### 日志查看
```bash
# 查看详细日志
tail -f logs/download.log

# 查看任务详情
python main.py task-detail task_001
```

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📋 路径配置

### 默认路径结构
```
dataset-manage/
├── metadata/           # 元数据存储（任务信息、文件状态等）
├── downloads/          # 下载文件存储
└── logs/              # 日志文件
```

### 自定义路径配置

#### 方法1: 命令行参数
```bash
# 指定自定义路径
python main.py --metadata-dir /path/to/metadata --downloads-dir /path/to/downloads download gpt2

# 查看当前配置
python main.py config
```

#### 方法2: 环境变量
```bash
# 设置环境变量
export METADATA_DIR=/custom/metadata/path
export DOWNLOADS_DIR=/custom/downloads/path
export LOGS_DIR=/custom/logs/path

# 运行程序将使用自定义路径
python main.py download gpt2
```

#### 方法3: 在脚本中设置
```python
from config import get_config

config = get_config()
config.set_metadata_dir("/custom/metadata")
config.set_downloads_dir("/custom/downloads")
config.set_logs_dir("/custom/logs")
```

### 路径配置的优先级
1. 命令行参数 `--metadata-dir`、`--downloads-dir`、`--logs-dir`
2. 环境变量 `METADATA_DIR`、`DOWNLOADS_DIR`、`LOGS_DIR`
3. 默认值 `metadata`、`downloads`、`logs`

### 路径配置示例

#### 生产环境配置
```bash
# 设置专用的存储路径
export METADATA_DIR=/data/hf-downloader/metadata
export DOWNLOADS_DIR=/data/hf-downloader/downloads
export LOGS_DIR=/var/log/hf-downloader

# 启动下载
python main.py download large-model
```

#### 开发环境配置
```bash
# 使用临时目录
python main.py --metadata-dir /tmp/metadata --downloads-dir /tmp/downloads download test-model
```

#### 多项目隔离
```bash
# 项目A
export METADATA_DIR=/projects/projectA/metadata
export DOWNLOADS_DIR=/projects/projectA/models
python main.py download modelA

# 项目B
export METADATA_DIR=/projects/projectB/metadata  
export DOWNLOADS_DIR=/projects/projectB/models
python main.py download modelB
```

## 🌐 网络配置

### 镜像支持
工具自动检测中国用户并使用hf-mirror.com：
```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### 代理支持
```bash
export HTTP_PROXY=http://proxy:8080
export HTTPS_PROXY=http://proxy:8080
```

## 📋 完整命令列表

| 命令 | 说明 | 示例 |
|------|------|------|
| `add-dataset` | 添加数据集 | `python main.py add-dataset gpt2` |
| `download` | 下载数据集 | `python main.py download gpt2 --tool aria2c` |
| `list-tasks` | 列出所有任务 | `python main.py list-tasks` |
| `list-datasets` | 列出所有数据集 | `python main.py list-datasets` |
| `status` | 查看任务状态 | `python main.py status task_001` |
| `task-detail` | 查看详细信息 🆕 | `python main.py task-detail task_001` |
| `verify` | 验证文件完整性 🆕 | `python main.py verify task_001` |
| `check-system` | 系统状态检查 🆕 | `python main.py check-system --path /data` |
| `config` | 显示配置信息 🆕 | `python main.py config` |
| `analyze-dataset` | 分析数据集结构 🆕 | `python main.py analyze-dataset repo/dataset --dataset` |
| `plan-batch` | 规划分批下载 🆕 | `python main.py plan-batch repo/dataset --available-space SIZE --dataset` |
| `batch-download` | 执行分批下载 🆕 | `python main.py batch-download repo/dataset --available-space SIZE --dataset` |
| `batch-continue` | 继续分批下载 🆕 | `python main.py batch-continue task_001 2` |
| `batch-status` | 分批下载状态 🆕 | `python main.py batch-status task_001` |
| `cancel` | 取消任务 | `python main.py cancel task_001` |
| `resume` | 恢复任务 | `python main.py resume task_001` |
| `clean` | 清理任务记录 | `python main.py clean` |
| `fix-progress` | 修复进度显示 | `python main.py fix-progress` |

## 🔧 高级配置

### 下载参数
```bash
python main.py download repo_id \
  --tool aria2c \           # 下载工具
  -x 8 \                   # 每个文件的连接数
  -j 5 \                   # 并发下载数
  --include "*.json" \     # 包含模式
  --exclude "*.bin" \      # 排除模式
  --local-dir /data/models # 本地目录
```

### 系统检查参数
```bash
python main.py check-system \
  --path /data/downloads \  # 检查路径
  --size 5368709120        # 预计大小(5GB)
```

## 🆘 故障排除

### 常见问题

1. **网络连接问题**
   ```bash
   python main.py check-system  # 检查网络状态
   ```

2. **磁盘空间不足**
   ```bash
   python main.py check-system --size 1000000000  # 检查指定大小的可用空间
   ```

3. **下载进度卡住**
   ```bash
   python main.py cancel <task_id>    # 取消任务
   python main.py resume <task_id>    # 重新开始
   ```

4. **文件完整性问题**
   ```bash
   python main.py verify <task_id>    # 验证文件完整性
   ```
# 分析30TB数据集
python main.py analyze-dataset large-model/30tb-dataset --dataset

# 规划分批策略（10TB可用空间）
python main.py plan-batch large-model/30tb-dataset --available-space 10995116277760 --dataset

# 开始第一批次
python main.py batch-download large-model/30tb-dataset --available-space 10995116277760 --dataset

# 换盘后继续第二批次
python main.py batch-continue task_abc123 2

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📦 分批下载管理 🆕

### 🎯 解决超大数据集下载问题

**适用场景**: 30TB数据集 vs 10TB存储空间等存储限制场景

### 📋 分批下载工作流程

#### 1. 分析数据集结构
```bash
# 分析数据集大小和文件分布
python main.py analyze-dataset large-model/30tb-dataset --dataset
```

#### 2. 规划分批策略
```bash
# 规划分批下载 (10TB可用空间)
python main.py plan-batch large-model/30tb-dataset \
  --available-space 10995116277760 \
  --dataset \
  --safety-margin 0.9
```

#### 3. 执行分批下载
```bash
# 开始第一批次下载
python main.py batch-download large-model/30tb-dataset \
  --available-space 10995116277760 \
  --dataset \
  --tool aria2c
```

#### 4. 换盘继续下载
```bash
# 第一批次完成后，换盘继续第二批次
python main.py batch-continue task_abc123 2
```

#### 5. 查看分批状态
```bash
# 查看分批下载进度
python main.py batch-status task_abc123
```

### 🛡️ 分批下载安全特性

- **智能空间管理**: 自动预留安全余量，防止磁盘满
- **元数据分离**: 下载状态与文件分离，支持换盘场景
- **断点续传**: 支持从任意批次继续下载
- **完整性验证**: 每批次完成后自动验证
- **超大文件处理**: 单独处理超过存储限制的文件

### 📖 详细使用指南
查看 [`BATCH_DOWNLOAD_GUIDE.md`](BATCH_DOWNLOAD_GUIDE.md) 获取完整的分批下载使用指南。