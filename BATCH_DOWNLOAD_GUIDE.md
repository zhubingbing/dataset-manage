# 🚀 分批下载功能完全指南

## 🎯 解决的问题

对于您提到的场景（30TB数据集 vs 10TB存储空间），我们的分批下载管理器完全解决了这个问题：

- ✅ **智能分批规划** - 根据可用空间自动分批
- ✅ **换盘无缝衔接** - 支持中断后继续下载
- ✅ **独立元数据管理** - 下载状态与实际文件分离存储
- ✅ **超大文件处理** - 单独处理超过存储限制的文件
- ✅ **空间安全保护** - 自动预留安全余量
- ✅ **进度完整跟踪** - 批次级别和文件级别双重跟踪

## 📋 完整工作流程

### 步骤1: 分析数据集
```bash
# 分析30TB数据集的结构
python main.py analyze-dataset large-model/30tb-dataset --dataset
```

**输出示例:**
```
=== 数据集分析结果 ===
总文件数: 15,420
总大小: 30.2 TB

=== 文件类型分布 ===
.safetensors      8,245 个文件     28.5 TB
.json               156 个文件      1.2 GB
.txt                 89 个文件      125 MB
```

### 步骤2: 规划分批策略
```bash
# 规划分批下载 (10TB可用空间)
python main.py plan-batch large-model/30tb-dataset \
  --available-space 10995116277760 \
  --dataset \
  --safety-margin 0.9
```

**输出示例:**
```
=== 分批下载规划 ===
数据集总大小: 30.2 TB
可用空间: 10.0 TB
安全可用空间: 9.0 TB (预留10%安全余量)
需要分 4 批次下载
  批次 1: 1,245 个文件, 8.9 TB
  批次 2: 1,356 个文件, 8.8 TB
  批次 3: 1,289 个文件, 8.7 TB
  批次 4: 11,530 个文件, 3.8 TB

=== 磁盘管理建议 ===
💡 建议每完成2-3个批次后进行一次文件备份和清理
ℹ 检测到 12 个超大文件需要单独处理

=== 磁盘使用时间线 ===
批次  1: 1245 文件, 当前批次    8.9 TB, 累计    8.9 TB
批次  2: 1356 文件, 当前批次    8.8 TB, 累计   17.7 TB
批次  3: 1289 文件, 当前批次    8.7 TB, 累计   26.4 TB
批次  4:11530 文件, 当前批次    3.8 TB, 累计   30.2 TB

预计峰值磁盘使用: 8.9 TB
```

### 步骤3: 执行第一批次
```bash
# 开始分批下载
python main.py batch-download large-model/30tb-dataset \
  --available-space 10995116277760 \
  --dataset \
  --tool aria2c
```

**系统会自动:**
1. 创建下载任务
2. 检查系统状态（磁盘、网络、权限）
3. 下载第一批次（1,245个文件，8.9TB）
4. 验证文件完整性
5. 显示下一步操作指南

### 步骤4: 换盘和继续下载
```bash
# 第一批次完成后的操作
# 1. 备份/移动第一批次文件到外部存储
mv downloads/large-model/30tb-dataset /external/storage/batch1/

# 2. 清理空间准备下一批次
rm -rf downloads/large-model/30tb-dataset/*

# 3. 继续下载第二批次
python main.py batch-continue task_abc123 2
```

### 步骤5: 查看进度和状态
```bash
# 查看分批下载状态
python main.py batch-status task_abc123

# 查看任务详情
python main.py task-detail task_abc123

# 查看系统状态
python main.py check-system
```

## 🛡️ 安全特性

### 1. 磁盘空间保护
- **安全余量**: 默认预留10%空间，可调整
- **实时监控**: 每个批次下载前检查可用空间
- **自动停止**: 空间不足时自动停止下载

### 2. 元数据独立存储
```
metadata/
├── tasks/
│   └── task_abc123/
│       ├── batch_progress.json      # 批次进度
│       ├── file_list.json          # 完整文件列表
│       ├── file_status.json        # 文件下载状态
│       └── task_metadata.json      # 任务元数据
└── batch_plan_large-model_30tb-dataset.json  # 分批规划
```

### 3. 断点续传支持
- **文件级跟踪**: 每个文件的下载状态独立跟踪
- **批次级恢复**: 支持从任意批次开始继续
- **状态持久化**: 所有状态信息持久保存

## 🎛️ 高级配置

