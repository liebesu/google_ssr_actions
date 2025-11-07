# ⚙️ Workflow 文件更新说明（重要）

## 📋 当前状态

✅ **代码已推送，但 workflow 文件需要手动更新**

由于 GitHub token 权限限制，`.github/workflows/build-and-publish-subscriptions.yml` 文件需要手动更新以启用认证调试功能。

## 🔧 手动更新步骤

### 方法：通过 GitHub Web 界面

1. **访问文件**
   - https://github.com/liebesu/google_ssr_actions/edit/main/.github/workflows/build-and-publish-subscriptions.yml

2. **找到第 67-110 行**（`Generate subscriptions` 步骤）

3. **替换整个步骤**为以下内容：

```yaml
      - name: Generate subscriptions
        run: |
          mkdir -p dist
          # Disable proxy in CI and emit index/health to avoid 404
          export DISABLE_PROXY=1
          # Pass SerpAPI keys as environment variable for backup plan
          if [ -n "${{ secrets.SCRAPER_KEYS }}" ]; then export SCRAPER_KEYS="${{ secrets.SCRAPER_KEYS }}"; fi
          # Pass SerpAPI keys from individual secrets
          if [ -n "${{ secrets.SERPAPI_KEY_1 }}" ]; then export SERPAPI_KEY_1="${{ secrets.SERPAPI_KEY_1 }}"; echo "Set SERPAPI_KEY_1"; fi
          if [ -n "${{ secrets.SERPAPI_KEY_2 }}" ]; then export SERPAPI_KEY_2="${{ secrets.SERPAPI_KEY_2 }}"; echo "Set SERPAPI_KEY_2"; fi
          if [ -n "${{ secrets.SERPAPI_KEY_3 }}" ]; then export SERPAPI_KEY_3="${{ secrets.SERPAPI_KEY_3 }}"; echo "Set SERPAPI_KEY_3"; fi
          if [ -n "${{ secrets.SERPAPI_KEY_4 }}" ]; then export SERPAPI_KEY_4="${{ secrets.SERPAPI_KEY_4 }}"; echo "Set SERPAPI_KEY_4"; fi
          if [ -n "${{ secrets.SERPAPI_KEY_5 }}" ]; then export SERPAPI_KEY_5="${{ secrets.SERPAPI_KEY_5 }}"; echo "Set SERPAPI_KEY_5"; fi
          if [ -n "${{ secrets.SERPAPI_KEY_6 }}" ]; then export SERPAPI_KEY_6="${{ secrets.SERPAPI_KEY_6 }}"; echo "Set SERPAPI_KEY_6"; fi
          if [ -n "${{ secrets.SERPAPI_KEY_7 }}" ]; then export SERPAPI_KEY_7="${{ secrets.SERPAPI_KEY_7 }}"; echo "Set SERPAPI_KEY_7"; fi
          if [ -n "${{ secrets.SERPAPI_KEY_8 }}" ]; then export SERPAPI_KEY_8="${{ secrets.SERPAPI_KEY_8 }}"; echo "Set SERPAPI_KEY_8"; fi
          if [ -n "${{ secrets.SERPAPI_KEY_9 }}" ]; then export SERPAPI_KEY_9="${{ secrets.SERPAPI_KEY_9 }}"; echo "Set SERPAPI_KEY_9"; fi
          if [ -n "${{ secrets.SERPAPI_KEY_10 }}" ]; then export SERPAPI_KEY_10="${{ secrets.SERPAPI_KEY_10 }}"; echo "Set SERPAPI_KEY_10"; fi
          # Pass optional auth envs (优先级: secrets > vars)
          echo "=== 🔐 配置认证信息 ==="
          if [ -n "${{ vars.AUTH_PLAIN }}" ]; then 
            export AUTH_PLAIN="${{ vars.AUTH_PLAIN }}"; 
            echo "✅ AUTH_PLAIN from vars configured"
          fi
          if [ -n "${{ secrets.AUTH_SHA256 }}" ]; then 
            export AUTH_SHA256="${{ secrets.AUTH_SHA256 }}"; 
            echo "✅ AUTH_SHA256 from secrets configured (长度: ${#AUTH_SHA256})"
          elif [ -n "${{ vars.AUTH_SHA256 }}" ]; then 
            export AUTH_SHA256="${{ vars.AUTH_SHA256 }}"; 
            echo "✅ AUTH_SHA256 from vars configured (长度: ${#AUTH_SHA256})"
          else
            echo "⚠️ AUTH_SHA256 未配置，页面将无需认证"
          fi
          if [ -n "${{ secrets.AUTH_USER }}" ]; then 
            export AUTH_USER="${{ secrets.AUTH_USER }}"; 
            echo "✅ AUTH_USER from secrets configured: $AUTH_USER"
          elif [ -n "${{ vars.AUTH_USER }}" ]; then 
            export AUTH_USER="${{ vars.AUTH_USER }}"; 
            echo "✅ AUTH_USER from vars configured: $AUTH_USER"
          else
            echo "⚠️ AUTH_USER 未配置"
          fi
          echo "=== 开始生成订阅 ==="
          python aggregator_cli.py --output-dir dist --dedup --public-base https://liebesu.github.io/google_ssr_actions --github-discovery --emit-health --emit-index
          
          # 确保 dist 目录有内容
          echo "=== 检查 dist 目录内容 ==="
          ls -la dist/
          echo "=== 检查 index.html ==="
          if [ -f dist/index.html ]; then
            echo "index.html 存在，大小: $(wc -c < dist/index.html) 字节"
            echo "=== 检查认证配置 ==="
            if grep -q 'AUTH_HASH = "__AUTH_HASH__"' dist/index.html; then
              echo "⚠️ 警告: AUTH_HASH 占位符未被替换，认证可能未配置"
            elif grep -q 'AUTH_HASH = ""' dist/index.html; then
              echo "⚠️ 警告: AUTH_HASH 为空，页面将无需认证"
            elif grep -q 'AUTH_HASH = "0d605622' dist/index.html; then
              echo "✅ AUTH_HASH 已正确配置"
            else
              echo "ℹ️ AUTH_HASH 状态: $(grep -o 'AUTH_HASH = "[^"]*"' dist/index.html | head -1)"
            fi
            if grep -q 'AUTH_USER = "__AUTH_USER__"' dist/index.html; then
              echo "⚠️ 警告: AUTH_USER 占位符未被替换"
            elif grep -q 'AUTH_USER = "liebesu"' dist/index.html; then
              echo "✅ AUTH_USER 已正确配置"
            else
              echo "ℹ️ AUTH_USER 状态: $(grep -o 'AUTH_USER = "[^"]*"' dist/index.html | head -1)"
            fi
            head -15 dist/index.html
          else
            echo "index.html 不存在！"
          fi
```

