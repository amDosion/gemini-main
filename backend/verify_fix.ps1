# 验证图像生成修复
# 运行测试脚本验证所有修复是否生效

Write-Host "==================== 验证图像生成修复 ====================" -ForegroundColor Cyan
Write-Host ""

# 检查环境变量
if (-not $env:GEMINI_API_KEY) {
    Write-Host "❌ 错误: 未设置 GEMINI_API_KEY 环境变量" -ForegroundColor Red
    exit 1
}

Write-Host "✅ GEMINI_API_KEY 已设置" -ForegroundColor Green
Write-Host ""

# 运行测试
Write-Host "运行图像生成测试..." -ForegroundColor Yellow
python test_image_generation.py

Write-Host ""
Write-Host "==================== 验证完成 ====================" -ForegroundColor Cyan
