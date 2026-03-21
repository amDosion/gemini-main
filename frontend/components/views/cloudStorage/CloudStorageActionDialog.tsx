import React from 'react';
import type { StorageBrowseItem } from '../../../types/storage';
import { ActionDialog } from '../../common/ActionDialog';

export type CloudStorageDialogState =
  | { kind: 'confirmDelete'; item: StorageBrowseItem }
  | { kind: 'confirmBatchDelete'; items: StorageBrowseItem[] }
  | { kind: 'rename'; item: StorageBrowseItem; value: string };

interface CloudStorageActionDialogProps {
  state: CloudStorageDialogState | null;
  onCancel: () => void;
  onConfirm: () => void;
  onRenameValueChange: (value: string) => void;
}

export const CloudStorageActionDialog: React.FC<CloudStorageActionDialogProps> = ({
  state,
  onCancel,
  onConfirm,
  onRenameValueChange
}) => {
  if (!state) return null;

  const isRename = state.kind === 'rename';
  const renameValue = isRename ? state.value : '';
  const canConfirmRename = renameValue.trim().length > 0;

  const title = (() => {
    if (state.kind === 'confirmDelete') {
      return state.item.entryType === 'directory' ? 'Delete folder?' : 'Delete file?';
    }
    if (state.kind === 'confirmBatchDelete') {
      return 'Delete selected items?';
    }
    return 'Rename item';
  })();

  const description = (() => {
    if (state.kind === 'confirmDelete') {
      return `This action cannot be undone: "${state.item.name}".`;
    }
    if (state.kind === 'confirmBatchDelete') {
      return `This action will delete ${state.items.length} selected item(s).`;
    }
    return `Enter a new name for "${state.item.name}".`;
  })();

  const confirmLabel = isRename ? 'Rename' : 'Delete';

  return (
    <ActionDialog
      isOpen
      title={title}
      description={description}
      cancelLabel="Cancel"
      confirmLabel={confirmLabel}
      confirmTone={isRename ? 'primary' : 'danger'}
      confirmDisabled={isRename && !canConfirmRename}
      onCancel={onCancel}
      onConfirm={onConfirm}
    >
      {isRename ? (
        <input
          type="text"
          value={renameValue}
          autoFocus
          onChange={(event) => onRenameValueChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              if (!canConfirmRename) return;
              onConfirm();
            }
          }}
          className="w-full px-3 py-2 rounded-md border border-slate-700 bg-slate-950 text-sm text-slate-200 focus:outline-none focus:border-indigo-500/70"
          placeholder="New file name"
        />
      ) : null}
    </ActionDialog>
  );
};
