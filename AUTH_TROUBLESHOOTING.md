# 🔐 认证配置快速检查

## ❓ 问题：页面不需要密码就能访问

这说明认证配置没有生效。请按以下步骤检查和修复：

## ✅ 快速检查清单

### 1. 检查 GitHub Variables/Secrets 是否配置

访问：https://github.com/liebesu/google_ssr_actions/settings/secrets/actions

**必须配置以下变量之一：**

#### 方式 A：使用 Variables（推荐）
- `AUTH_USER` = `liebesu`
- `AUTH_SHA256` = `0d605622a936837919436b104b6f15fabeb1f0dea561a631abf8873858f0526a`

#### 方式 B：使用 Secrets（更安全）
- `AUTH_USER` = `liebesu`
- `AUTH_SHA256` = `0d605622a936837919436b104b6f15fabeb1f0dea561a631abf8873858f0526a`

### 2. 检查 Actions 日志

访问：https://github.com/liebesu/google_ssr_actions/actions

查看最新构建的日志，应该看到：

```
=== 🔐 配置认证信息 ===
✅ AUTH_SHA256 from vars configured (长度: 64)
✅ AUTH_USER from vars configured: liebesu
```

如果看到：
```
⚠️ AUTH_SHA256 未配置，页面将无需认证
⚠️ AUTH_USER 未配置
```

说明 Variables/Secrets 没有配置。

### 3. 检查生成的页面

在 Actions 日志中查看：
```
=== 检查认证配置 ===
✅ AUTH_HASH 已正确配置
✅ AUTH_USER 已正确配置
```

如果看到：
```
⚠️ 警告: AUTH_HASH 为空，页面将无需认证
```

说明环境变量没有正确传递。

## 🔧 修复步骤

### 步骤 1：配置 Variables

1. 访问：https://github.com/liebesu/google_ssr_actions/settings/secrets/actions
2. 点击 **Variables** 标签
3. 点击 **New repository variable**
4. 添加：
   - Name: `AUTH_USER`
   - Value: `liebesu`
5. 再次点击 **New repository variable**
6. 添加：
   - Name: `AUTH_SHA256`
   - Value: `0d605622a936837919436b104b6f15fabeb1f0dea561a631abf8873858f0526a`

### 步骤 2：触发新的构建

配置完成后，手动触发一次构建：

1. 访问：https://github.com/liebesu/google_ssr_actions/actions
2. 选择 **build-and-publish-subscriptions**
3. 点击 **Run workflow** → **Run workflow**

### 步骤 3：验证

构建完成后：

1. **检查日志**
   - 应该看到 `✅ AUTH_SHA256 from vars configured`
   - 应该看到 `✅ AUTH_HASH 已正确配置`

2. **访问页面**
   - https://liebesu.github.io/google_ssr_actions/
   - 应该看到登录框
   - 输入用户名 `liebesu` 和密码 `Liebesu!@#` 应该能登录

## 📅 定时构建

**重要**：认证配置已经融合到定时构建中！

- ✅ 手动触发：使用认证配置
- ✅ 定时构建（每4小时）：使用认证配置
- ✅ Push 触发：使用认证配置

所有构建方式都会读取相同的 `vars.AUTH_USER` 和 `vars.AUTH_SHA256` 变量。

## 🆘 仍然不工作？

### 检查 1：变量名称是否正确

确保变量名称完全匹配（区分大小写）：
- ✅ `AUTH_USER`（正确）
- ❌ `auth_user`（错误）
- ❌ `AUTH_USERNAME`（错误）

### 检查 2：变量值是否正确

**AUTH_SHA256** 必须是完整的 64 位十六进制字符串：
- ✅ `0d605622a936837919436b104b6f15fabeb1f0dea561a631abf8873858f0526a`（64字符）
- ❌ `0d605622...`（不完整）

### 检查 3：清除浏览器缓存

如果配置正确但页面仍然不需要密码：

1. 按 `Ctrl+Shift+R`（Windows）或 `Cmd+Shift+R`（Mac）强制刷新
2. 或清除浏览器缓存和 LocalStorage
3. 使用隐私模式访问

### 检查 4：查看构建日志

在 Actions 日志中搜索：
- `=== 🔐 配置认证信息 ===`
- `=== 检查认证配置 ===`

确认输出信息。

## 📝 配置示例

### 正确的配置

**Variables 标签页：**
```
AUTH_USER = liebesu
AUTH_SHA256 = 0d605622a936837919436b104b6f15fabeb1f0dea561a631abf8873858f0526a
```

**构建日志应该显示：**
```
=== 🔐 配置认证信息 ===
✅ AUTH_SHA256 from vars configured (长度: 64)
✅ AUTH_USER from vars configured: liebesu
=== 开始生成订阅 ===
...
=== 检查认证配置 ===
✅ AUTH_HASH 已正确配置
✅ AUTH_USER 已正确配置
```

## 🎯 总结

1. ✅ 配置 GitHub Variables：`AUTH_USER` 和 `AUTH_SHA256`
2. ✅ 手动触发一次构建
3. ✅ 检查构建日志确认配置生效
4. ✅ 访问页面验证需要登录

配置完成后，**所有构建方式（手动、定时、push）都会使用认证配置**！

---

**需要帮助？** 查看 `AUTH_SETUP_GUIDE.md` 获取详细说明。

