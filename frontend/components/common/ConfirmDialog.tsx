import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { ActionDialog } from './ActionDialog';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
}) => {
  return (
    <ActionDialog
      isOpen={isOpen}
      title={title}
      description={message}
      cancelLabel={cancelLabel}
      confirmLabel={confirmLabel}
      confirmTone="danger"
      onCancel={onCancel}
      onConfirm={onConfirm}
      icon={<AlertTriangle size={16} />}
    />
  );
};

export default ConfirmDialog;
