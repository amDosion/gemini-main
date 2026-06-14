import { Message, Role } from '../types/types';

/** 空占位消息:无正文、无附件、且非错误。用于过滤"双气泡"占位。 */
export function isPlaceholderMessage(message: Message): boolean {
  return (
    !message.content &&
    (!message.attachments || message.attachments.length === 0) &&
    !message.isError
  );
}

/** MODEL 角色且(有附件 或 是错误)的消息,按时间倒序(最新在前)。 */
export function filterModelImageBatches(messages: Message[]): Message[] {
  return messages
    .filter(
      (message) =>
        message.role === Role.MODEL &&
        ((message.attachments && message.attachments.length > 0) || message.isError)
    )
    .reverse();
}