### 自定义存储路径
```bash
# 将元数据存储到SSD，下载文件存储到机械硬盘
python main.py \
  --metadata-dir /fast/ssd/metadata \
  --downloads-dir /large/hdd/downloads \
  batch-download large-model/30tb-dataset \
  --available-space 10995116277760 \
  --dataset
```

### 自动化批次处理
```bash
# 自动执行所有批次（需要充足空间）
python main.py batch-download large-model/30tb-dataset \
  --available-space 10995116277760 \
  --dataset \
  --auto-proceed
```

### 调整安全策略
```bash
# 更严格的安全余量（预留20%）
python main.py plan-batch large-model/30tb-dataset \
  --available-space 10995116277760 \
  --dataset \
  --safety-margin 0.8
```

## 💡 最佳实践

### 1. 大数据集下载策略
```bash
# 对于超大数据集，建议的完整流程：

# Step 1: 分析和规划
python main.py analyze-dataset your-model/huge-dataset --dataset
python main.py plan-batch your-model/huge-dataset --available-space YOUR_SPACE --dataset

# Step 2: 准备专用目录
mkdir -p /data/batch_downloads
mkdir -p /backup/completed_batches

# Step 3: 执行分批下载
python main.py --downloads-dir /data/batch_downloads \
  batch-download your-model/huge-dataset \
  --available-space YOUR_SPACE --dataset

# Step 4: 循环处理每个批次
for batch in {2..N}; do
  # 备份完成的批次
  mv /data/batch_downloads/* /backup/completed_batches/batch_$((batch-1))/
  
  # 继续下一批次
  python main.py --downloads-dir /data/batch_downloads \
    batch-continue task_id $batch
  
  # 验证完整性
  python main.py verify task_id
done
```

### 2. 换盘场景处理
```bash
#!/bin/bash
# 自动化换盘脚本示例

TASK_ID="your_task_id"
CURRENT_BATCH=1
TOTAL_BATCHES=4

for ((batch=$CURRENT_BATCH; batch<=TOTAL_BATCHES; batch++)); do
  echo "处理批次 $batch/$TOTAL_BATCHES"
  
  # 下载当前批次
  python main.py batch-continue $TASK_ID $batch
  
  if [ $? -eq 0 ]; then
    echo "批次 $batch 下载完成"
    
    # 备份到外部存储
    echo "正在备份批次 $batch..."
    rsync -av downloads/ /external/storage/batch_$batch/
    
    if [ $batch -lt $TOTAL_BATCHES ]; then
      echo "请更换存储设备后按回车继续..."
      read -p "准备好继续下一批次了吗? (y/n): " confirm
      
      if [[ $confirm == [yY] ]]; then
        # 清理当前批次文件为下一批次腾出空间
        rm -rf downloads/*
        echo "已清理空间，准备下载批次 $((batch+1))"
      else
        echo "用户取消，退出"
        break
      fi
    fi
  else
    echo "批次 $batch 下载失败，退出"
    break
  fi
done

echo "分批下载完成！"
```

## 🔧 故障排除

### 常见问题和解决方案

1. **批次中断后如何恢复？**
   ```bash
   # 查看批次状态
   python main.py batch-status task_id
   
   # 从指定批次继续
   python main.py batch-continue task_id 3
   ```

2. **修改批次规划怎么办？**
   ```bash
   # 重新规划（会覆盖原有规划）
   python main.py plan-batch dataset-id --available-space NEW_SIZE --dataset
   ```

3. **验证已下载文件的完整性？**
   ```bash
   # 验证特定任务的文件
   python main.py verify task_id
   ```

4. **清理中间状态？**
   ```bash
   # 清理完成的任务记录
   python main.py clean
   
   # 手动清理特定任务的元数据
   rm -rf metadata/tasks/task_id
   ```

## 📊 性能建议

### 存储优化
- **SSD用于元数据**: 将`--metadata-dir`指向SSD提升响应速度
- **机械硬盘用于下载**: 将`--downloads-dir`指向大容量机械硬盘
- **网络存储**: 支持NFS、CIFS等网络存储

### 网络优化
- **并发下载**: 调整`-j`参数控制并发数
- **连接数**: 调整`-x`参数控制每文件连接数
- **代理设置**: 支持HTTP/HTTPS代理

### 监控和日志
- **实时监控**: `python main.py check-system`
- **详细日志**: 查看`logs/dataset_manager.log`
- **进度跟踪**: `python main.py batch-status task_id`

---

🎉 **恭喜！** 您现在拥有了一个强大的分批下载系统，可以轻松处理任意大小的数据集下载，完美解决了存储空间限制的问题！ 