import { db } from '../../../services/db';
import {
  triggerBrowserDownload
} from '../../../services/downloadService';
import type {
  StorageBatchDeleteRequestItem,
  StorageBrowseItem,
  StorageBrowseResponse,
  StorageDownloadPrepareResponse,
  StorageDownloadRequestItem,
  StorageFileMetadataItem
} from '../../../types/storage';

const DEFAULT_BROWSE_LIMIT = 200;
const DEFAULT_UPLOAD_TIMEOUT_MS = 180000;

const BROWSE_ERROR_MESSAGE = 'Failed to browse cloud storage';
const BATCH_DELETE_ERROR_MESSAGE = 'Batch delete failed';
const UPLOAD_FAILED_MESSAGE = 'upload failed';

function resolveErrorMessage(error: unknown, fallbackMessage: string): string {
  return error instanceof Error ? error.message : fallbackMessage;
}

function collectMetadataPatch(items: StorageBrowseItem[]): {
  metadataPatch: Record<string, StorageFileMetadataItem>;
  metadataUrls: string[];
} {
  const metadataPatch: Record<string, StorageFileMetadataItem> = {};

  (Array.isArray(items) ? items : []).forEach((item) => {
    const key = String(item?.url || '').trim();
    const metadata = item?.metadata;
    if (!key || !metadata || typeof metadata !== 'object') return;
    if (metadata.source === 'unavailable') return;
    metadataPatch[key] = {
      ...metadata,
      url: key
    };
  });

  return {
    metadataPatch,
    metadataUrls: Object.keys(metadataPatch)
  };
}

export interface BrowseCloudStoragePathSuccess {
  success: true;
  response: StorageBrowseResponse;
  metadataPatch: Record<string, StorageFileMetadataItem>;
  metadataUrls: string[];
}

export interface CloudStorageActionFailure {
  success: false;
  errorMessage: string;
}

export type BrowseCloudStoragePathResult = BrowseCloudStoragePathSuccess | CloudStorageActionFailure;

export async function browseCloudStoragePath(
  storageId: string,
  path: string,
  cursor?: string,
  limit: number = DEFAULT_BROWSE_LIMIT
): Promise<BrowseCloudStoragePathResult> {
  try {
    const response = await db.browseStorage(storageId, path, cursor, limit);
    const { metadataPatch, metadataUrls } = collectMetadataPatch(response.items);
    return {
      success: true,
      response,
      metadataPatch,
      metadataUrls
    };
  } catch (error) {
    return {
      success: false,
      errorMessage: resolveErrorMessage(error, BROWSE_ERROR_MESSAGE)
    };
  }
}

export interface CloudStorageMutationSuccess {
  success: true;
  storageRevision?: number;
  noticeMessage?: string;
}

export type CloudStorageMutationResult = CloudStorageMutationSuccess | CloudStorageActionFailure;

export async function deleteCloudStorageItem(
  storageId: string,
  item: StorageBrowseItem
): Promise<CloudStorageMutationResult> {
  try {
    const response = await db.deleteStorageItem(
      storageId,
      item.path,
      item.entryType === 'directory',
      item.url || undefined
    );

    if (!response.success) {
      return {
        success: false,
        errorMessage: response.message || `Failed to delete ${item.name}`
      };
    }

    return {
      success: true,
      storageRevision: response.storageRevision,
      noticeMessage: `Deleted: ${item.name}`
    };
  } catch (error) {
    return {
      success: false,
      errorMessage: resolveErrorMessage(error, `Failed to delete ${item.name}`)
    };
  }
}

export async function renameCloudStorageItem(
  storageId: string,
  item: StorageBrowseItem,
  newName: string
): Promise<CloudStorageMutationResult> {
  try {
    const response = await db.renameStorageItem(
      storageId,
      item.path,
      newName,
      item.entryType === 'directory'
    );

    if (!response.success) {
      return {
        success: false,
        errorMessage: response.message || `Failed to rename ${item.name}`
      };
    }

    return {
      success: true,
      storageRevision: response.storageRevision,
      noticeMessage: `Renamed to: ${newName}`
    };
  } catch (error) {
    return {
      success: false,
      errorMessage: resolveErrorMessage(error, `Failed to rename ${item.name}`)
    };
  }
}

