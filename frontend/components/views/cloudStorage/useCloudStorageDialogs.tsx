import React, { useCallback, useEffect, useRef, useState } from 'react';
import type { StorageBrowseItem } from '../../../types/storage';
import {
  CloudStorageActionDialog,
  CloudStorageDialogState
} from './CloudStorageActionDialog';

type PendingDialogRequest =
  | { kind: 'confirm'; resolve: (value: boolean) => void }
  | { kind: 'rename'; resolve: (value: string | null) => void };

export interface UseCloudStorageDialogsResult {
  confirmDelete: (item: StorageBrowseItem) => Promise<boolean>;
  confirmBatchDelete: (items: StorageBrowseItem[]) => Promise<boolean>;
  promptRename: (item: StorageBrowseItem) => Promise<string | null>;
  dialog: React.ReactNode;
}

export function useCloudStorageDialogs(): UseCloudStorageDialogsResult {
  const [dialogState, setDialogState] = useState<CloudStorageDialogState | null>(null);
  const pendingRef = useRef<PendingDialogRequest | null>(null);

  const cancelPending = useCallback(() => {
    const pending = pendingRef.current;
    if (!pending) return;
    pendingRef.current = null;
    if (pending.kind === 'confirm') {
      pending.resolve(false);
      return;
    }
    pending.resolve(null);
  }, []);

  const confirmDelete = useCallback((item: StorageBrowseItem) => {
    cancelPending();
    return new Promise<boolean>((resolve) => {
      pendingRef.current = { kind: 'confirm', resolve };
      setDialogState({ kind: 'confirmDelete', item });
    });
  }, [cancelPending]);

  const confirmBatchDelete = useCallback((items: StorageBrowseItem[]) => {
    cancelPending();
    return new Promise<boolean>((resolve) => {
      pendingRef.current = { kind: 'confirm', resolve };
      setDialogState({ kind: 'confirmBatchDelete', items });
    });
  }, [cancelPending]);

  const promptRename = useCallback((item: StorageBrowseItem) => {
    cancelPending();
    return new Promise<string | null>((resolve) => {
      pendingRef.current = { kind: 'rename', resolve };
      setDialogState({ kind: 'rename', item, value: item.name });
    });
  }, [cancelPending]);

  const handleCancelDialog = useCallback(() => {
    cancelPending();
    setDialogState(null);
  }, [cancelPending]);

  const handleConfirmDialog = useCallback(() => {
    const pending = pendingRef.current;
    pendingRef.current = null;
    if (!pending) {
      setDialogState(null);
      return;
    }

    if (pending.kind === 'confirm') {
      pending.resolve(true);
    } else {
      pending.resolve(dialogState?.kind === 'rename' ? dialogState.value : null);
    }
    setDialogState(null);
  }, [dialogState]);

  const handleRenameValueChange = useCallback((value: string) => {
    setDialogState((prev) => (prev?.kind === 'rename' ? { ...prev, value } : prev));
  }, []);

  useEffect(() => {
    return () => {
      cancelPending();
    };
  }, [cancelPending]);

  return {
    confirmDelete,
    confirmBatchDelete,
    promptRename,
    dialog: (
      <CloudStorageActionDialog
        state={dialogState}
        onCancel={handleCancelDialog}
        onConfirm={handleConfirmDialog}
        onRenameValueChange={handleRenameValueChange}
      />
    )
  };
}

