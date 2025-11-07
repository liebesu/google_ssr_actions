# ⚙️ Workflow 文件更新说明

## 📋 当前状态

✅ **代码已成功推送到 GitHub！**

但是，由于 GitHub token 权限限制，`.github/workflows/build-and-publish-subscriptions.yml` 文件需要手动更新。

## 🔧 手动更新步骤

### 方法一：通过 GitHub Web 界面（推荐）

1. **访问文件**
   - 打开：https://github.com/liebesu/google_ssr_actions/blob/main/.github/workflows/build-and-publish-subscriptions.yml

2. **编辑文件**
   - 点击右上角的 **✏️ Edit** 按钮

3. **修改 cron 表达式**
   - 找到第 6 行：
     ```yaml
     - cron: "0 */3 * * *"
     ```
   - 修改为：
     ```yaml
     - cron: "0 */4 * * *"  # 每4小时构建一次
     ```

4. **提交更改**
   - 在页面底部填写提交信息：`⚙️ 调整自动构建频率为每4小时`
   - 点击 **Commit changes**

### 方法二：通过命令行（如果有 workflow 权限）

```bash
cd /Users/henry/enlink/liebesu_code/github_actions/ssr/google_ssr_actions
git pull origin main
# 编辑文件，将 cron 从 "0 */3 * * *" 改为 "0 */4 * * *"
git add .github/workflows/build-and-publish-subscriptions.yml
git commit -m "⚙️ 调整自动构建频率为每4小时"
git push origin main
```

## ✅ 验证更新

更新后，检查：

1. **查看文件**
   - https://github.com/liebesu/google_ssr_actions/blob/main/.github/workflows/build-and-publish-subscriptions.yml
   - 确认第 6 行显示：`- cron: "0 */4 * * *"`

2. **查看 Actions**
   - https://github.com/liebesu/google_ssr_actions/actions
   - 确认 workflow 配置已更新

## 📅 构建计划

更新后，系统将每4小时自动构建一次：

- **UTC 时间**：00:00, 04:00, 08:00, 12:00, 16:00, 20:00
- **北京时间**：08:00, 12:00, 16:00, 20:00, 00:00(+1), 04:00(+1)

---

**注意**：本地已经修改了 workflow 文件，但由于权限限制无法推送。请通过 Web 界面手动更新。

