import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

const proxyDebugEnabled = process.env.VITE_PROXY_DEBUG === '1';
const DEFAULT_ALLOWED_HOSTS = ['gemini.lspon.com', 'geminiai.lspon.com', 'gemini.dicry.cn'];
const DEFAULT_DEV_CORS_ORIGINS = ['http://localhost:21573', 'http://127.0.0.1:21573'];
const DEFAULT_DEV_PORT = 21573;

export function shouldEmitBuildSourcemap(value = process.env.VITE_BUILD_SOURCEMAP): boolean {
  return value === '1';
}

function splitCsv(value: string | undefined): string[] {
  return (value ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

function isHttpOrigin(value: string): boolean {
  try {
    const url = new URL(value);
    return (url.protocol === 'http:' || url.protocol === 'https:') && url.origin === value.replace(/\/$/, '');
  } catch {
    return false;
  }
}

export function resolveAllowedHosts(value = process.env.VITE_ALLOWED_HOSTS): string[] {
  const hosts = splitCsv(value).filter((host) => host !== '*');
  return hosts.length > 0 ? hosts : DEFAULT_ALLOWED_HOSTS;
}

export function resolveDevCorsOrigins(value = process.env.VITE_DEV_CORS_ORIGINS): string[] {
  const origins = splitCsv(value).filter((origin) => origin !== '*' && isHttpOrigin(origin));
  return origins.length > 0 ? origins : DEFAULT_DEV_CORS_ORIGINS;
}

function resolvePositivePort(value: string | undefined, fallback: number): number {
  const parsed = Number.parseInt(value ?? '', 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

const CHUNK_GROUPS: Record<string, Set<string>> = {
  'react-vendor': new Set(['react', 'react-dom', 'scheduler']),
  'router-vendor': new Set(['react-router', 'react-router-dom']),
  'ui-vendor': new Set(['lucide-react', '@heroicons/react']),
  'syntax-vendor': new Set(['react-syntax-highlighter', 'refractor']),
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

function isAntDesignPackage(pkg: string): boolean {
  return pkg === 'antd' || pkg.startsWith('@ant-design/') || pkg.startsWith('@rc-component/') || pkg.startsWith('rc-');
}

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

export function resolveManualChunk(id: string): string | undefined {
  const pkg = resolvePackageName(id);
  if (!pkg) {
    return undefined;
  }

  if (isAntDesignPackage(pkg)) {
    return 'antd-vendor';
  }

  for (const [chunkName, packages] of Object.entries(CHUNK_GROUPS)) {
    if (packages.has(pkg)) {
      return chunkName;
    }
  }

  return undefined;
}

// Dev-only: inject the standalone React DevTools agent (`npx react-devtools`,
// listens on ws://localhost:8097) at the top of <head> so it loads before React.
// `apply: 'serve'` keeps it out of the production build entirely.
function reactDevtoolsPlugin(enabled = process.env.VITE_REACT_DEVTOOLS === '1') {
  return {
    name: 'react-devtools-standalone',
    apply: 'serve' as const,
    transformIndexHtml(html: string) {
      if (!enabled) {
        return html;
      }
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
    allowedHosts: resolveAllowedHosts(),
    open: '/login', // 自动打开浏览器到登录页面
    // Avoid Vite's `cors: true` wildcard in shared/reverse-proxied dev deployments.
    cors: {
      origin: resolveDevCorsOrigins(),
      credentials: true,
      methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
      allowedHeaders: ['Content-Type', 'X-CSRF-Token', 'Authorization', 'X-Request-ID'],
    },
    hmr: {
      // 本地 http://localhost:21573 默认使用 ws。反向代理/HTTPS 终结部署可通过
      // VITE_HMR_PROTOCOL=wss 与 VITE_HMR_CLIENT_PORT=18443 显式覆盖。
      protocol: process.env.VITE_HMR_PROTOCOL ?? 'ws',
      // 不指定 host，让 HMR 自动适配当前访问地址（支持 localhost、127.0.0.1 和局域网 IP）
      port: DEFAULT_DEV_PORT,
      clientPort: resolvePositivePort(process.env.VITE_HMR_CLIENT_PORT, DEFAULT_DEV_PORT),
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
    // Production source maps expose source structure and increase asset size.
    // Enable only for explicit deployment debugging.
    sourcemap: shouldEmitBuildSourcemap(),
    rollupOptions: {
      output: {
        // 手动分包，优化首屏加载与缓存命中。
        // 只固定边界清晰的依赖组；未显式分组的包交给 Rollup 自动归属，
        // 避免把子依赖强塞进 vendor 后形成跨 chunk 循环依赖。
        manualChunks: resolveManualChunk,
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
