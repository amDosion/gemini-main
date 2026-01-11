// 定义错误处理函数返回结果的接口
export interface ErrorHandlerResult {
  code: string; // 错误代码，用于程序化识别
  message: string; // 用户友好的中文错误消息
  suggestions: string[]; // 针对该错误的可行建议
  details?: any; // 原始错误对象，用于调试
}

/**
 * 处理和分类应用程序中发生的各种错误。
 * @param error - 捕获到的原始错误对象，可以是任何类型。
 * @returns {ErrorHandlerResult} - 一个结构化的错误对象，包含代码、消息、建议和详情。
 */
export function handleError(error: any): ErrorHandlerResult {
  // 预设一个通用的未知错误结构，以防无法匹配任何已知错误类型
  const unknownError: ErrorHandlerResult = {
    code: 'UNKNOWN',
    message: '发生未知错误',
    suggestions: [
      '请稍后重试。',
      '如果问题持续存在，请联系技术支持。',
      '检查浏览器的开发者控制台获取更多技术细节。',
    ],
    details: error,
  };

  // 检查 error 对象是否存在，如果不存在则直接返回未知错误
  if (!error) {
    return unknownError;
  }

  // --- 网络错误处理 ---
  // 通常由 axios 或 fetch 在网络层面失败时抛出 (例如，DNS问题、CORS、无网络连接)
  if (error.code === 'NETWORK_ERROR' || error.message === 'Network Error') {
    return {
      code: 'NETWORK_ERROR',
      message: '网络连接失败',
      suggestions: [
        '请检查您的网络连接是否正常。',
        '如果您在使用代理或VPN，请尝试禁用它们后重试。',
        '刷新页面或稍后再试。',
      ],
      details: error,
    };
  }
  
  // --- Axios 超时错误处理 ---
  if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
    return {
      code: 'TIMEOUT',
      message: '请求超时',
      suggestions: [
        '网络状况可能不佳，请稍后重试。',
        '尝试简化您的请求或提示词。',
        '检查您的网络设置。',
      ],
      details: error,
    };
  }

  // --- HTTP 响应错误处理 ---
  // 如果错误对象包含 response 属性，说明是来自服务器的HTTP响应错误
  if (error.response) {
    const { status, data } = error.response;
    const details = data || error.message; // 保存响应数据或消息作为详情

    switch (status) {
      // 状态码 400: 无效参数
      case 400:
        return {
          code: 'INVALID_ARGUMENT',
          message: '请求参数无效',
          suggestions: [
            '请检查您输入的提示词是否符合格式要求。',
            '确认所有必需的参数都已正确提供。',
            '避免使用特殊或不支持的字符。',
          ],
          details: details,
        };

      // 状态码 401: 未认证
      case 401:
        return {
          code: 'UNAUTHENTICATED',
          message: '身份验证失败',
          suggestions: [
            '请检查您的 API 密钥是否正确并已在设置中配置。',
            '确保您的账户有权访问此服务。',
            '如果密钥最近已更改，请更新配置。',
          ],
          details: details,
        };

      // 状态码 429: 资源耗尽 (例如，API速率限制或配额超出)
      case 429:
        return {
          code: 'RESOURCE_EXHAUSTED',
          message: '请求过于频繁或已超出配额',
          suggestions: [
            '请等待片刻后再试。',
            '检查您的 API 使用情况和账户配额。',
            '考虑升级您的服务计划以获取更高的限制。',
          ],
          details: details,
        };

      // 状态码 503: 服务不可用
      case 503:
        return {
          code: 'SERVICE_UNAVAILABLE',
          message: '服务暂时不可用',
          suggestions: [
            '服务可能正在维护或负载过高，请稍后重试。',
            '访问官方服务状态页面以获取最新信息。',
          ],
          details: details,
        };
      
      // 其他 HTTP 错误状态码
      default:
        return {
          code: `HTTP_${status}`,
          message: `服务器返回错误 (代码: ${status})`,
          suggestions: [
            '请稍后重试。',
            '如果问题持续，这可能是一个服务端问题，请联系技术支持。',
          ],
          details: details,
        };
    }
  }

  // 如果以上所有检查都不匹配，则返回通用未知错误
  return unknownError;
}