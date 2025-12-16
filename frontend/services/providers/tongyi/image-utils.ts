
import { Attachment } from "../../../../types";
import { uploadDashScopeFile } from "./api";

// --- Helper: Process Reference Image ---
export async function ensureRemoteUrl(attachment: Attachment, apiKey: string, baseUrl?: string): Promise<string> {
    let imageUrl = attachment.url;
    
    // ✅ 优先使用 base64Data 字段（CONTINUITY LOGIC 预处理的数据）
    const base64Data = (attachment as any).base64Data;
    
    if (!imageUrl && !attachment.file && !base64Data) {
        throw new Error("Reference image required.");
    }

    // ✅ 如果 url 已经是 HTTP/HTTPS URL，直接使用
    // 注意：调用方必须在请求头中包含 X-DashScope-OssResourceResolve: enable
    // 这样 DashScope 才能访问外部 URL（包括用户的云存储 URL）
    if (imageUrl?.startsWith('http://') || imageUrl?.startsWith('https://')) {
        console.log('[ensureRemoteUrl] 已有远程 URL，直接使用:', imageUrl.substring(0, 60));
        return imageUrl;
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
