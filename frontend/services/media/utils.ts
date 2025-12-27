
import { Attachment } from "../../types/types";

// Helper to read File to Base64
export async function fileToBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

// Helper to convert Blob to Base64 Data URL
async function blobToBase64(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}

/**
 * 处理参考图片的结果类型
 */
export interface ProcessedImage {
    mimeType: string;
    imageBytes: string;      // Base64 编码的图片数据（不含前缀）
    base64Url: string;       // 完整的 Base64 Data URL
    googleFileUri?: string;  // Google Files API URI（如果有）
}

/**
 * Helper to process reference images for various APIs
 * 
 * 返回标准对象: { mimeType, imageBytes, base64Url, googleFileUri }
 * 
 * 优先级：
 * 1. googleFileUri - 如果附件已上传到 Google Files API
 * 2. base64Data - CONTINUITY LOGIC 预处理的数据
 * 3. url (Base64) - Base64 Data URL
 * 4. file - 原始 File 对象
 * 5. url (HTTP) - 远程 URL
 */
export async function processReferenceImage(att: Attachment): Promise<ProcessedImage> {
    let mimeType = att.mimeType || 'image/png';
    let imageBytes = '';
    let base64Url = '';

    // ✅ 优先检查 Google Files API URI（最高效）
    if (att.googleFileUri) {
        // 检查是否过期
        const isExpired = att.googleFileExpiry && Date.now() > att.googleFileExpiry;
        if (!isExpired) {
            console.log('[processReferenceImage] ✅ 使用 Google Files API URI');
            return { 
                mimeType, 
                imageBytes: '', 
                base64Url: '', 
                googleFileUri: att.googleFileUri 
            };
        } else {
            console.log('[processReferenceImage] ⚠️ Google Files API URI 已过期，回退到 Base64');
        }
    }

    // ✅ 优先使用 base64Data 字段（CONTINUITY LOGIC 预处理的数据）
    const base64Data = (att as any).base64Data;
    if (base64Data && base64Data.startsWith('data:')) {
        const match = base64Data.match(/^data:(.*?);base64,(.*)$/);
        if (match) {
            mimeType = match[1];
            imageBytes = match[2];
            base64Url = base64Data;
            return { mimeType, imageBytes, base64Url };
        }
    }

    if (att.url && att.url.startsWith('data:')) {
        const match = att.url.match(/^data:(.*?);base64,(.*)$/);
        if (match) {
            mimeType = match[1];
            imageBytes = match[2];
            base64Url = att.url;
        }
    } else if (att.file) {
        const base64Str = await fileToBase64(att.file);
        base64Url = base64Str;
        const match = base64Str.match(/^data:(.*?);base64,(.*)$/);
        if (match) {
            mimeType = match[1];
            imageBytes = match[2];
        }
    } else if (att.url && att.url.startsWith('http')) {
        // HTTP URL - 通过后端代理下载（解决 CORS）
        console.log('[processReferenceImage] 从 HTTP URL 下载:', att.url.substring(0, 60));
        try {
            const proxyUrl = `/api/storage/download?url=${encodeURIComponent(att.url)}`;
            const response = await fetch(proxyUrl);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const blob = await response.blob();
            const base64Str = await blobToBase64(blob);
            base64Url = base64Str;
            const match = base64Str.match(/^data:(.*?);base64,(.*)$/);
            if (match) {
                mimeType = match[1];
                imageBytes = match[2];
                console.log('[processReferenceImage] ✅ HTTP URL 下载成功');
            }
        } catch (e) {
            console.error('[processReferenceImage] ❌ HTTP URL 下载失败:', e);
            // 返回空数据，让调用方处理
            base64Url = att.url;
        }
    } else if (att.url) {
        // 其他 URL 类型（如 blob:）
        base64Url = att.url;
    }
    
    return { mimeType, imageBytes, base64Url };
}

// Helper to convert PCM to WAV
export function pcmToWav(pcmData: Uint8Array, sampleRate: number = 24000, numChannels: number = 1): Blob {
    const buffer = pcmData.buffer;
    const byteLength = buffer.byteLength;
    const header = new ArrayBuffer(44);
    const view = new DataView(header);

    const writeString = (view: DataView, offset: number, string: string) => {
        for (let i = 0; i < string.length; i++) {
            view.setUint8(offset + i, string.charCodeAt(i));
        }
    };

    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + byteLength, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * numChannels * 2, true);
    view.setUint16(32, numChannels * 2, true);
    view.setUint16(34, 16, true);
    writeString(view, 36, 'data');
    view.setUint32(40, byteLength, true);

    // ✅ 创建新的 ArrayBuffer 副本以解决 TypeScript 类型兼容性问题
    const pcmArrayBuffer = new Uint8Array(pcmData).buffer as ArrayBuffer;
    return new Blob([header, pcmArrayBuffer], { type: 'audio/wav' });
}
