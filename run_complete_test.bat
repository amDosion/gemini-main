@echo off
chcp 65001 >nul
echo ========================================
echo 完整测试 Deep Research 功能
echo ========================================
echo.

cd /d D:\gemini-main\gemini-main\backend

echo [1/2] 激活虚拟环境...
call .venv\Scripts\activate.bat

echo [2/2] 运行完整测试...
echo.

cd ..
python test_complete_flow.py

echo.
echo ========================================
echo 测试完成
echo ========================================
pause
