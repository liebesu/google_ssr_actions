# 🚀 快速开始

## 🔐 立即登录

**用户名**：`liebesu`  
**密码**：`Liebesu!@#`

## 📋 快速操作

### 1️⃣ 本地测试（立即可用）

```bash
# 直接用浏览器打开
open index.html

# 或者
open test_secure_auth.html  # 测试页面
```

### 2️⃣ 配置 GitHub Actions（生产环境）

1. 进入仓库 **Settings** → **Secrets and variables** → **Actions**
2. 选择 **Variables** 标签
3. 点击 **New repository variable**
4. 添加两个变量：

```
Name: AUTH_USER
Value: liebesu

Name: AUTH_SHA256
Value: 0d605622a936837919436b104b6f15fabeb1f0dea561a631abf8873858f0526a
```

5. 进入 **Actions** 标签
6. 选择工作流并点击 **Run workflow**

### 3️⃣ 修改密码

```bash
# 计算新密码的 SHA-256
python3 -c "import hashlib; pwd='你的新密码'; print(hashlib.sha256(pwd.encode('utf-8')).hexdigest())"

# 复制输出的哈希值
# 更新 GitHub Variables 中的 AUTH_SHA256
# 重新运行 Actions
```

## 📚 详细文档

- **完整配置指南**：`AUTH_SETUP_GUIDE.md`
- **更新总结**：`SECURITY_UPDATE_SUMMARY.md`
- **测试页面**：`test_secure_auth.html`

## ✅ 安全检查清单

- [x] 密码已更新为 `Liebesu!@#`
- [x] 内容默认隐藏（防止绕过）
- [x] GitHub Secrets 配置指南已创建
- [x] 测试页面可用
- [x] 本地 index.html 已更新
- [x] 模板文件已更新

## 🆘 遇到问题？

**无法登录？**
- 确认用户名和密码正确
- 检查浏览器控制台是否有错误
- 尝试清除 LocalStorage 后重试

**页面空白？**
- 按 F12 打开开发者工具
- 检查 Console 标签页
- 确认没有 JavaScript 错误

**GitHub Actions 失败？**
- 检查 Secrets/Variables 配置是否正确
- 查看 Actions 日志中的错误信息
- 确认 workflow 文件语法正确

---

**快速联系**：查看 `AUTH_SETUP_GUIDE.md` 的故障排除部分

