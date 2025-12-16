
import { Attachment } from "../../../../types";
import { uploadDashScopeFile } from "./api";

// --- Helper: Process Reference Image ---
export async function ensureRemoteUrl(attachment: Attachment, apiKey: string, baseUrl?: string): Promise<string> {
    let imageUrl = attachment.url;
    if (!imageUrl && !attachment.file) throw new Error("Reference image required.");

    // If it's a blob/data URI, we MUST upload it to DashScope first
    if (imageUrl?.startsWith('blob:') || imageUrl?.startsWith('data:') || attachment.file) {
        let fileToUpload = attachment.file;
        if (!fileToUpload && imageUrl) {
             const res = await fetch(imageUrl);
             const blob = await res.blob();
             fileToUpload = new File([blob], "temp_image.png", { type: blob.type });
        }
        if (fileToUpload) {
            imageUrl = await uploadDashScopeFile(fileToUpload, apiKey, baseUrl);
        }
    }
    if (!imageUrl) throw new Error("Failed to upload image to DashScope OSS.");
    return imageUrl;
}
