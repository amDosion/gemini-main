import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ChevronDown,
  RefreshCw,
  X,
} from 'lucide-react';
import { AppMode, ModeCatalogItem } from '../../types/types';

interface WorkspaceTagViewsProps {
  activeMode: AppMode;
  openModes: AppMode[];
  modeCatalog?: ModeCatalogItem[];
  onSelectMode: (mode: AppMode) => void;
  onCloseMode: (mode: AppMode) => void;
  onCloseModes?: (modes: AppMode[]) => void;
  onReloadMode?: (mode: AppMode) => void;
}

const FALLBACK_MODE_LABELS: Record<AppMode, string> = {
  chat: 'Chat',
  'multi-agent': 'Multi Agent',
  'image-gen': 'Image Gen',
  'image-chat-edit': 'Chat Edit',
  'image-mask-edit': 'Mask Edit',
  'image-inpainting': 'Inpainting',
  'image-background-edit': 'Background',
  'image-recontext': 'Recontext',
  'image-outpainting': 'Outpainting',
  'video-gen': 'Video Gen',
  'audio-gen': 'Audio Gen',
  'pdf-extract': 'PDF Extract',
  'virtual-try-on': 'Try On',
  'image-upscale': 'Upscale',
  'image-segmentation': 'Segmentation',
  'product-recontext': 'Product',
};

export const getWorkspaceModeLabel = (
  mode: AppMode,
  modeCatalog: ModeCatalogItem[] = []
): string => {
  return modeCatalog.find((item) => item.id === mode)?.label || FALLBACK_MODE_LABELS[mode] || mode;
};

