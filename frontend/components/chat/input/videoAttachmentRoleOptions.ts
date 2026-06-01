import type { Attachment } from '../../../types/types';
import type { ModeControlsSchema, VideoContractAttachmentSlot } from '../../../hooks/useModeControlsSchema';

export interface AttachmentRoleOption {
  value: string;
  label: string;
  slotName: string;
}

const SLOT_LABELS: Record<string, string> = {
  source_image: '首帧',
  last_frame_image: '尾帧',
  source_video: '源视频',
  reference_video: '参考视频',
  reference_images: '参考图',
  video_edit_reference_images: '参考图',
  driving_audio: '驱动音频',
  video_mask_image: '遮罩图',
};

const SLOT_DEFAULT_ROLES: Record<string, string> = {
  source_image: 'first_frame',
  last_frame_image: 'last_frame',
  source_video: 'source_video',
  reference_video: 'reference_video',
  reference_images: 'reference_image',
  video_edit_reference_images: 'reference_image',
  driving_audio: 'driving_audio',
  video_mask_image: 'mask',
};

function getAttachmentKind(attachment: Attachment): string | null {
  const mimeType = attachment.mimeType || '';
  if (mimeType.startsWith('image/')) return 'image';
  if (mimeType.startsWith('video/')) return 'video';
  if (mimeType.startsWith('audio/')) return 'audio';
  return null;
}

function getSlotKind(slot: VideoContractAttachmentSlot): string | null {
  if (slot.kind) return slot.kind;
  if (slot.name.includes('video')) return 'video';
  if (slot.name.includes('audio')) return 'audio';
  if (slot.name.includes('image') || slot.name.includes('frame') || slot.name.includes('mask')) {
    return 'image';
  }
  return null;
}

function getPrimaryRole(slot: VideoContractAttachmentSlot): string | null {
  const roles = slot.roles ?? [];
  const preferred = SLOT_DEFAULT_ROLES[slot.name];
  if (preferred && (roles.length === 0 || roles.includes(preferred))) {
    return preferred;
  }
  return roles[0] ?? slot.name ?? null;
}

function getRoleLabel(slot: VideoContractAttachmentSlot): string {
  return SLOT_LABELS[slot.name] || slot.label || slot.name;
}

export function getVideoAttachmentRoleOptions(
  schema: ModeControlsSchema | null | undefined,
  attachment: Attachment
): AttachmentRoleOption[] {
  const attachmentKind = getAttachmentKind(attachment);
  if (!attachmentKind) return [];

  const slots = schema?.videoContract?.attachmentSlots ?? [];
  const options: AttachmentRoleOption[] = [];
  const seenValues = new Set<string>();

  for (const slot of slots) {
    if (!slot || slot.enabled === false) continue;
    const slotKind = getSlotKind(slot);
    if (slotKind && slotKind !== attachmentKind) continue;

    const value = getPrimaryRole(slot);
    if (!value || seenValues.has(value)) continue;

    seenValues.add(value);
    options.push({
      value,
      label: getRoleLabel(slot),
      slotName: slot.name,
    });
  }

  return options;
}

export function applyDefaultVideoAttachmentRoles(
  schema: ModeControlsSchema | null | undefined,
  attachments: Attachment[]
): Attachment[] {
  if (attachments.length === 0) return attachments;

  let changed = false;
  const nextAttachments = attachments.map((attachment) => {
    if (attachment.role) return attachment;
    const defaultRole = getVideoAttachmentRoleOptions(schema, attachment)[0]?.value;
    if (!defaultRole) return attachment;
    changed = true;
    return {
      ...attachment,
      role: defaultRole,
    };
  });

  return changed ? nextAttachments : attachments;
}
