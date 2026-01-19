# Gemini Chat 项目

## 项目简介

这是一个基于 FastAPI 后端和 React 前端的 Gemini Chat 应用程序。

## 环境要求

- Node.js (用于前端)
- Python 3.x (用于后端)
- npm 或 yarn (包管理器)

## 安装步骤

### 1. 后端环境设置

1. 进入后端目录：
   ```bash
   cd backend
   ```

2. 创建 Python 虚拟环境：
   ```bash
   python -m venv venv
   ```

3. 激活虚拟环境：
   - Windows (PowerShell):
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   - Windows (CMD):
     ```cmd
     venv\Scripts\activate.bat
     ```
   - Linux/Mac:
     ```bash
     source venv/bin/activate
     ```

4. 安装后端依赖：
   ```bash
   pip install -r requirements.txt
   ```

### 2. 前端环境设置

1. 在项目根目录安装前端依赖：
   ```bash
   npm install
   ```

## 启动项目

### 方式一：同时启动前后端（推荐）

在项目根目录运行：
```bash
npm run dev
```

这将同时启动：
- 前端开发服务器（Vite）：http://localhost:21573
- 后端 API 服务器（FastAPI）：http://localhost:21574

### 方式二：分别启动

#### 启动后端

在项目根目录运行：
```bash
npm run server
```

或者手动启动：
```bash
cd backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --reload-dir app --port 21574 --log-level info
```

#### 启动前端

在项目根目录运行：
```bash
npm run vite
```

或者：
```bash
vite
```

## 项目结构

```
.
├── backend/          # 后端代码（FastAPI）
│   ├── app/         # 应用主代码
│   ├── venv/        # Python 虚拟环境
│   └── requirements.txt  # Python 依赖
├── frontend/        # 前端代码（React + TypeScript）
├── package.json     # 前端依赖和脚本
└── vite.config.ts   # Vite 配置
```

## 注意事项

1. **虚拟环境**：后端必须使用虚拟环境运行，确保依赖隔离。
2. **端口配置**：
   - 前端默认端口：21573
   - 后端默认端口：21574
3. **环境变量**：确保后端目录中有 `.env` 文件并配置了必要的环境变量。

## 开发说明

- 后端支持热重载（`--reload`），修改代码后会自动重启
- 前端使用 Vite，支持快速热模块替换（HMR）
- 使用 `concurrently` 同时运行前后端服务

## 故障排除

如果遇到问题：

1. **后端无法启动**：
   - 检查虚拟环境是否已激活
   - 确认所有依赖已正确安装
   - 检查端口 21574 是否被占用

2. **前端无法启动**：
   - 检查 Node.js 版本是否兼容
   - 删除 `node_modules` 和 `package-lock.json`，重新运行 `npm install`
   - 检查端口 21573 是否被占用

3. **依赖安装失败**：
   - 使用国内镜像源（如淘宝镜像）
   - 检查网络连接
   - 对于 Python 依赖，可以使用：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`
