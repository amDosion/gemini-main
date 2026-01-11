# Claude Agent Hooks 环境设置脚本（Windows PowerShell）
# 用途：安装所有必需的工具和依赖
# 使用：.\setup_hooks.ps1

Write-Host "🔧 Claude Agent Hooks 环境设置" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan

# 检查 Python
Write-Host "检查 Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Python: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "❌ Python 未安装" -ForegroundColor Red
    exit 1
}

# 检查 Node.js
Write-Host "检查 Node.js..." -ForegroundColor Yellow
$nodeVersion = node --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Node.js: $nodeVersion" -ForegroundColor Green
} else {
    Write-Host "❌ Node.js 未安装" -ForegroundColor Red
    exit 1
}

# 检查 npm
Write-Host "检查 npm..." -ForegroundColor Yellow
$npmVersion = npm --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ npm: $npmVersion" -ForegroundColor Green
} else {
    Write-Host "❌ npm 未安装" -ForegroundColor Red
    exit 1
}

# 安装 Python 工具
Write-Host "`n📦 安装 Python 开发工具..." -ForegroundColor Yellow
$pythonTools = @("black", "ruff", "mypy", "pytest", "pytest-cov", "pytest-asyncio", "pip-audit")

foreach ($tool in $pythonTools) {
    Write-Host "  - 安装 $tool..." -NoNewline
    pip install $tool --quiet 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✅" -ForegroundColor Green
    } else {
        Write-Host " ❌" -ForegroundColor Red
    }
}

# 安装后端开发依赖
Write-Host "`n📦 安装后端开发依赖..." -ForegroundColor Yellow
Set-Location backend
if (Test-Path "requirements-dev.txt") {
    pip install -r requirements-dev.txt
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ 后端开发依赖安装完成" -ForegroundColor Green
    } else {
        Write-Host "❌ 后端开发依赖安装失败" -ForegroundColor Red
    }
}
Set-Location ..

# 安装前端开发依赖
Write-Host "`n📦 安装前端开发依赖..." -ForegroundColor Yellow
if (Test-Path "package.json") {
    npm install --silent
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ 前端依赖安装完成" -ForegroundColor Green
    } else {
        Write-Host "❌ 前端依赖安装失败" -ForegroundColor Red
    }
}

# 安装前端开发工具
Write-Host "`n📦 安装前端开发工具..." -ForegroundColor Yellow
$frontendTools = @("prettier", "eslint", "@typescript-eslint/parser", "@typescript-eslint/eslint-plugin")

foreach ($tool in $frontendTools) {
    Write-Host "  - 安装 $tool..." -NoNewline
    npm install --save-dev $tool --silent 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✅" -ForegroundColor Green
    } else {
        Write-Host " ⚠️ (可能已存在)" -ForegroundColor Yellow
    }
}

# 创建日志目录
Write-Host "`n📁 创建日志目录..." -ForegroundColor Yellow
$logDir = ".claude\logs"
if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    Write-Host "✅ 日志目录已创建: $logDir" -ForegroundColor Green
} else {
    Write-Host "✅ 日志目录已存在" -ForegroundColor Green
}

# 创建备份目录
Write-Host "📁 创建备份目录..." -ForegroundColor Yellow
$backupDir = ".claude\backups"
if (!(Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    Write-Host "✅ 备份目录已创建: $backupDir" -ForegroundColor Green
} else {
    Write-Host "✅ 备份目录已存在" -ForegroundColor Green
}

# 创建配置文件（如果不存在）
Write-Host "`n📄 检查配置文件..." -ForegroundColor Yellow

if (!(Test-Path ".prettierrc")) {
    Write-Host "创建 .prettierrc..." -NoNewline
    @"
{
  "semi": true,
  "trailingComma": "es5",
  "singleQuote": true,
  "printWidth": 100,
  "tabWidth": 2,
  "useTabs": false
}
"@ | Out-File -FilePath ".prettierrc" -Encoding UTF8
    Write-Host " ✅" -ForegroundColor Green
}

if (!(Test-Path "backend\.ruff.toml")) {
    Write-Host "创建 backend\.ruff.toml..." -NoNewline
    @"
line-length = 100
target-version = "py310"

[lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "A", "C4", "DTZ", "T10", "EM", "ISC", "ICN", "G", "PIE", "PT", "Q", "RET", "SIM", "TID", "ARG", "ERA", "PD", "PL", "TRY", "NPY", "RUF"]
ignore = ["E501", "B008", "TRY003"]

[lint.per-file-ignores]
"__init__.py" = ["F401"]
"tests/**/*.py" = ["ARG", "PLR2004"]
"@ | Out-File -FilePath "backend\.ruff.toml" -Encoding UTF8
    Write-Host " ✅" -ForegroundColor Green
}

# 测试配置
Write-Host "`n🧪 测试 Hooks 配置..." -ForegroundColor Yellow

Write-Host "  - 测试 Black..." -NoNewline
echo "print('test')" | python -m black - --quiet 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host " ✅" -ForegroundColor Green
} else {
    Write-Host " ❌" -ForegroundColor Red
}

Write-Host "  - 测试 Ruff..." -NoNewline
$testFile = "backend\test_temp.py"
"print('test')" | Out-File -FilePath $testFile -Encoding UTF8
cd backend
ruff check $testFile --quiet 2>&1 | Out-Null
$ruffResult = $LASTEXITCODE
cd ..
Remove-Item $testFile -ErrorAction SilentlyContinue
if ($ruffResult -eq 0) {
    Write-Host " ✅" -ForegroundColor Green
} else {
    Write-Host " ❌" -ForegroundColor Red
}

Write-Host "  - 测试 Prettier..." -NoNewline
echo "console.log('test')" | npx prettier --parser typescript --stdin-filepath test.ts 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host " ✅" -ForegroundColor Green
} else {
    Write-Host " ❌" -ForegroundColor Red
}

Write-Host "  - 测试 pytest..." -NoNewline
cd backend
pytest --version 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host " ✅" -ForegroundColor Green
} else {
    Write-Host " ❌" -ForegroundColor Red
}
cd ..

Write-Host "  - 测试 Vitest..." -NoNewline
npx vitest --version 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host " ✅" -ForegroundColor Green
} else {
    Write-Host " ❌" -ForegroundColor Red
}

# 完成
Write-Host "`n✨ 环境设置完成！" -ForegroundColor Cyan
Write-Host "`n📖 下一步：" -ForegroundColor Yellow
Write-Host "  1. 查看配置：.claude\hooks.json" -ForegroundColor White
Write-Host "  2. 阅读文档：.claude\HOOKS_GUIDE.md" -ForegroundColor White
Write-Host "  3. 启用需要的 Hooks：编辑 hooks.json 中的 'enabled' 字段" -ForegroundColor White
Write-Host "  4. 测试 Hooks：修改一个文件并观察 Claude Code 的行为`n" -ForegroundColor White
