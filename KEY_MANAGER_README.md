# SerpAPI 密钥管理功能

## 功能概述

本系统提供了完整的 SerpAPI 密钥管理功能，支持：

- 🔑 **密钥录入**：通过Web界面添加新的SerpAPI密钥
- ✅ **密钥验证**：实时验证密钥的有效性和配额状态
- 📅 **创建时间管理**：记录密钥的创建日期，用于智能选择
- 🗂️ **密钥管理**：查看、删除、重新验证密钥
- 🔄 **自动集成**：验证通过后自动集成到云构建流程

## 使用方法

### 1. 启动密钥管理服务

```bash
# 在项目根目录执行
./start_key_manager.sh
```

服务将在 `http://localhost:5000` 启动

### 2. 访问密钥管理页面

打开浏览器访问：`http://localhost:5000/static/key_manager.html`

### 3. 添加新密钥

1. 填写密钥名称（例如：Key-1, Production-Key）
2. 输入 SerpAPI 密钥
3. 选择密钥创建日期
4. 添加描述（可选）
5. 点击"添加并验证密钥"

### 4. 验证过程

系统会自动：
- 验证密钥格式
- 调用 SerpAPI 测试接口
- 获取配额信息
- 保存密钥信息

### 5. 管理密钥

- 查看所有密钥状态
- 重新验证密钥
- 删除无效密钥

## 技术实现

### 文件结构

```
├── static/
│   └── key_manager.html          # 密钥管理页面
├── data/
│   └── serpapi_keys.json        # 密钥存储文件
├── api_key_registration_dates.json  # 注册日期配置
├── key_manager_api.py           # API服务
├── enhanced_key_manager.py      # 增强版密钥管理器
└── start_key_manager.sh         # 启动脚本
```

### API 端点

- `POST /api/validate-key` - 验证密钥
- `POST /api/add-key` - 添加密钥
- `GET /api/keys` - 获取密钥列表
- `POST /api/revalidate-key/<key_id>` - 重新验证密钥
- `DELETE /api/delete-key/<key_id>` - 删除密钥

### 安全特性

- 密钥使用 SHA256 哈希存储
- 页面显示时自动掩码
- 支持环境变量集成
- 自动故障转移

## 集成到云构建

验证通过的密钥会自动集成到云构建流程：

1. 密钥验证通过后保存到 `data/serpapi_keys.json`
2. 更新 `api_key_registration_dates.json` 中的注册日期
3. 下次云构建时自动加载有效密钥
4. 智能选择最优密钥（按重置时间优先级）

## 环境变量支持

系统支持以下环境变量：

- `SERPAPI_KEY_1` 到 `SERPAPI_KEY_10` - 密钥存储
- `SCRAPER_KEYS` - 逗号分隔的密钥列表

## 故障排除

### 常见问题

1. **密钥验证失败**
   - 检查密钥格式是否正确
   - 确认密钥未过期
   - 检查网络连接

2. **服务启动失败**
   - 确认 Python3 已安装
   - 安装依赖：`pip3 install flask requests`
   - 检查端口 5000 是否被占用

3. **密钥不生效**
   - 确认密钥状态为 "valid"
   - 检查环境变量是否正确设置
   - 重新验证密钥

### 日志查看

服务日志会显示在控制台，包括：
- 密钥加载状态
- 验证结果
- 错误信息

## 注意事项

- 密钥信息存储在本地文件中，请确保文件安全
- 定期检查密钥配额状态
- 建议设置密钥过期提醒
- 生产环境建议使用环境变量存储密钥














