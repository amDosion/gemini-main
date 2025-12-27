@echo off
echo ========================================
echo 测试修复后的 Interactions API
echo ========================================
echo.

cd /d D:\gemini-main\gemini-main\backend
call .venv\Scripts\activate.bat

echo 运行测试脚本...
echo.

python ..\test_interactions_api_fixed.py

echo.
echo ========================================
echo 测试完成
echo ========================================
pause