export function buildBatchDeleteRequestItems(items: StorageBrowseItem[]): StorageBatchDeleteRequestItem[] {
  return items.map((item) => ({
    path: item.path,
    isDirectory: item.entryType === 'directory',
    fileUrl: item.url || undefined
  }));
}

export function buildDownloadRequestItems(items: StorageBrowseItem[]): StorageDownloadRequestItem[] {
  return items.map((item) => ({
    path: item.path,
    name: item.name,
    isDirectory: item.entryType === 'directory',
    fileUrl: item.url || undefined
  }));
}

export interface BatchDeleteCloudStorageSuccess {
  success: true;
  storageRevision?: number;
  noticeMessage?: string;
  errorMessage?: string;
  removedItems?: StorageBrowseItem[];
}

export type BatchDeleteCloudStorageResult = BatchDeleteCloudStorageSuccess | CloudStorageActionFailure;

export async function batchDeleteCloudStorageItems(
  storageId: string,
  items: StorageBrowseItem[]
): Promise<BatchDeleteCloudStorageResult> {
  const requestItems = buildBatchDeleteRequestItems(items);

  try {
    const response = await db.batchDeleteStorageItems(storageId, requestItems);
    const removedItems = items.filter((_, index) => response.results[index]?.success === true);
    if (response.failureCount > 0) {
      return {
        success: true,
        storageRevision: response.storageRevision,
        errorMessage: `Deleted ${response.successCount}/${response.total}. Some items failed.`,
        removedItems
      };
    }

    return {
      success: true,
      storageRevision: response.storageRevision,
      noticeMessage: `Deleted ${response.successCount} items.`,
      removedItems
    };
  } catch (error) {
    return {
      success: false,
      errorMessage: resolveErrorMessage(error, BATCH_DELETE_ERROR_MESSAGE)
    };
  }
}

export async function prepareCloudStorageDownload(
  storageId: string,
  items: StorageBrowseItem[]
): Promise<StorageDownloadPrepareResponse> {
  const requestItems = buildDownloadRequestItems(items);
  return db.prepareStorageDownload(storageId, requestItems);
}

export async function startPreparedCloudStorageDownload(
  downloadUrl: string,
  _fallbackFileName: string = 'storage-download.bin'
): Promise<void> {
  triggerBrowserDownload({ href: downloadUrl });
}

export interface UploadCloudStorageFilesOptions {
  files: File[];
  storageId: string;
  timeoutMs?: number;
  onProgress?: (progress: { done: number; total: number }) => void;
  onStorageRevision?: (storageRevision?: number) => void;
}

export interface UploadCloudStorageFilesResult {
  noticeMessage?: string;
  errorMessage?: string;
}

function buildUploadSummaryMessage(total: number, successCount: number, errors: string[]): UploadCloudStorageFilesResult {
  if (errors.length > 0) {
    return {
      errorMessage:
        `Uploaded ${successCount}/${total}. ` +
        errors.slice(0, 3).join(' | ') +
        (errors.length > 3 ? ' ...' : '')
    };
  }

  return {
    noticeMessage: `Uploaded ${successCount} file(s).`
  };
}

export async function uploadCloudStorageFiles({
  files,
  storageId,
  timeoutMs = DEFAULT_UPLOAD_TIMEOUT_MS,
  onProgress,
  onStorageRevision
}: UploadCloudStorageFilesOptions): Promise<UploadCloudStorageFilesResult> {
  const uploadList = Array.isArray(files) ? files : [];

  let successCount = 0;
  const errors: string[] = [];

  for (let index = 0; index < uploadList.length; index += 1) {
    const file = uploadList[index];
    try {
      const response = await db.uploadStorageFile(file, storageId, timeoutMs);
      onStorageRevision?.(response.storageRevision);
      if (response.success) {
        successCount += 1;
      } else {
        errors.push(`${file.name}: ${response.error || UPLOAD_FAILED_MESSAGE}`);
      }
    } catch (error) {
      errors.push(`${file.name}: ${resolveErrorMessage(error, UPLOAD_FAILED_MESSAGE)}`);
    } finally {
      onProgress?.({ done: index + 1, total: uploadList.length });
    }
  }

  return buildUploadSummaryMessage(uploadList.length, successCount, errors);
}
