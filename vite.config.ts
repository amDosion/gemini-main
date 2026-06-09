import { defineConfig } from 'vitest/config';
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

// Dev-only: inject the standalone React DevTools agent (`npx react-devtools`,
// listens on ws://localhost:8097) at the top of <head> so it loads before React.
// `apply: 'serve'` keeps it out of the production build entirely.
function reactDevtoolsPlugin() {
  return {
    name: 'react-devtools-standalone',
    apply: 'serve' as const,
    transformIndexHtml(html: string) {
      return html.replace('<head>', '<head>\n    <script src="http://localhost:8097"></script>');
    },
  };
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [reactDevtoolsPlugin(), react()],
  // T3: a coverage gate now exists and is enforced. Thresholds are a conservative
  // floor below the measured baseline — ratchet them upward as coverage improves.
  test: {
    coverage: {
      provider: 'v8',
      reporter: ['text-summary', 'text', 'html'],
      reportsDirectory: './coverage',
      include: ['frontend/**/*.{ts,tsx}'],
      exclude: [
        'frontend/**/*.test.{ts,tsx}',
        'frontend/**/*.d.ts',
        'frontend/**/__mocks__/**',
        'frontend/**/types/**',
        'frontend/**/*.stories.{ts,tsx}',
      ],
      // Measured baseline 2026-06-04: stmts 60.1 / branch 64.5 / func 60.3 / lines 60.1.
      // Floor set ~5pts below baseline to absorb minor fluctuation; ratchet upward.
      thresholds: {
        statements: 55,
        branches: 58,
        functions: 55,
        lines: 55,
      },
    },
  },
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
      // 协议：默认 wss，保持反向代理(HTTPS 终结)部署兼容；本地纯 HTTP 直连开发用
      // VITE_HMR_PROTOCOL=ws 覆盖（见 scripts/start_all.ps1）。否则浏览器会去连不存在的
      // wss 端口导致 HMR 握手失败（页面功能不受影响，仅热更新失效）。
      protocol: process.env.VITE_HMR_PROTOCOL ?? 'wss',
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
  optimizeDeps: {
    include: ['react', 'react-dom', 'lucide-react'],
  },
});
