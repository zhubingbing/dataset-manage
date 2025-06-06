# Hugging Face 认证使用指南

本工具现在支持 Hugging Face 认证，可以下载需要登录的私有仓库和受限模型（如 Meta 的 Llama 系列）。

## 🔐 获取 HF Token

1. 访问 [Hugging Face Settings](https://huggingface.co/settings/tokens)
2. 点击 "New token" 创建新的访问令牌
3. 选择权限：
   - **Read**: 用于下载私有模型/数据集
   - **Write**: 用于上传和修改（一般不需要）
4. 复制生成的 token（格式：`hf_xxxxxxxxxxxxxxxxxxxx`）

## 🚀 使用方法

### 方法1: 命令行参数（推荐）

```bash
# 下载需要认证的模型
python main.py download meta-llama/Llama-2-7b \
    --hf-username myuser \
    --hf-token hf_xxxxxxxxxxxxxxxxxxxx

# 下载私有数据集
python main.py download private-org/private-dataset \
    --dataset \
    --hf-username myuser \
    --hf-token hf_xxxxxxxxxxxxxxxxxxxx

# 导入HFD任务时设置认证
python main.py --hf-token hf_xxxxxxxxxxxxxxxxxxxx \
    import-hfd /path/to/llama-dir /path/to/output
```

### 方法2: 环境变量

```bash
# 设置环境变量
export HF_USERNAME=myuser
export HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx

# 然后正常使用工具
python main.py download meta-llama/Llama-2-7b
```

### 方法3: 配置文件（持久化）

```bash
# 首次设置认证信息
python main.py --hf-username myuser --hf-token hf_xxxxxxxxxxxxxxxxxxxx download gpt2

# 认证信息会保存到config.json，后续使用无需再次输入
python main.py download meta-llama/Llama-2-7b
```

## 🎯 支持的仓库类型

### 1. 受限模型（Gated Models）
- Meta Llama 系列: `meta-llama/Llama-2-7b`, `meta-llama/Llama-2-13b` 等
- 其他需要同意许可的模型

### 2. 私有仓库
- 组织内部的私有模型和数据集
- 个人私有仓库

### 3. 普通公开仓库
- 即使有认证信息，也可以正常下载公开仓库
- 认证信息不会影响公开内容的访问

## ⚡ 功能特性

### 🔒 安全认证
- ✅ 支持 Bearer Token 认证
- ✅ 自动处理认证头部
- ✅ 多种配置方式（环境变量优先）

### 🚀 下载支持
- ✅ aria2c 高速下载（自动添加认证头）
- ✅ wget 备用下载（自动添加认证头）
- ✅ 断点续传和重试机制

### 📊 状态反馈
- ✅ 自动检测认证状态
- ✅ 清晰的错误提示
- ✅ 401/403 错误友好提示

## 🔧 故障排除

### 401 认证失败
```
❌ 认证失败: 该仓库需要有效的Hugging Face token
💡 请使用 --hf-token 参数提供访问令牌
```

**解决方案：**
1. 检查 token 是否正确
2. 确认 token 权限（需要 Read 权限）
3. 检查 token 是否过期

### 403 访问被拒绝
```
❌ 访问被拒绝: 您可能没有访问该仓库的权限
```

**解决方案：**
1. 对于受限模型：先在 HuggingFace 网站申请访问权限
2. 对于私有仓库：确认您有访问权限
3. 等待申请审批通过

### 网络连接问题
```
⚠️ API请求超时
```

**解决方案：**
1. 检查网络连接
2. 尝试使用镜像站点：`--base-url https://hf-mirror.com`
3. 配置代理（如果需要）

## 📝 配置文件示例

生成的 `config.json` 示例：
```json
{
  "huggingface": {
    "username": "myuser",
    "token": "hf_xxxxxxxxxxxxxxxxxxxx"
  },
  "network": {
    "hf_endpoint": "https://hf-mirror.com"
  },
  "download": {
    "tool": "aria2c",
    "max_connections": 16
  }
}
```

## 🌟 完整示例

```bash
# 1. 设置认证并下载 Llama-2-7b
python main.py download meta-llama/Llama-2-7b \
    --hf-username myuser \
    --hf-token hf_xxxxxxxxxxxxxxxxxxxx \
    --tool aria2c \
    --threads 8

# 2. 查看下载状态
python main.py list-tasks

# 3. 恢复中断的下载（认证信息已保存）
python main.py resume task_12345

# 4. 下载其他需要认证的内容（无需重新输入认证）
python main.py download meta-llama/Llama-2-13b
```

## 🔥 对比 hfd 工具

我们的工具完全兼容 hfd 的认证方式：

**hfd 命令：**
```bash
hfd meta-llama/Llama-2-7b --hf_username myuser --hf_token mytoken -x 4
```

**我们的工具：**
```bash
python main.py download meta-llama/Llama-2-7b --hf-username myuser --hf-token mytoken --threads 4
```

**优势：**
- ✅ 持久化认证配置
- ✅ 任务管理和断点续传
- ✅ 实时进度监控
- ✅ 批量下载支持
- ✅ 智能文件验证

---

> 💡 **提示**: 认证信息会安全地保存在本地配置文件中，无需每次重新输入。 