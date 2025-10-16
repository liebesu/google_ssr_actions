# SerpAPI 密钥配置指南

## 概述

本系统支持多个SerpAPI密钥，以提高搜索配额和可靠性。您需要在GitHub仓库的Secrets中配置这些密钥。

## 配置步骤

### 1. 访问GitHub仓库设置

1. 进入您的GitHub仓库：`https://github.com/liebesu/google_ssr_actions`
2. 点击 **Settings** 标签
3. 在左侧菜单中点击 **Secrets and variables** → **Actions**

### 2. 添加SerpAPI密钥

点击 **New repository secret** 按钮，添加以下密钥：

| Secret名称 | 描述 | 示例值 |
|-----------|------|--------|
| `SERPAPI_KEY_1` | 第一个SerpAPI密钥 | `your_serpapi_key_1_here` |
| `SERPAPI_KEY_2` | 第二个SerpAPI密钥 | `your_serpapi_key_2_here` |
| `SERPAPI_KEY_3` | 第三个SerpAPI密钥 | `your_serpapi_key_3_here` |
| `SERPAPI_KEY_4` | 第四个SerpAPI密钥 | `your_serpapi_key_4_here` |
| `SERPAPI_KEY_5` | 第五个SerpAPI密钥 | `your_serpapi_key_5_here` |
| `SERPAPI_KEY_6` | 第六个SerpAPI密钥 | `your_serpapi_key_6_here` |
| `SERPAPI_KEY_7` | 第七个SerpAPI密钥 | `your_serpapi_key_7_here` |
| `SERPAPI_KEY_8` | 第八个SerpAPI密钥 | `your_serpapi_key_8_here` |
| `SERPAPI_KEY_9` | 第九个SerpAPI密钥 | `your_serpapi_key_9_here` |
| `SERPAPI_KEY_10` | 第十个SerpAPI密钥 | `your_serpapi_key_10_here` |

### 3. 可选：批量密钥管理

您也可以使用 `SERPAPI_KEYS_JSON` secret 来批量管理密钥：

```json
[
  {
    "name": "Key-1",
    "key": "your_serpapi_key_1_here",
    "registration_date": "2025-01-01",
    "description": "主要密钥"
  },
  {
    "name": "Key-2", 
    "key": "your_serpapi_key_2_here",
    "registration_date": "2025-01-02",
    "description": "备用密钥"
  }
]
```

## 密钥管理页面

您也可以使用Web界面管理密钥：

1. 访问：`https://liebesu.github.io/google_ssr_actions/key_manager.html`
2. 添加、验证和管理您的SerpAPI密钥
3. 获取GitHub Actions配置代码

## 验证配置

配置完成后：

1. 等待下一次自动构建（每3小时）或手动触发构建
2. 访问：`https://liebesu.github.io/google_ssr_actions/`
3. 查看 **SerpAPI 密钥状态** 卡片
4. 应该显示正确的密钥数量和状态

## 故障排除

### 密钥状态显示为0

- 检查GitHub Secrets是否正确配置
- 确认密钥格式正确（不包含多余的空格或换行）
- 查看GitHub Actions构建日志

### 密钥验证失败

- 确认密钥在SerpAPI控制台中有效
- 检查密钥是否有足够的配额
- 验证密钥权限设置

### 页面显示问题

- 清除浏览器缓存
- 检查浏览器控制台是否有JavaScript错误
- 确认页面完全加载

## 支持

如果遇到问题，请检查：

1. GitHub Actions构建日志
2. 浏览器开发者工具控制台
3. 密钥管理页面的状态

---

**注意**：密钥信息是敏感数据，请妥善保管，不要泄露给他人。



