@echo off
echo ========================================
echo 重启后端服务 (应用 model_capabilities.py 修复)
echo ========================================
echo.

echo [1/3] 停止现有的后端进程...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *uvicorn*" 2>nul
taskkill /F /IM uvicorn.exe 2>nul
timeout /t 2 /nobreak >nul

echo [2/3] 清除 Python 缓存...
cd /d "%~dp0"
for /r %%i in (__pycache__) do (
    if exist "%%i" (
        echo   删除: %%i
        rd /s /q "%%i"
    )
)
for /r %%i in (*.pyc) do (
    if exist "%%i" del /q "%%i"
)

echo [3/3] 启动后端服务...
echo.
echo 提示: 如果需要手动启动，请运行:
echo   cd backend
echo   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
echo.
cd backend
start "Gemini Backend" cmd /k "uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

echo.
echo ========================================
echo 后端服务已重启！
echo ========================================
echo.
echo 接下来请执行以下步骤:
echo 1. 等待 5 秒让后端完全启动
echo 2. 刷新前端页面 (Ctrl+F5 强制刷新)
echo 3. 进入 Settings -^> Profiles
echo 4. 编辑 Google 配置
echo 5. 点击 "Verify Connection"
echo 6. 确保 Gemini 3 Pro Image Preview 被勾选
echo 7. 点击 Save
echo 8. 切换到 image-edit 模式测试
echo.
pause
