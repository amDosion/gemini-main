# 运行项目

启动开发服务器或运行项目。

## 开发模式

### 同时启动前后端
```bash
cd frontend
npm run dev
```
这会同时启动：
- 前端 Vite 开发服务器：http://localhost:21573
- 后端 FastAPI 服务器：http://localhost:21574

### 单独启动前端
```bash
cd frontend
npm run dev:frontend
```

### 单独启动后端
```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 21574 --reload
```

## 生产构建

### 前端构建
```bash
cd frontend
npm run build
```

### 预览构建结果
```bash
cd frontend
npm run preview
```

## 运行测试

### 前端测试
```bash
cd frontend
npm run test
```

### 后端测试
```bash
cd backend
pytest
```

## 常见问题

### 端口被占用
```bash
# Windows
netstat -ano | findstr :21574
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :21574
kill -9 <PID>
```

### 依赖问题
```bash
# 前端
cd frontend
rm -rf node_modules
npm install

# 后端
cd backend
pip install -r requirements.txt
```

## 使用示例

```
/run 启动开发服务器
```

```
/run 只启动后端
```

```
/run 构建生产版本
```
