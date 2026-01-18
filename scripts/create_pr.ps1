# GitHub PR 自动化创建脚本
# 使用 GitHub API 创建 Pull Request

param(
    [string]$Owner = "amDosion",
    [string]$Repo = "gemini-main",
    [string]$Head = "docs/git-pr-setup",
    [string]$Base = "master",
    [string]$Title = "docs: 添加 GitHub PR 模板和工作流配置",
    [string]$Token = $env:GITHUB_PERSONAL_ACCESS_TOKEN
)

# 从 MCP 配置读取 Token（如果环境变量未设置）
if (-not $Token) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $repoRoot = Split-Path -Parent $scriptDir
    $mcpConfigPath = Join-Path $repoRoot ".kiro\settings\mcp.json"
    
    if (Test-Path $mcpConfigPath) {
        try {
            $mcpConfig = Get-Content $mcpConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($mcpConfig.mcpServers.github.env.GITHUB_PERSONAL_ACCESS_TOKEN) {
                $Token = $mcpConfig.mcpServers.github.env.GITHUB_PERSONAL_ACCESS_TOKEN
            }
        } catch {
            Write-Host "警告: 无法读取 MCP 配置文件" -ForegroundColor Yellow
        }
    }
}

if (-not $Token) {
    Write-Host "❌ 错误: 未找到 GitHub Personal Access Token" -ForegroundColor Red
    Write-Host "请设置环境变量 GITHUB_PERSONAL_ACCESS_TOKEN 或在 .kiro/settings/mcp.json 中配置" -ForegroundColor Yellow
    exit 1
}

# PR 描述内容
$body = @'
# Pull Request

## 描述 (Description)

本次 PR 为项目添加了完整的 GitHub 配置，包括 Issue 模板、Pull Request 模板、GitHub Actions 工作流和相关文档。

## 相关 Issue (Related Issue)

- N/A

## 变更类型 (Type of Change)

- [x] 文档更新 (Documentation update)
- [x] 构建/配置相关 (Build/Config)

## 变更内容 (Changes)

### 主要变更
- 添加 Issue 模板（Bug 报告和功能请求）
- 添加 Pull Request 模板
- 配置 GitHub Actions 工作流
- 添加贡献指南和 Git 使用文档
- 更新 .gitignore

### 代码变更
- `.github/ISSUE_TEMPLATE/bug_report.md` - Bug 报告模板
- `.github/ISSUE_TEMPLATE/feature_request.md` - 功能请求模板
- `.github/PULL_REQUEST_TEMPLATE/default.md` - PR 模板
- `.github/workflows/pr-check.yml` - PR 检查工作流
- `.github/workflows/code-quality.yml` - 代码质量检查工作流
- `.github/CONTRIBUTING.md` - 贡献指南
- `.github/README.md` - GitHub 配置说明
- `docs/GIT_SETUP.md` - Git 配置和使用指南
- `docs/GIT_PR_SETUP_SUMMARY.md` - 配置总结文档
- `.gitignore` - 更新忽略规则

## 测试 (Testing)

- [x] 已进行手动测试 (Manual testing performed)
- [x] 测试通过 (All tests pass)

### 测试步骤
1. 验证所有模板文件格式正确
2. 验证 GitHub Actions 工作流语法正确
3. 验证文档链接和格式

## 检查清单 (Checklist)

- [x] 代码遵循项目的代码风格
- [x] 已进行自我审查
- [x] 文档已相应更新
- [x] 变更不会产生新的警告
- [x] 已检查代码安全性

## 安全注意事项 (Security Considerations)

- [x] 不涉及安全问题
- [x] 已审查安全影响

## 额外说明 (Additional Notes)

本次配置为项目建立了标准的贡献流程和 PR 检查机制，将有助于：
- 规范 Issue 和 PR 的格式
- 自动检查 PR 标题格式（Conventional Commits）
- 自动运行代码质量检查
- 提供清晰的贡献指南
'@

# 构建请求体
$prData = @{
    title = $Title
    head = $Head
    base = $Base
    body = $body
} | ConvertTo-Json

# GitHub API 端点
$apiUrl = "https://api.github.com/repos/$Owner/$Repo/pulls"

# 设置请求头
$headers = @{
    "Authorization" = "token $Token"
    "Accept" = "application/vnd.github.v3+json"
    "Content-Type" = "application/json"
}

Write-Host "🚀 正在创建 Pull Request..." -ForegroundColor Cyan
Write-Host "  仓库: $Owner/$Repo" -ForegroundColor Gray
Write-Host "  源分支: $Head" -ForegroundColor Gray
Write-Host "  目标分支: $Base" -ForegroundColor Gray
Write-Host "  标题: $Title" -ForegroundColor Gray
Write-Host ""

try {
    # 发送 API 请求
    $response = Invoke-RestMethod -Uri $apiUrl -Method Post -Headers $headers -Body $prData -ErrorAction Stop
    
    Write-Host "✅ Pull Request 创建成功！" -ForegroundColor Green
    Write-Host ""
    Write-Host "PR 信息:" -ForegroundColor Cyan
    Write-Host "  编号: #$($response.number)" -ForegroundColor White
    Write-Host "  标题: $($response.title)" -ForegroundColor White
    Write-Host "  状态: $($response.state)" -ForegroundColor White
    Write-Host "  URL: $($response.html_url)" -ForegroundColor White
    Write-Host ""
    Write-Host "🔗 查看 PR: $($response.html_url)" -ForegroundColor Yellow
    
    # 在浏览器中打开 PR
    Start-Process $response.html_url
    
} catch {
    $errorResponse = $_.ErrorDetails.Message
    Write-Host "创建 PR 失败" -ForegroundColor Red
    Write-Host "错误信息: $errorResponse" -ForegroundColor Red
    
    if ($errorResponse -match "already exists") {
        Write-Host ""
        Write-Host "提示: 该分支的 PR 可能已存在" -ForegroundColor Yellow
        $prUrl = "https://github.com/$Owner/$Repo/pulls"
        Write-Host "请访问: $prUrl" -ForegroundColor Yellow
    }
    
    exit 1
}