4. **提交更改**
   - 提交信息：`🔐 增强认证配置：添加调试输出和验证步骤`
   - 点击 **Commit changes**

## ✅ 更新后的效果

更新后，每次构建都会：

1. **显示认证配置状态**
   ```
   === 🔐 配置认证信息 ===
   ✅ AUTH_SHA256 from vars configured (长度: 64)
   ✅ AUTH_USER from vars configured: liebesu
   ```

2. **验证生成的页面**
   ```
   === 检查认证配置 ===
   ✅ AUTH_HASH 已正确配置
   ✅ AUTH_USER 已正确配置
   ```

3. **如果未配置，会显示警告**
   ```
   ⚠️ AUTH_SHA256 未配置，页面将无需认证
   ⚠️ AUTH_USER 未配置
   ```

## 📅 定时构建已融合认证

**重要**：认证配置已经融合到所有构建方式中：

- ✅ **手动触发**：使用认证配置
- ✅ **定时构建**（每4小时）：使用认证配置  
- ✅ **Push 触发**：使用认证配置

所有构建都会读取相同的 `vars.AUTH_USER` 和 `vars.AUTH_SHA256` 变量。

## 🔍 如何检查认证是否生效

### 方法 1：查看 Actions 日志

访问：https://github.com/liebesu/google_ssr_actions/actions

在最新构建的日志中搜索：
- `=== 🔐 配置认证信息 ===`
- `=== 检查认证配置 ===`

### 方法 2：访问页面

访问：https://liebesu.github.io/google_ssr_actions/

- ✅ **应该看到登录框** = 认证已配置
- ❌ **直接看到内容** = 认证未配置

## 🆘 如果仍然不需要密码

请检查：

1. **GitHub Variables 是否配置**
   - https://github.com/liebesu/google_ssr_actions/settings/secrets/actions
   - 确认 `AUTH_USER` 和 `AUTH_SHA256` 存在

2. **查看构建日志**
   - 应该看到 `✅ AUTH_SHA256 from vars configured`
   - 如果看到 `⚠️ AUTH_SHA256 未配置`，说明 Variables 没有配置

3. **查看生成的页面**
   - 日志中应该显示 `✅ AUTH_HASH 已正确配置`
   - 如果显示 `⚠️ AUTH_HASH 为空`，说明环境变量没有传递

详细排查步骤请查看：`AUTH_TROUBLESHOOTING.md`

---

**更新 workflow 文件后，认证配置将在所有构建方式（包括定时构建）中生效！** 🎉

