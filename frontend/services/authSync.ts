/**
 * 多标签页认证状态同步
 */

// 创建广播频道
const authChannel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('auth') : null;
const tokenRefreshListeners = new Set<() => void>();
const logoutListeners = new Set<() => void>();

authChannel?.addEventListener('message', (event) => {
  const payload = event.data || {};

  if (payload.type === 'token_refreshed') {
    tokenRefreshListeners.forEach((listener) => {
      listener();
    });
    return;
  }

  if (payload.type === 'logout') {
    logoutListeners.forEach((listener) => {
      listener();
    });
  }
});

/**
 * 广播 token 刷新事件
 */
export function broadcastTokenRefresh() {
  authChannel?.postMessage({
    type: 'token_refreshed',
    timestamp: Date.now()
  });
}

/**
 * 监听其他标签页的 token 刷新
 */
export function listenTokenRefresh(callback: () => void) {
  tokenRefreshListeners.add(callback);

  return () => {
    tokenRefreshListeners.delete(callback);
  };
}

/**
 * 广播登出事件
 */
export function broadcastLogout() {
  authChannel?.postMessage({
    type: 'logout',
    timestamp: Date.now()
  });
}

/**
 * 监听其他标签页的登出
 */
export function listenLogout(callback: () => void) {
  logoutListeners.add(callback);

  return () => {
    logoutListeners.delete(callback);
  };
}
