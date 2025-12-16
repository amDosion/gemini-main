/**
 * Lsky Pro V2 Image Upload Service
 *
 * API Documentation: https://docs.lsky.pro/
 */

export interface LskyConfig {
  domain: string;
  token: string;
}

export interface LskyUploadResult {
  success: boolean;
  url?: string;
  error?: string;
  fullData?: any;  // 完整的兰空响应数据
}

export interface LskyUploadOptions {
  onProgress?: (progress: number) => void;
}

/**
 * Upload image to Lsky Pro V2
 * @param file Image file to upload
 * @param config Lsky Pro configuration
 * @param options Upload options including progress callback
 * @returns Upload result with image URL
 */
export async function uploadToLsky(
  file: File,
  config: LskyConfig,
  options?: LskyUploadOptions
): Promise<LskyUploadResult> {
  try {
    console.log('[Lsky] Uploading image to Lsky Pro...');

    const formData = new FormData();
    // 🔥 使用文件的实际名称（已经被重命名过）
    formData.append('file', file, file.name);

    // Lsky Pro V2 API endpoint
    const uploadUrl = `${config.domain}/api/v1/upload`;

    // Ensure Authorization header has "Bearer " prefix
    const authToken = config.token.startsWith('Bearer ')
      ? config.token
      : `Bearer ${config.token}`;

    // 使用 XMLHttpRequest 以支持上传进度
    return new Promise((resolve) => {
      const xhr = new XMLHttpRequest();

      // 监听上传进度
      if (options?.onProgress) {
        xhr.upload.addEventListener('progress', (event) => {
          if (event.lengthComputable) {
            const progress = Math.round((event.loaded / event.total) * 100);
            options.onProgress!(progress);
          }
        });
      }

      // 监听完成
      xhr.addEventListener('load', async () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const result = JSON.parse(xhr.responseText);

            // Lsky Pro V2 response format:
            // {
            //   "status": true,
            //   "message": "上传成功",
            //   "data": {
            //     "key": "xxx",
            //     "name": "xxx.jpg",
            //     "pathname": "/xxx.jpg",
            //     "origin_name": "xxx.jpg",
            //     "size": 123456,
            //     "mimetype": "image/jpeg",
            //     "extension": "jpg",
            //     "md5": "xxx",
            //     "sha1": "xxx",
            //     "links": {
            //       "url": "https://xxx.com/xxx.jpg",
            //       "html": "<img src=\"https://xxx.com/xxx.jpg\" alt=\"xxx.jpg\" />",
            //       "bbcode": "[img]https://xxx.com/xxx.jpg[/img]",
            //       "markdown": "![xxx.jpg](https://xxx.com/xxx.jpg)",
            //       "markdown_with_link": "[![xxx.jpg](https://xxx.com/xxx.jpg)](https://xxx.com/xxx.jpg)",
            //       "thumbnail_url": "https://xxx.com/xxx.jpg"
            //     }
            //   }
            // }

            if (result.status && result.data?.links?.url) {
              const imageUrl = result.data.links.url;
              console.log('[Lsky] Upload successful:', imageUrl);

              // 🔥 打印完整的响应，查看是否有原始 OSS URL
              console.log('[Lsky] Full response data:', JSON.stringify(result.data, null, 2));

              resolve({
                success: true,
                url: imageUrl,
                fullData: result.data,  // 返回完整数据供调用者使用
              });
            } else {
              const errorMsg = result.message || 'Unknown error';
              console.error('[Lsky] Upload failed:', errorMsg);
              resolve({
                success: false,
                error: errorMsg,
              });
            }
          } catch (parseError) {
            console.error('[Lsky] Failed to parse response:', parseError);
            resolve({
              success: false,
              error: 'Failed to parse server response',
            });
          }
        } else {
          console.error('[Lsky] Upload failed:', xhr.status, xhr.responseText);
          resolve({
            success: false,
            error: `Upload failed: ${xhr.status} ${xhr.responseText}`,
          });
        }
      });

      // 监听错误
      xhr.addEventListener('error', () => {
        console.error('[Lsky] Upload error: Network error');
        resolve({
          success: false,
          error: 'Network error',
        });
      });

      // 监听中断
      xhr.addEventListener('abort', () => {
        console.error('[Lsky] Upload aborted');
        resolve({
          success: false,
          error: 'Upload aborted',
        });
      });

      // 发送请求
      xhr.open('POST', uploadUrl);
      xhr.setRequestHeader('Authorization', authToken);
      xhr.setRequestHeader('Accept', 'application/json');
      xhr.send(formData);
    });
  } catch (error) {
    console.error('[Lsky] Upload error:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}