export const WorkspaceTagViews: React.FC<WorkspaceTagViewsProps> = ({
  activeMode,
  openModes,
  modeCatalog = [],
  onSelectMode,
  onCloseMode,
  onCloseModes,
  onReloadMode,
}) => {
  const [pinnedModes, setPinnedModes] = useState<Set<AppMode>>(new Set());
  const [openMenuMode, setOpenMenuMode] = useState<AppMode | null>(null);
  const [menuPosition, setMenuPosition] = useState<{ left: number; top: number } | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setPinnedModes((current) => {
      const next = new Set([...current].filter((mode) => openModes.includes(mode)));
      return next.size === current.size ? current : next;
    });
  }, [openModes]);

  useEffect(() => {
    if (!openMenuMode) return;

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (target && rootRef.current?.contains(target)) {
        return;
      }
      setOpenMenuMode(null);
    };

    document.addEventListener('mousedown', handlePointerDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
    };
  }, [openMenuMode]);

  const orderedModes = useMemo(() => openModes, [openModes]);

  const closeModes = (modes: AppMode[]) => {
    const uniqueModes = [...new Set(modes)].filter((mode) => openModes.includes(mode));
    if (uniqueModes.length === 0) return;

    if (onCloseModes) {
      onCloseModes(uniqueModes);
      return;
    }

    uniqueModes.forEach(onCloseMode);
  };

  const closeSingleMode = (mode: AppMode) => {
    if (openModes.length <= 1 || pinnedModes.has(mode)) return;
    onCloseMode(mode);
  };

  const togglePinnedMode = (mode: AppMode) => {
    setPinnedModes((current) => {
      const next = new Set(current);
      if (next.has(mode)) {
        next.delete(mode);
      } else {
        next.add(mode);
      }
      return next;
    });
    setOpenMenuMode(null);
    setMenuPosition(null);
  };

  const getMenuCloseTargets = (mode: AppMode) => {
    const visibleIndex = orderedModes.indexOf(mode);
    const isPinned = pinnedModes.has(mode);
    const left = orderedModes
      .slice(0, Math.max(0, visibleIndex))
      .filter((item) => !pinnedModes.has(item));
    const right = orderedModes
      .slice(visibleIndex + 1)
      .filter((item) => !pinnedModes.has(item));
    const others = orderedModes.filter((item) => item !== mode && !pinnedModes.has(item));

    return {
      current: !isPinned && openModes.length > 1 ? [mode] : [],
      left,
      right,
      others,
    };
  };

  const runCloseAction = (modes: AppMode[]) => {
    closeModes(modes);
    setOpenMenuMode(null);
    setMenuPosition(null);
  };

  const openContextMenu = (mode: AppMode, event: React.MouseEvent<HTMLElement>) => {
    event.preventDefault();
    event.stopPropagation();
    const rootRect = rootRef.current?.getBoundingClientRect();
    const menuWidth = 168;
    const margin = 8;

    if (rootRect) {
      const maxLeft = Math.max(margin, rootRect.width - menuWidth - margin);
      setMenuPosition({
        left: Math.min(Math.max(margin, event.clientX - rootRect.left), maxLeft),
        top: Math.max(32, event.clientY - rootRect.top),
      });
    } else {
      setMenuPosition({ left: margin, top: 32 });
    }
    setOpenMenuMode(mode);
  };

  if (openModes.length === 0) {
    return null;
  }

  return (
    <div
      ref={rootRef}
      data-testid="workspace-tag-views"
      className="relative flex h-9 shrink-0 items-center gap-2 border-b border-slate-800 bg-slate-950 px-2"
    >
      <div
        role="tablist"
        aria-label="工作区选项卡"
        onScroll={() => {
          setOpenMenuMode(null);
          setMenuPosition(null);
        }}
        className="custom-scrollbar flex min-w-0 flex-1 items-end gap-1 overflow-x-auto overflow-y-visible pt-1"
      >
        {orderedModes.map((mode) => {
          const isActive = activeMode === mode;
          const isPinned = pinnedModes.has(mode);
          const label = getWorkspaceModeLabel(mode, modeCatalog);
          const canClose = !isPinned && openModes.length > 1;

          const tagClassName = [
            'group relative flex h-8 max-w-[190px] shrink-0 items-center overflow-visible rounded-t-md border px-1.5 text-xs transition-colors',
            isActive
              ? 'border-slate-600 bg-slate-800 text-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]'
              : 'border-slate-800 bg-slate-900 text-slate-400 hover:border-slate-700 hover:bg-slate-800/80 hover:text-slate-100',
            isPinned ? 'border-cyan-700/60' : '',
          ].join(' ');

          return (
            <div
              key={mode}
              data-testid={`workspace-tag-${mode}`}
              onContextMenu={(event) => openContextMenu(mode, event)}
              className={tagClassName}
            >
              <button
                type="button"
                role="tab"
                aria-selected={isActive}
                title={label}
                onClick={() => onSelectMode(mode)}
                className="flex h-full min-w-0 flex-1 items-center gap-1.5 rounded-t-md px-1 text-left outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/60"
              >
                {isPinned && (
                  <span
                    role="img"
                    aria-label={`${label} 已固定`}
                    className="shrink-0 text-[12px] leading-none"
                  >
                    📌
                  </span>
                )}
                <span className="truncate">{label}</span>
              </button>

              {canClose && (
                <button
                  type="button"
                  aria-label={`关闭 ${label}`}
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    closeSingleMode(mode);
                  }}
                  className="ml-0.5 rounded p-0.5 text-slate-500 transition-colors hover:bg-slate-700 hover:text-slate-100"
                >
                  <X size={12} />
                </button>
              )}

            </div>
          );
        })}
      </div>

      <button
        type="button"
        aria-label="重载当前选项卡"
        title="重载当前选项卡"
        onClick={() => onReloadMode?.(activeMode)}
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-slate-800 bg-slate-900 text-slate-400 transition-colors hover:border-slate-700 hover:bg-slate-800 hover:text-slate-100"
      >
        <RefreshCw size={14} />
      </button>

      {openMenuMode && menuPosition && (() => {
        const isPinned = pinnedModes.has(openMenuMode);
        const closeTargets = getMenuCloseTargets(openMenuMode);

        return (
          <div
            role="menu"
            className="absolute z-50 min-w-[168px] rounded-md border border-slate-700 bg-slate-950 py-1 shadow-xl shadow-black/40"
            style={{ left: menuPosition.left, top: menuPosition.top }}
          >
            <WorkspaceTagMenuButton
              icon={<span aria-hidden="true">📌</span>}
              label={isPinned ? '取消固定选项卡' : '固定选项卡'}
              onClick={() => togglePinnedMode(openMenuMode)}
            />
            <WorkspaceTagMenuButton
              label="关闭选项卡"
              disabled={closeTargets.current.length === 0}
              onClick={() => runCloseAction(closeTargets.current)}
            />
            <div className="my-1 h-px bg-slate-800" />
            <WorkspaceTagMenuButton
              label="关闭左侧"
              disabled={closeTargets.left.length === 0}
              onClick={() => runCloseAction(closeTargets.left)}
            />
            <WorkspaceTagMenuButton
              label="关闭右侧"
              disabled={closeTargets.right.length === 0}
              onClick={() => runCloseAction(closeTargets.right)}
            />
            <WorkspaceTagMenuButton
              label="关闭其他"
              disabled={closeTargets.others.length === 0}
              onClick={() => runCloseAction(closeTargets.others)}
            />
          </div>
        );
      })()}
    </div>
  );
};

interface WorkspaceTagMenuButtonProps {
  label: string;
  icon?: React.ReactNode;
  disabled?: boolean;
  onClick: () => void;
}

const WorkspaceTagMenuButton: React.FC<WorkspaceTagMenuButtonProps> = ({
  label,
  icon,
  disabled = false,
  onClick,
}) => {
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        if (!disabled) {
          onClick();
        }
      }}
      className={`flex h-8 w-full items-center gap-2 px-3 text-left text-xs transition-colors ${
        disabled
          ? 'cursor-not-allowed text-slate-600'
          : 'text-slate-300 hover:bg-slate-800 hover:text-slate-100'
      }`}
    >
      <span className="flex w-4 shrink-0 items-center justify-center text-slate-400">
        {icon || <ChevronDown size={13} className="rotate-[-90deg]" />}
      </span>
      <span className="truncate">{label}</span>
    </button>
  );
};

export default WorkspaceTagViews;
