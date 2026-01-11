# ============================================
# 清理缓存并重启后端服务
# ============================================

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "清理 Python 缓存并重启后端服务" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan

# 步骤 1: 停止现有的 Python 进程
Write-Host "`n[1/5] 停止现有的 Python 进程..." -ForegroundColor Yellow
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    Write-Host "找到 $($pythonProcesses.Count) 个 Python 进程，正在停止..." -ForegroundColor Yellow
    Stop-Process -Name python -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Write-Host "✅ Python 进程已停止" -ForegroundColor Green
} else {
    Write-Host "✅ 没有运行中的 Python 进程" -ForegroundColor Green
}

# 步骤 2: 清理 __pycache__ 目录
Write-Host "`n[2/5] 清理 __pycache__ 目录..." -ForegroundColor Yellow
$pycacheDirs = Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
if ($pycacheDirs) {
    Write-Host "找到 $($pycacheDirs.Count) 个 __pycache__ 目录" -ForegroundColor Yellow
    $pycacheDirs | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "✅ __pycache__ 目录已清理" -ForegroundColor Green
} else {
    Write-Host "✅ 没有 __pycache__ 目录" -ForegroundColor Green
}

# 步骤 3: 清理 .pyc 文件
Write-Host "`n[3/5] 清理 .pyc 文件..." -ForegroundColor Yellow
$pycFiles = Get-ChildItem -Path . -Recurse -File -Filter "*.pyc" -ErrorAction SilentlyContinue
if ($pycFiles) {
    Write-Host "找到 $($pycFiles.Count) 个 .pyc 文件" -ForegroundColor Yellow
    $pycFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host "✅ .pyc 文件已清理" -ForegroundColor Green
} else {
    Write-Host "✅ 没有 .pyc 文件" -ForegroundColor Green
}

# 步骤 4: 清理 .pyo 文件
Write-Host "`n[4/5] 清理 .pyo 文件..." -ForegroundColor Yellow
$pyoFiles = Get-ChildItem -Path . -Recurse -File -Filter "*.pyo" -ErrorAction SilentlyContinue
if ($pyoFiles) {
    Write-Host "找到 $($pyoFiles.Count) 个 .pyo 文件" -ForegroundColor Yellow
    $pyoFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host "✅ .pyo 文件已清理" -ForegroundColor Green
} else {
    Write-Host "✅ 没有 .pyo 文件" -ForegroundColor Green
}

# 步骤 5: 验证代码修改
Write-Host "`n[5/5] 验证代码修改..." -ForegroundColor Yellow

# 检查是否使用正确的属性名 'scores'
$scoresCheck = Select-String -Path "app\services\gemini\image_generator.py" -Pattern "hasattr\(generated_image\.safety_attributes, 'scores'\)" -Quiet
if ($scoresCheck) {
    Write-Host "✅ image_generator.py 使用正确的属性名 'scores'" -ForegroundColor Green
} else {
    Write-Host "❌ image_generator.py 未找到 'scores' 属性检查" -ForegroundColor Red
}

# 检查是否还有错误的 'safety_scores'
$safetyScoresCheck = Select-String -Path "app\services\gemini\*.py" -Pattern "safety_scores" -Quiet
if ($safetyScoresCheck) {
    Write-Host "❌ 警告：代码中仍然存在 'safety_scores' 引用" -ForegroundColor Red
    Select-String -Path "app\services\gemini\*.py" -Pattern "safety_scores"
} else {
    Write-Host "✅ 代码中没有 'safety_scores' 引用" -ForegroundColor Green
}

# 启动后端服务
Write-Host "`n" + "=" * 80 -ForegroundColor Cyan
Write-Host "启动后端服务" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan

Write-Host "`n提示：" -ForegroundColor Yellow
Write-Host "  - 服务将在 http://0.0.0.0:21573 启动" -ForegroundColor Yellow
Write-Host "  - 使用 --reload 参数，代码变更会自动重载" -ForegroundColor Yellow
Write-Host "  - 按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host ""

# 设置环境变量禁用字节码生成
$env:PYTHONDONTWRITEBYTECODE = "1"

# 启动服务
python -B -m uvicorn app.main:app --reload --host 0.0.0.0 --port 21573
