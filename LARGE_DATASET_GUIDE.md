# 超大数据集下载指南

对于像 `HuggingFaceFW/fineweb` 这样的超大型数据集，本工具提供了专门的处理策略。

## 🚨 常见问题

### 递归深度超限错误
```
获取文件列表失败: maximum recursion depth exceeded
```

**原因：** 数据集包含数十万甚至数百万个文件，超出了 Python 的处理能力。

## 🔧 解决方案

### 1. 自动采样模式（推荐用于测试）

当遇到超大数据集时，工具会自动切换到采样模式：

```bash
# 恢复下载时会自动处理超大数据集
python main.py resume task_1749202470 --skip-moved-files
```

采样模式特点：
- ✅ 获取前5000个文件作为样本
- ✅ 用于测试下载功能
- ✅ 避免内存和递归问题
- ⚠️ **不是完整数据集**

### 2. 批量下载（推荐用于生产）

对于真正需要下载完整数据集的情况，使用批量下载：

```bash
# 1. 分析数据集（快速模式）
python main.py analyze-dataset HuggingFaceFW/fineweb --dataset --quick

# 2. 规划批量下载（假设有1TB可用空间）
python main.py plan-batch HuggingFaceFW/fineweb --available-space 1099511627776 --dataset

# 3. 执行批量下载
python main.py batch-download HuggingFaceFW/fineweb --available-space 1099511627776 --dataset
```

### 3. 手动重置任务

如果任务状态异常，可以删除后重新开始：

```bash
# 删除有问题的任务
python main.py delete-task task_1749202470 --force

# 重新创建任务并使用批量下载
python main.py batch-download HuggingFaceFW/fineweb --available-space YOUR_SPACE --dataset
```

## 📊 超大数据集列表

以下数据集需要特殊处理：

| 数据集 | 大小 | 文件数 | 建议方法 |
|--------|------|--------|----------|
| HuggingFaceFW/fineweb | ~15TB | ~440万 | 批量下载 |
| allenai/c4 | ~750GB | ~350万 | 批量下载 |
| mc4 | ~10TB | ~1000万+ | 批量下载 |
| LAION-5B | ~240TB | ~584万 | 分批+多盘 |

## ⚙️ 技术参数调整

### 增加系统限制
```bash
# 临时增加内存限制（如果需要）
ulimit -v 8388608  # 8GB虚拟内存

# 增加文件描述符限制
ulimit -n 65536
```

### 配置文件优化
```json
{
  "download": {
    "max_concurrent_downloads": 4,
    "split": 8,
    "timeout": 300
  },
  "system": {
    "max_concurrent_downloads": 2,
    "disk_space_threshold": 10240
  }
}
```

## 🎯 针对 fineweb 的具体建议

### 基本信息
- **数据集名称**: HuggingFaceFW/fineweb
- **类型**: 网页文本数据集
- **大小**: 约15TB
- **文件数**: 约440万个 parquet 文件
- **特点**: 高度分片的大型文本数据集

### 推荐下载策略

#### 方案1: 部分下载（开发测试）
```bash
# 下载前1000个文件用于测试
python main.py download HuggingFaceFW/fineweb --dataset
# 系统会自动切换到采样模式
```

#### 方案2: 完整批量下载（生产环境）
```bash
# 步骤1: 快速分析
python main.py analyze-dataset HuggingFaceFW/fineweb --dataset --quick --sample-size 200

# 步骤2: 准备足够的存储空间（至少20TB）
# 步骤3: 执行批量下载
python main.py batch-download HuggingFaceFW/fineweb \
    --available-space 21474836480000 \
    --dataset \
    --auto-proceed

# 步骤4: 监控下载进度
python main.py batch-status <task_id>
```

#### 方案3: 分类下载（按需）
```bash
# 查看数据集结构，按子集下载
# 例如只下载特定的数据分片
python main.py download HuggingFaceFW/fineweb \
    --dataset \
    --include "CC-MAIN-2024*" \
    --local-dir ./fineweb_2024
```

## 🔍 故障排除

### 内存不足
```bash
# 症状：进程被系统杀死
# 解决：使用批量下载 + 较小的批次
python main.py plan-batch HuggingFaceFW/fineweb --available-space 500000000000 --safety-margin 0.7
```

### 网络超时
```bash
# 症状：频繁的网络超时
# 解决：调整下载参数
python main.py batch-download HuggingFaceFW/fineweb \
    --available-space YOUR_SPACE \
    --dataset \
    --tool aria2c  # 使用aria2c的重试机制
```

### 磁盘空间管理
```bash
# 查看磁盘使用
df -h

# 设置较小的批次大小
python main.py plan-batch HuggingFaceFW/fineweb \
    --available-space 1000000000000 \  # 1TB批次
    --safety-margin 0.8
```

## 💡 最佳实践

1. **先小规模测试**: 使用采样模式下载少量文件验证流程
2. **充足的存储**: 准备至少1.5倍数据集大小的存储空间
3. **网络稳定**: 确保网络连接稳定，或使用重试机制
4. **分批进行**: 对于TB级数据集，分多个批次下载
5. **监控资源**: 定期检查磁盘空间和内存使用
6. **备份重要配置**: 保存批量下载的规划文件

## 📞 技术支持

如果遇到其他问题：

1. 查看 `logs/` 目录中的详细日志
2. 使用 `python main.py check-system` 检查系统状态
3. 尝试重置任务: `python main.py delete-task <task_id> --force`
4. 使用批量下载替代普通下载

---

> ⚠️ **重要提醒**: 超大数据集下载需要大量时间和存储空间，请确保有足够的资源并做好长期下载的准备。 