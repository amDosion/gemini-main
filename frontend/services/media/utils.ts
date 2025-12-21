
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

// Helper to process reference images for various APIs
// Returns standard object: { mimeType, imageBytes, base64Url }
export async function processReferenceImage(att: Attachment): Promise<{ mimeType: string; imageBytes: string; base64Url: string }> {
    let mimeType = 'image/png';
    let imageBytes = '';
    let base64Url = '';

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
    } else if (att.url) {
        // Remote URL - try to fetch it to get bytes if needed (CORS permitting)
        // Or just return the URL if the provider supports URLs
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
