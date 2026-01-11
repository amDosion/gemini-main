# 完整重启脚本 - 确保使用最新代码

Write-Host "==================== 后端服务完整重启 ====================" -ForegroundColor Cyan
Write-Host ""

# 步骤 1: 停止所有 Python 进程
Write-Host "步骤 1: 停止所有 Python 进程..." -ForegroundColor Yellow
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    Write-Host "  找到 $($pythonProcesses.Count) 个 Python 进程，正在停止..." -ForegroundColor Gray
    Stop-Process -Name python -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Write-Host "  ✅ 所有 Python 进程已停止" -ForegroundColor Green
} else {
    Write-Host "  ℹ️  没有运行中的 Python 进程" -ForegroundColor Gray
}
Write-Host ""

# 步骤 2: 清理 Python 缓存
Write-Host "步骤 2: 清理 Python 缓存..." -ForegroundColor Yellow
$cacheCount = 0

# 删除 __pycache__ 目录
$pycacheDirs = Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
if ($pycacheDirs) {
    $cacheCount += $pycacheDirs.Count
    $pycacheDirs | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  删除了 $($pycacheDirs.Count) 个 __pycache__ 目录" -ForegroundColor Gray
}

# 删除 .pyc 文件
$pycFiles = Get-ChildItem -Path . -Recurse -File -Filter "*.pyc" -ErrorAction SilentlyContinue
if ($pycFiles) {
    $cacheCount += $pycFiles.Count
    $pycFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host "  删除了 $($pycFiles.Count) 个 .pyc 文件" -ForegroundColor Gray
}

# 删除 .pyo 文件
$pyoFiles = Get-ChildItem -Path . -Recurse -File -Filter "*.pyo" -ErrorAction SilentlyContinue
if ($pyoFiles) {
    $cacheCount += $pyoFiles.Count
    $pyoFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host "  删除了 $($pyoFiles.Count) 个 .pyo 文件" -ForegroundColor Gray
}

if ($cacheCount -eq 0) {
    Write-Host "  ℹ️  没有找到缓存文件" -ForegroundColor Gray
} else {
    Write-Host "  ✅ 清理了 $cacheCount 个缓存文件/目录" -ForegroundColor Green
}
Write-Host ""

# 步骤 3: 验证代码修复
Write-Host "步骤 3: 验证代码修复..." -ForegroundColor Yellow
$verifyPassed = $true

# 检查 image_generator.py
if (Test-Path "app\services\gemini\image_generator.py") {
    $content = Get-Content "app\services\gemini\image_generator.py" -Raw
    if ($content -match "\.scores") {
        Write-Host "  ✅ image_generator.py 使用正确的 'scores' 属性" -ForegroundColor Green
    } else {
        Write-Host "  ❌ image_generator.py 未找到 'scores' 属性" -ForegroundColor Red
        $verifyPassed = $false
    }
    
    if ($content -match "safety_scores") {
        Write-Host "  ❌ image_generator.py 仍包含错误的 'safety_scores'" -ForegroundColor Red
        $verifyPassed = $false
    } else {
        Write-Host "  ✅ image_generator.py 不包含 'safety_scores'" -ForegroundColor Green
    }
}

if ($verifyPassed) {
    Write-Host "  ✅ 代码验证通过" -ForegroundColor Green
} else {
    Write-Host "  ❌ 代码验证失败，请检查代码" -ForegroundColor Red
    Write-Host ""
    Write-Host "按任意键退出..." -ForegroundColor Yellow
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}
Write-Host ""

# 步骤 4: 启动后端服务
Write-Host "步骤 4: 启动后端服务..." -ForegroundColor Yellow
Write-Host "  命令: python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 21574" -ForegroundColor Gray
Write-Host ""
Write-Host "==================== 后端服务启动中 ====================" -ForegroundColor Cyan
Write-Host ""
Write-Host "提示：" -ForegroundColor Yellow
Write-Host "  - 后端将在 http://0.0.0.0:21574 上运行" -ForegroundColor Gray
Write-Host "  - 前端代理将 /api 请求转发到后端" -ForegroundColor Gray
Write-Host "  - 按 Ctrl+C 停止服务" -ForegroundColor Gray
Write-Host ""

# 设置环境变量禁用字节码缓存
$env:PYTHONDONTWRITEBYTECODE = "1"

# 启动服务
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 21574
