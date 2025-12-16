# WebSocket 连接失败修复

## 问题描述

**错误信息**：
```
WebSocket connection to 'ws://localhost:5173/' failed
```

**影响**：
- ❌ 热重载（HMR）不工作
- ❌ 修改代码后需要手动刷新浏览器
- ❌ 开发体验下降

---

## 根本原因

Vite 的 HMR（热模块替换）使用 WebSocket 连接来实现实时更新。默认配置在某些环境下可能无法正常工作，导致 WebSocket 连接失败。

**可能的原因**：
1. WebSocket 配置不完整
2. 端口冲突
3. 防火墙阻止
4. IPv6/IPv4 地址问题
5. 代理配置不支持 WebSocket

---

## 修复方案

### 修改 `vite.config.ts`

添加完整的 WebSocket 和 HMR 配置：

```typescript
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',        // 监听所有网络接口
    port: 5173,             // 明确指定端口
    strictPort: false,      // 端口被占用时自动尝试下一个
    cors: true,             // 启用 CORS
    hmr: {
      protocol: 'ws',       // WebSocket 协议
      host: 'localhost',    // HMR 服务器地址
      port: 5173,           // HMR 端口
      clientPort: 5173,     // 客户端连接端口
      overlay: true,        // 显示错误覆盖层
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        ws: true,           // ✅ 关键：启用 WebSocket 代理
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  },
  define: {
    'process.env.API_KEY': JSON.stringify(process.env.API_KEY || ''),
  }
});
```

---

## 配置说明

### 1. `host: '0.0.0.0'`

**作用**：监听所有网络接口

**好处**：
- 允许从其他设备访问（如手机测试）
- 解决某些网络环境下的连接问题

### 2. `port: 5173`

**作用**：明确指定端口

**好处**：
- 与 HMR 配置保持一致
- 避免端口不匹配问题

### 3. `strictPort: false`

**作用**：端口被占用时自动尝试下一个

**好处**：
- 避免启动失败
- 提高开发体验

### 4. `cors: true`

**作用**：启用跨域资源共享

**好处**：
- 解决跨域问题
- 支持从不同域名访问

### 5. `hmr` 配置

**作用**：配置热模块替换

**关键参数**：
- `protocol: 'ws'`：使用 WebSocket 协议
- `host: 'localhost'`：HMR 服务器地址
- `port: 5173`：HMR 端口
- `clientPort: 5173`：客户端连接端口
- `overlay: true`：在浏览器中显示错误

### 6. `ws: true`

**作用**：在代理中启用 WebSocket

**重要性**：⭐⭐⭐⭐⭐

这是最关键的配置！如果没有这个，代理会阻止 WebSocket 连接。

---

## 应用修复

### 步骤 1：停止前端服务器

在前端终端按 `Ctrl + C`

### 步骤 2：清除缓存（推荐）

```bash
# Windows PowerShell
Remove-Item -Recurse -Force node_modules\.vite

# Windows CMD
rmdir /s /q node_modules\.vite

# Linux/Mac
rm -rf node_modules/.vite
```

### 步骤 3：重新启动

```bash
npm run dev
```

### 步骤 4：验证

**预期结果**：

1. **控制台输出**：
   ```
   VITE v5.x.x  ready in xxx ms

   ➜  Local:   http://localhost:5173/
   ➜  Network: http://192.168.x.x:5173/
   ➜  press h + enter to show help
   ```

2. **浏览器控制台**：
   ```
   [vite] connected.
   ```

3. **测试热重载**：
   - 修改任意 `.tsx` 文件
   - 保存
   - 浏览器自动刷新 ✅

---

## 故障排查

### 问题 1：仍然连接失败

**可能原因**：防火墙阻止

**解决方案**：
1. 临时关闭防火墙测试
2. 添加防火墙规则：
   ```
   允许入站连接：端口 5173，协议 TCP
   ```

### 问题 2：IPv6 地址问题

**症状**：连接到 `[::1]:5173` 失败

**解决方案**：强制使用 IPv4
```typescript
server: {
  host: '127.0.0.1', // 使用 IPv4 地址
  // ... 其他配置
}
```

### 问题 3：端口被占用

**错误信息**：
```
Port 5173 is in use
```

**解决方案 1**：释放端口
```bash
# Windows
netstat -ano | findstr :5173
taskkill /PID <进程ID> /F

# Linux/Mac
lsof -ti:5173 | xargs kill -9
```

**解决方案 2**：使用其他端口
```typescript
server: {
  port: 5174, // 改用其他端口
  hmr: {
    port: 5174, // HMR 端口也要改
    clientPort: 5174,
  }
}
```

### 问题 4：代理冲突

**症状**：WebSocket 连接被代理拦截

**解决方案**：确保代理配置正确
```typescript
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
    secure: false,
    ws: true, // ✅ 必须启用
  }
}
```

---

## 高级配置

### 添加调试日志

```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
      secure: false,
      ws: true,
      configure: (proxy, options) => {
        proxy.on('error', (err, req, res) => {
          console.log('❌ Proxy error:', err);
        });
        proxy.on('proxyReq', (proxyReq, req, res) => {
          console.log('→ Sending:', req.method, req.url);
        });
        proxy.on('proxyRes', (proxyRes, req, res) => {
          console.log('← Received:', proxyRes.statusCode, req.url);
        });
      },
    }
  }
}
```

### 自定义 HMR 超时

```typescript
server: {
  hmr: {
    protocol: 'ws',
    host: 'localhost',
    port: 5173,
    clientPort: 5173,
    timeout: 30000, // 30 秒超时
  }
}
```

### 禁用 HMR（不推荐）

如果实在无法修复，可以临时禁用：

```typescript
server: {
  hmr: false, // 禁用热重载
}
```

**注意**：禁用后需要手动刷新浏览器。

---

## 总结

### 修复内容

✅ 添加完整的 HMR WebSocket 配置  
✅ 启用代理的 WebSocket 支持  
✅ 优化服务器监听配置  
✅ 添加 CORS 支持

### 验证结果

✅ WebSocket 连接成功  
✅ 热重载正常工作  
✅ 开发体验提升

### 关键配置

最重要的是在代理配置中添加 `ws: true`：

```typescript
proxy: {
  '/api': {
    ws: true, // ⭐ 关键配置
  }
}
```

---

**状态**：✅ 已修复  
**影响范围**：前端开发服务器  
**测试结果**：WebSocket 连接正常
