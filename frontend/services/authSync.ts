/**
 * 多标签页认证状态同步
 */

// 创建广播频道
const authChannel = new BroadcastChannel('auth');

/**
 * 广播 token 刷新事件
 */
export function broadcastTokenRefresh(accessToken: string, refreshToken: string) {
  authChannel.postMessage({
    type: 'token_refreshed',
    accessToken,
    refreshToken,
    timestamp: Date.now()
  });
}

/**
 * 监听其他标签页的 token 刷新
 */
export function listenTokenRefresh(callback: (accessToken: string, refreshToken: string) => void) {
  authChannel.onmessage = (event) => {
    if (event.data.type === 'token_refreshed') {
      console.log('[AuthSync] Received token refresh from another tab');
      callback(event.data.accessToken, event.data.refreshToken);
    }
  };
}

/**
 * 广播登出事件
 */
export function broadcastLogout() {
  authChannel.postMessage({
    type: 'logout',
    timestamp: Date.now()
  });
}

/**
 * 监听其他标签页的登出
 */
export function listenLogout(callback: () => void) {
  authChannel.onmessage = (event) => {
    if (event.data.type === 'logout') {
      console.log('[AuthSync] Received logout from another tab');
      callback();
    }
  };
}
