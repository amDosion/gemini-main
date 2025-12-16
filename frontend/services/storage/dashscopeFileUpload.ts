/**
 * DashScope Temporary File Upload Service
 *
 * Uploads files to DashScope's temporary storage (48-hour validity)
 * Returns oss:// format URLs for use with DashScope APIs
 *
 * Documentation: https://help.aliyun.com/zh/model-studio/get-temporary-file-url
 */

export interface DashScopeUploadResult {
  success: boolean;
  ossUrl?: string; // oss:// format URL
  error?: string;
}

interface UploadPolicyResponse {
  data: {
    upload_host: string;
    upload_dir: string;
    oss_access_key_id: string;
    signature: string;
    policy: string;
    x_oss_object_acl: string;
    x_oss_forbid_overwrite: string;
  };
}

/**
 * Upload image to DashScope temporary storage
 * @param imageUrl - Image URL or base64 data URL to upload
 * @param apiKey - DashScope API key
 * @param model - Model name (must match the model used in subsequent API calls)
 * @returns Upload result with oss:// URL
 */
export async function uploadToDashScope(
  imageUrl: string,
  apiKey: string,
  model: string = 'wanx-v1'
): Promise<DashScopeUploadResult> {
  try {
    console.log('[DashScope Upload] Starting upload to temporary storage...');
    console.log('[DashScope Upload] Model:', model);

    // Step 1: Get upload policy
    console.log('[DashScope Upload] Step 1: Getting upload policy...');
    const policyUrl = `https://dashscope.aliyuncs.com/api/v1/uploads?action=getPolicy&model=${model}`;

    const policyResponse = await fetch(policyUrl, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
    });

    if (!policyResponse.ok) {
      const errorText = await policyResponse.text();
      console.error('[DashScope Upload] Failed to get policy:', errorText);
      return {
        success: false,
        error: `Failed to get upload policy: ${errorText}`,
      };
    }

    const policyData: UploadPolicyResponse = await policyResponse.json();
    console.log('[DashScope Upload] ✅ Got upload policy');

    // Step 2: Convert image to blob
    console.log('[DashScope Upload] Step 2: Converting image to blob...');
    let blob: Blob;
    let fileName: string;

    if (imageUrl.startsWith('data:')) {
      // Base64 data URL
      const base64Data = imageUrl.split(',')[1];
      const mimeType = imageUrl.match(/data:([^;]+);/)?.[1] || 'image/jpeg';
      const binaryData = atob(base64Data);
      const bytes = new Uint8Array(binaryData.length);
      for (let i = 0; i < binaryData.length; i++) {
        bytes[i] = binaryData.charCodeAt(i);
      }
      blob = new Blob([bytes], { type: mimeType });
      fileName = `expansion-${Date.now()}.${mimeType.split('/')[1]}`;
    } else {
      // URL - fetch it
      const imageResponse = await fetch(imageUrl);
      if (!imageResponse.ok) {
        return {
          success: false,
          error: `Failed to fetch image: ${imageResponse.statusText}`,
        };
      }
      blob = await imageResponse.blob();
      fileName = `expansion-${Date.now()}.jpg`;
    }

    console.log('[DashScope Upload] ✅ Image converted to blob:', blob.size, 'bytes');

    // Step 3: Upload to OSS
    console.log('[DashScope Upload] Step 3: Uploading to OSS...');
    const key = `${policyData.data.upload_dir}/${fileName}`;

    const formData = new FormData();
    formData.append('OSSAccessKeyId', policyData.data.oss_access_key_id);
    formData.append('Signature', policyData.data.signature);
    formData.append('policy', policyData.data.policy);
    formData.append('x-oss-object-acl', policyData.data.x_oss_object_acl);
    formData.append('x-oss-forbid-overwrite', policyData.data.x_oss_forbid_overwrite);
    formData.append('key', key);
    formData.append('success_action_status', '200');
    formData.append('file', blob, fileName);

    const uploadResponse = await fetch(policyData.data.upload_host, {
      method: 'POST',
      body: formData,
    });

    if (!uploadResponse.ok) {
      const errorText = await uploadResponse.text();
      console.error('[DashScope Upload] Upload failed:', errorText);
      return {
        success: false,
        error: `Upload failed: ${errorText}`,
      };
    }

    const ossUrl = `oss://${key}`;
    console.log('[DashScope Upload] ✅ Upload successful!');
    console.log('[DashScope Upload] OSS URL:', ossUrl);
    console.log('[DashScope Upload] ⏱️  Valid for 48 hours');

    return {
      success: true,
      ossUrl,
    };

  } catch (error) {
    console.error('[DashScope Upload] Error:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}
