import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const proxyDebugEnabled = process.env.VITE_PROXY_DEBUG === '1';

const CHUNK_GROUPS: Record<string, Set<string>> = {
  'react-vendor': new Set(['react', 'react-dom', 'scheduler']),
  'router-vendor': new Set(['react-router', 'react-router-dom']),
  'ui-vendor': new Set(['lucide-react', '@heroicons/react']),
  'flow-vendor': new Set([
    'reactflow',
    '@xyflow/react',
    '@reactflow/core',
    'd3-selection',
    'd3-transition',
    'd3-zoom',
    'd3-drag',
    'd3-color',
    'd3-dispatch',
    'd3-ease',
    'd3-interpolate',
    'd3-timer',
  ]),
  'markdown-vendor': new Set([
    'react-markdown',
    'rehype-raw',
    'react-syntax-highlighter',
    'refractor',
    'parse5',
    'unified',
    'micromark',
    'micromark-core-commonmark',
    'mdast-util-to-hast',
    'mdast-util-from-markdown',
    'hast-util-raw',
    'hast-util-to-jsx-runtime',
    'parse-entities',
    'property-information',
    'entities',
    'vfile',
  ]),
  'genai-vendor': new Set(['@google/genai']),
  'sanitize-vendor': new Set(['dompurify']),
};

function resolvePackageName(id: string): string | null {
  const marker = '/node_modules/';
  const markerIndex = id.lastIndexOf(marker);
  if (markerIndex === -1) {
    return null;
  }
  const packagePath = id.slice(markerIndex + marker.length);
  const parts = packagePath.split('/');
  if (parts.length === 0 || !parts[0]) {
    return null;
  }
  if (parts[0].startsWith('@') && parts.length > 1) {
    return `${parts[0]}/${parts[1]}`;
  }
  return parts[0];
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // 监听所有 IPv4 网络接口（包括 localhost 和局域网 IP）
    port: 21573,
    strictPort: false, // 如果端口被占用，自动尝试下一个可用端口
    // 允许的域名：可通过 VITE_ALLOWED_HOSTS（逗号分隔）覆盖，避免把生产域名硬编码到提交里
    // 安全：过滤掉裸 "*" 字面值——Vite 会把 ['*'] 当通配匹配所有 Host，导致 DNS rebinding 攻击面
    allowedHosts: process.env.VITE_ALLOWED_HOSTS
      ? process.env.VITE_ALLOWED_HOSTS.split(',')
          .map((s) => s.trim())
          .filter((h) => h && h !== '*')
      : ['gemini.lspon.com', 'geminiai.lspon.com', 'gemini.dicry.cn'],
    open: '/login', // 自动打开浏览器到登录页面
    cors: true, // 启用 CORS
    hmr: {
      protocol: 'wss', // 使用 WebSocket 协议
      // 不指定 host，让 HMR 自动适配当前访问地址（支持 localhost、127.0.0.1 和局域网 IP）
      port: 21573,
      // 反向代理外网端口；可通过 VITE_HMR_CLIENT_PORT 覆盖，默认 18443 保持现有部署兼容
      // parseInt 在空串/非数字输入时返回 NaN，|| 0 fallback 到默认值，避免 Vite 接收 NaN
      clientPort: parseInt(process.env.VITE_HMR_CLIENT_PORT ?? '', 10) || 18443,
      timeout: 30000, // 30 秒超时
      overlay: true, // 在浏览器中显示错误覆盖层
    },
    proxy: {
      // Deep Research SSE 流可能持续数分钟，单独配置长连接超时避免被开发代理中断。
      '/api/research/stream': {
        target: 'http://localhost:21574',
        changeOrigin: true,
        secure: false,
        ws: true,
        timeout: 0,
        proxyTimeout: 0,
      },
      '/api': {
        target: 'http://localhost:21574',
        changeOrigin: true,
        secure: false,
        ws: true, // 代理 WebSocket
        timeout: 0,
        proxyTimeout: 0,
        // 添加代理日志，方便调试
        configure: (proxy, _options) => {
          if (!proxyDebugEnabled) {
            return;
          }
          proxy.on('error', (err, _req, _res) => {
            console.log('❌ 代理错误:', err.message);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('→ 发送请求:', req.method, req.url);
          });
          proxy.on('proxyRes', (proxyRes, req, _res) => {
            console.log('← 收到响应:', proxyRes.statusCode, req.url);
          });
        },
      },
      '/health': {
        target: 'http://localhost:21574',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  // 注意：不再通过 define 把 API key 编译进前端 bundle（之前的 process.env.API_KEY 注入会
  // 让 key 以明文形式出现在 production JS 中，任何拿到 bundle 的人都可提取）。
  // Provider API key 现在统一通过 profile UI 配置，由后端加密存储与中转使用。
  // 优化构建配置
  build: {
    sourcemap: true, // 生成 source map，方便调试
    rollupOptions: {
      output: {
        // 手动分包，优化首屏加载与缓存命中。
        // 只固定边界清晰的依赖组；未显式分组的包交给 Rollup 自动归属，
        // 避免把子依赖强塞进 vendor 后形成跨 chunk 循环依赖。
        manualChunks: (id: string) => {
          const pkg = resolvePackageName(id);
          if (!pkg) {
            return undefined;
          }

          for (const [chunkName, packages] of Object.entries(CHUNK_GROUPS)) {
            if (packages.has(pkg)) {
              return chunkName;
            }
          }

          return undefined;
        },
      },
    },
    // 提高 chunk 大小警告阈值（默认 500kB，使用 Vite 默认值以警示大 chunk）
    chunkSizeWarningLimit: 500,
  },
  // 优化依赖预构建
  // markdown 相关依赖虽然是动态 import (React.lazy)，仍需显式 include 以保证 dev 服务启动时
  // 同步完成 pre-bundle。否则首次 lazy load 触发懒优化，chunk 哈希在重新发现期间可能失效，
  // 导致 react-syntax-highlighter 等子 chunk 出现 ERR_FAILED。
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'lucide-react',
      'react-markdown',
      'rehype-raw',
      'rehype-sanitize',
      'react-syntax-highlighter',
      'react-syntax-highlighter/dist/esm/styles/prism',
      'react-syntax-highlighter/dist/esm/languages/prism/bash',
      'react-syntax-highlighter/dist/esm/languages/prism/css',
      'react-syntax-highlighter/dist/esm/languages/prism/javascript',
      'react-syntax-highlighter/dist/esm/languages/prism/json',
      'react-syntax-highlighter/dist/esm/languages/prism/jsx',
      'react-syntax-highlighter/dist/esm/languages/prism/markdown',
      'react-syntax-highlighter/dist/esm/languages/prism/markup',
      'react-syntax-highlighter/dist/esm/languages/prism/python',
      'react-syntax-highlighter/dist/esm/languages/prism/sql',
      'react-syntax-highlighter/dist/esm/languages/prism/tsx',
      'react-syntax-highlighter/dist/esm/languages/prism/typescript',
      'react-syntax-highlighter/dist/esm/languages/prism/yaml',
    ],
  },
});
