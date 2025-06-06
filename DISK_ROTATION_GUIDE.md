# 磁盘换盘下载指南

## 概述

当下载大型数据集（如30TB）而存储空间有限（如10TB）时，需要使用磁盘换盘策略。本工具支持智能断点续传，可以正确处理已移走文件的情况。

## 典型使用场景

### 场景1：分批下载 + 磁盘换盘
- 下载30TB数据集，只有10TB可用存储
- 每次下载约8-9TB，移走后继续下载剩余部分

### 场景2：大文件优先下载
- 先下载大文件，移走后再下载小文件
- 避免碎片化文件占用过多磁盘空间

## 操作流程

### 1. 开始下载
```bash
# 普通下载
python main.py download UCSC-VLAA/Recap-DataComp-1B --dataset

# 或使用分批下载（推荐大数据集）
python main.py analyze-dataset UCSC-VLAA/Recap-DataComp-1B --dataset --quick
python main.py plan-batch UCSC-VLAA/Recap-DataComp-1B --available-space 8000000000000 --dataset
python main.py batch-download UCSC-VLAA/Recap-DataComp-1B --available-space 8000000000000 --dataset
```

### 2. 监控下载进度
```bash
# 查看下载进度
python main.py list-tasks

# 查看详细信息
python main.py task-detail task_xxx

# 查看系统状态
python main.py check-system --size 1000000000000
```

### 3. 磁盘空间不足时的操作

#### 3.1 暂停下载
```bash
# 中断当前下载（Ctrl+C）
# 或取消任务
python main.py cancel task_xxx
```

#### 3.2 移走已下载文件
```bash
# 查看已下载的文件
ls -la downloads/UCSC-VLAA/Recap-DataComp-1B/

# 移走大文件到外部存储
mkdir -p /external_storage/batch1/
mv downloads/UCSC-VLAA/Recap-DataComp-1B/*.bin /external_storage/batch1/
mv downloads/UCSC-VLAA/Recap-DataComp-1B/*.safetensors /external_storage/batch1/

# 或者移走整个目录并重新创建
mv downloads/UCSC-VLAA/Recap-DataComp-1B /external_storage/batch1/
mkdir -p downloads/UCSC-VLAA/Recap-DataComp-1B
```

#### 3.3 恢复下载（推荐方式）
```bash
# 默认跳过已移走的文件（推荐）
python main.py resume task_xxx

# 或明确指定跳过策略
python main.py resume task_xxx --skip-moved-files
```

#### 3.4 重新下载已移走文件（不推荐）
```bash
# 如果确实需要重新下载已移走的文件
python main.py resume task_xxx --redownload-moved-files
```

## 智能断点续传说明

### 文件状态检测
工具会自动检测以下情况：
1. **文件存在且完整**：跳过下载
2. **文件存在但不完整**：重新下载
3. **文件不存在但元数据显示已完成**：
   - 默认：跳过（认为已移走）
   - `--redownload-moved-files`：重新下载

### 元数据保护
- 元数据存储在独立目录（`metadata/`），不会因文件移走而丢失
- 记录每个文件的下载状态、大小、完成时间等信息
- 支持跨会话断点续传

## 最佳实践

### 1. 预规划存储策略
```bash
# 分析数据集大小
python main.py analyze-dataset DATASET_NAME --dataset --quick

# 规划分批策略
python main.py plan-batch DATASET_NAME --available-space YOUR_SPACE --dataset
```

### 2. 监控和自动化
```bash
# 创建监控脚本
#!/bin/bash
while true; do
    # 检查磁盘空间
    available=$(df downloads/ | tail -1 | awk '{print $4}')
    if [ $available -lt 1000000 ]; then
        echo "磁盘空间不足，请处理..."
        python main.py list-tasks
        break
    fi
    
    # 检查下载状态
    python main.py list-tasks | grep running
    sleep 60
done
```

### 3. 文件组织策略
```bash
# 按文件类型分批移走
find downloads/ -name "*.bin" -size +1G -exec mv {} /external_storage/models/ \;
find downloads/ -name "*.jsonl" -exec mv {} /external_storage/data/ \;
find downloads/ -name "*.txt" -exec mv {} /external_storage/configs/ \;
```

## 错误排查

### 问题1：恢复下载时重新下载已移走文件
**原因**：使用了 `--redownload-moved-files` 参数
**解决**：使用默认策略或 `--skip-moved-files` 参数

### 问题2：元数据丢失
**原因**：元数据目录被误删
**解决**：重新开始下载，或从备份恢复元数据

### 问题3：任务状态异常
```bash
# 检查任务详情
python main.py task-detail task_xxx

# 如果状态卡住，可以手动重置
python main.py cancel task_xxx
python main.py resume task_xxx
```

## 高级用法

### 自定义路径配置
```bash
# 分离元数据和下载目录
export METADATA_DIR="/fast_ssd/metadata"
export DOWNLOADS_DIR="/large_hdd/downloads"
export LOGS_DIR="/fast_ssd/logs"

python main.py download DATASET_NAME --dataset
```

### 批处理脚本示例
```bash
#!/bin/bash
# auto_download_with_rotation.sh

DATASET="UCSC-VLAA/Recap-DataComp-1B"
AVAILABLE_SPACE="8000000000000"  # 8TB
TASK_ID=""

# 开始下载
echo "开始下载数据集..."
TASK_ID=$(python main.py download $DATASET --dataset | grep "任务ID:" | cut -d: -f2 | tr -d ' ')

while true; do
    # 检查任务状态
    STATUS=$(python main.py list-tasks | grep $TASK_ID | awk '{print $3}')
    
    if [ "$STATUS" = "completed" ]; then
        echo "下载完成！"
        break
    elif [ "$STATUS" = "failed" ]; then
        echo "下载失败，尝试恢复..."
        python main.py resume $TASK_ID --skip-moved-files
    fi
    
    # 检查磁盘空间
    available=$(df downloads/ | tail -1 | awk '{print $4}')
    if [ $available -lt 1000000 ]; then
        echo "磁盘空间不足，请移走文件后按回车继续..."
        read
        python main.py resume $TASK_ID --skip-moved-files
    fi
    
    sleep 30
done
```

## 总结

通过智能断点续传和磁盘换盘策略，可以高效下载任意大小的数据集，而不受单个存储设备容量限制。关键是理解文件状态管理和选择合适的恢复策略。 