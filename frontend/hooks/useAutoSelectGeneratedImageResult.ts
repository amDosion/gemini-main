import { useEffect, useRef } from 'react';
import { Attachment, Message, Role } from '../types/types';
import {
  buildMessageMediaSignature,
  buildMessagesMediaSignature,
} from '../utils/messageMediaSignature';

export type AutoSelectGeneratedImageResultPayload = {
  message: Message;
  attachments: Attachment[];
  firstAttachment: Attachment;
  firstUrl: string;
};

type UseAutoSelectGeneratedImageResultOptions = {
  messages: Message[];
  loadingState: string;
  getDisplayAttachments: (attachments?: Attachment[]) => Attachment[];
  getAttachmentUrl: (attachment: Attachment) => string | null;
  onSelectResult: (payload: AutoSelectGeneratedImageResultPayload) => void;
};

export function useAutoSelectGeneratedImageResult({
  messages,
  loadingState,
  getDisplayAttachments,
  getAttachmentUrl,
  onSelectResult,
}: UseAutoSelectGeneratedImageResultOptions) {
  const lastProcessedMessageKeyRef = useRef<string | null>(null);
  const messagesMediaSignature = buildMessagesMediaSignature(messages);

  useEffect(() => {
    if (loadingState !== 'idle' || messages.length === 0) {
      return;
    }

    const lastMessage = messages[messages.length - 1];
    const lastMessageKey = `${lastMessage.id}:${buildMessageMediaSignature(lastMessage)}`;
    if (lastMessageKey === lastProcessedMessageKeyRef.current) {
      return;
    }

    if (lastMessage.role === Role.MODEL) {
      const attachments = getDisplayAttachments(lastMessage.attachments);
      const firstAttachment = attachments.find((attachment) =>
        Boolean(getAttachmentUrl(attachment))
      );
      const firstUrl = firstAttachment ? getAttachmentUrl(firstAttachment) : null;

      if (firstAttachment && firstUrl) {
        onSelectResult({
          message: lastMessage,
          attachments,
          firstAttachment,
          firstUrl,
        });
        lastProcessedMessageKeyRef.current = lastMessageKey;
        return;
      }
    }

    if (lastMessage.isError) {
      lastProcessedMessageKeyRef.current = lastMessageKey;
    }
  }, [
    getAttachmentUrl,
    getDisplayAttachments,
    loadingState,
    messages,
    messagesMediaSignature,
    onSelectResult,
  ]);
}
