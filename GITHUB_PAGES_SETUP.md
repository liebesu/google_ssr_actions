# GitHub Pages 配置指南

## 问题诊断
当前首页返回 404 错误，可能的原因：

1. **GitHub Pages 未启用**
2. **部署权限不足**
3. **环境配置错误**

## 解决步骤

### 1. 启用 GitHub Pages
1. 访问仓库设置：`https://github.com/liebesu/google_ssr_actions/settings/pages`
2. 在 "Source" 部分选择 "GitHub Actions"
3. 保存设置

### 2. 配置部署权限
1. 在仓库设置中找到 "Actions" → "General"
2. 在 "Workflow permissions" 部分选择 "Read and write permissions"
3. 勾选 "Allow GitHub Actions to create and approve pull requests"

### 3. 检查环境配置
1. 在仓库设置中找到 "Environments"
2. 确保存在 "github-pages" 环境
3. 如果没有，需要手动创建

### 4. 验证构建状态
- 查看 Actions 运行状态：`https://github.com/liebesu/google_ssr_actions/actions`
- 检查是否有部署错误

## 当前工作流配置

工作流文件：`.github/workflows/build-and-publish-subscriptions.yml`

### 构建步骤
1. **构建阶段**：生成 `dist/` 目录
2. **上传阶段**：上传 Pages 工件
3. **部署阶段**：部署到 GitHub Pages

### 关键配置
```yaml
- name: Upload artifact
  uses: actions/upload-pages-artifact@v3
  with:
    path: dist

- name: Deploy to GitHub Pages
  uses: actions/deploy-pages@v4
```

## 故障排除

### 检查清单
- [ ] GitHub Pages 已启用
- [ ] 部署权限已配置
- [ ] Actions 运行成功
- [ ] 工件上传成功
- [ ] 部署步骤完成

### 常见错误
1. **403 Forbidden**：权限不足
2. **404 Not Found**：Pages 未启用
3. **构建失败**：检查 Actions 日志

## 预期结果
配置完成后，应该能够访问：
- `https://liebesu.github.io/google_ssr_actions/`
- 显示订阅聚合器首页
- 包含 SerpAPI 密钥状态卡片
