
import { Attachment } from "../../../types/types";
import { uploadDashScopeFile } from "./api";

// --- Helper: Process Reference Image ---
export async function ensureRemoteUrl(attachment: Attachment, apiKey: string, baseUrl?: string): Promise<string> {
    let imageUrl = attachment.url;
    
    // ✅ 优先使用 base64Data 字段（CONTINUITY LOGIC 预处理的数据）
    const base64Data = (attachment as any).base64Data;
    
    if (!imageUrl && !attachment.file && !base64Data) {
        throw new Error("Reference image required.");
    }

    // ✅ 如果 url 已经是 HTTP/HTTPS URL
    // 注意：DashScope 访问外部 URL 可能会超时，因此我们需要先下载再上传到 OSS
    if (imageUrl?.startsWith('http://') || imageUrl?.startsWith('https://')) {
        console.log('[ensureRemoteUrl] 检测到远程 URL，需要下载并上传到 DashScope OSS');
        console.log('[ensureRemoteUrl] 原始 URL:', imageUrl.substring(0, 60));
        
        try {
            // 通过后端代理下载图片（避免 CORS 问题）
            const proxyUrl = `/api/storage/download?url=${encodeURIComponent(imageUrl)}`;
            const response = await fetch(proxyUrl);
            
            if (!response.ok) {
                throw new Error(`下载图片失败: ${response.status} ${response.statusText}`);
            }
            
            const blob = await response.blob();
            const fileName = attachment.name || imageUrl.split('/').pop() || 'image.png';
            const fileToUpload = new File([blob], fileName, { type: blob.type || 'image/png' });
            
            console.log('[ensureRemoteUrl] 下载完成，开始上传到 DashScope OSS');
            const ossUrl = await uploadDashScopeFile(fileToUpload, apiKey, baseUrl);
            console.log('[ensureRemoteUrl] 上传完成，OSS URL:', ossUrl.substring(0, 60));
            
            return ossUrl;
        } catch (error: any) {
            console.error('[ensureRemoteUrl] 下载或上传失败:', error);
            // 如果下载失败，尝试直接使用原始 URL（作为后备方案）
            console.warn('[ensureRemoteUrl] 回退到直接使用原始 URL');
            return imageUrl;
        }
    }

    // 需要上传到 DashScope OSS
    let fileToUpload = attachment.file;
    
    // ✅ 优先使用 base64Data 转换为 File
    if (!fileToUpload && base64Data?.startsWith('data:')) {
        console.log('[ensureRemoteUrl] 使用 base64Data 转换为 File');
        const res = await fetch(base64Data);
        const blob = await res.blob();
        fileToUpload = new File([blob], attachment.name || "temp_image.png", { type: blob.type });
    }
    
    // 其次使用 url（blob/data URI）
    if (!fileToUpload && imageUrl && (imageUrl.startsWith('blob:') || imageUrl.startsWith('data:'))) {
        console.log('[ensureRemoteUrl] 使用 url 转换为 File');
        const res = await fetch(imageUrl);
        const blob = await res.blob();
        fileToUpload = new File([blob], attachment.name || "temp_image.png", { type: blob.type });
    }
    
    if (fileToUpload) {
        console.log('[ensureRemoteUrl] 上传文件到 DashScope OSS:', fileToUpload.name);
        imageUrl = await uploadDashScopeFile(fileToUpload, apiKey, baseUrl);
        console.log('[ensureRemoteUrl] 上传完成:', imageUrl?.substring(0, 60));
    }
    
    if (!imageUrl) throw new Error("Failed to upload image to DashScope OSS.");
    return imageUrl;
}
