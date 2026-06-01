/**
 * 应用模式导航组件
 *
 * 说明：
 * - modeCatalog 只描述 provider/profile 模型集合下的模式可用模型情况
 * - runtime probe 由独立接口负责，导航不消费运行时执行状态
 */
import React, { useMemo } from 'react';
import {
  MessageSquare,
  Wand2,
  Crop,
  Expand,
  PlaySquare,
  Mic,
  FileText,
  Shirt,
  Network,
  Layers,
  Sparkles,
  LayoutGrid,
  Cloud,
  Settings,
  UserCircle2,
  type LucideIcon,
} from 'lucide-react';
import { AppMode, ModeCatalogItem } from '../../types/types';

interface InlineModeNavigationProps {
  currentMode: AppMode;
  setMode: (mode: AppMode) => void;
  modeCatalog?: ModeCatalogItem[];
  onOpenSettings: (tab?: 'profiles' | 'editor') => void;
  onOpenCloudStorage: () => void;
  isPersonaViewOpen: boolean;
  onOpenPersonaView: () => void;
}

const MODE_ICON_MAP: Record<string, LucideIcon> = {
  chat: MessageSquare,
  'multi-agent': Network,
  'image-gen': Wand2,
  'image-chat-edit': MessageSquare,
  'image-mask-edit': Crop,
  'image-inpainting': Wand2,
  'image-background-edit': Layers,
  'image-recontext': Sparkles,
  'virtual-try-on': Shirt,
  'image-outpainting': Expand,
  'video-gen': PlaySquare,
  'audio-gen': Mic,
  'pdf-extract': FileText,
};

const MODE_COLOR_MAP: Record<string, { bg: string; text: string }> = {
  chat: { bg: 'bg-indigo-600', text: 'text-indigo-400' },
  'multi-agent': { bg: 'bg-teal-600', text: 'text-teal-400' },
  'image-gen': { bg: 'bg-emerald-600', text: 'text-emerald-400' },
  'image-chat-edit': { bg: 'bg-pink-600', text: 'text-pink-400' },
  'image-mask-edit': { bg: 'bg-pink-600', text: 'text-pink-400' },
  'image-inpainting': { bg: 'bg-pink-600', text: 'text-pink-400' },
  'image-background-edit': { bg: 'bg-pink-600', text: 'text-pink-400' },
  'image-recontext': { bg: 'bg-pink-600', text: 'text-pink-400' },
  'virtual-try-on': { bg: 'bg-rose-600', text: 'text-rose-400' },
  'image-outpainting': { bg: 'bg-orange-600', text: 'text-orange-400' },
  'video-gen': { bg: 'bg-indigo-600', text: 'text-indigo-400' },
  'audio-gen': { bg: 'bg-cyan-600', text: 'text-cyan-400' },
  'pdf-extract': { bg: 'bg-purple-600', text: 'text-purple-400' },
};

const GeminiBrandMark: React.FC = () => (
  <svg
    role="img"
    aria-label="Gemini"
    viewBox="0 0 48 48"
    className="h-7 w-7 drop-shadow-[0_0_12px_rgba(129,140,248,0.45)]"
  >
    <defs>
      <linearGradient id="inline-gemini-brand-gradient" x1="9" x2="39" y1="39" y2="9">
        <stop offset="0%" stopColor="#7DD3FC" />
        <stop offset="48%" stopColor="#A78BFA" />
        <stop offset="100%" stopColor="#F0ABFC" />
      </linearGradient>
    </defs>
    <path
      fill="url(#inline-gemini-brand-gradient)"
      d="M24 3.5c2.7 10.4 10.1 17.8 20.5 20.5C34.1 26.7 26.7 34.1 24 44.5 21.3 34.1 13.9 26.7 3.5 24 13.9 21.3 21.3 13.9 24 3.5Z"
    />
    <path
      fill="rgba(255,255,255,0.72)"
      d="M24 11.2c1.7 6.6 6.2 11.1 12.8 12.8-6.6 1.7-11.1 6.2-12.8 12.8-1.7-6.6-6.2-11.1-12.8-12.8 6.6-1.7 11.1-6.2 12.8-12.8Z"
      opacity="0.2"
    />
  </svg>
);

export const InlineModeNavigation: React.FC<InlineModeNavigationProps> = ({
  currentMode,
  setMode,
  modeCatalog = [],
  onOpenSettings,
  onOpenCloudStorage,
  isPersonaViewOpen,
  onOpenPersonaView,
}) => {
  const navModes = useMemo<ModeCatalogItem[]>(() => {
    return modeCatalog.filter((mode) => mode.visibleInNavigation !== false);
  }, [modeCatalog]);

  const utilityActions: Array<{
    id: string;
    label: string;
    title: string;
    Icon: LucideIcon;
    onClick: () => void;
    active?: boolean;
  }> = [
    {
      id: 'persona',
      label: 'Persona',
      title: 'AI Persona & Roles',
      Icon: UserCircle2,
      onClick: onOpenPersonaView,
      active: isPersonaViewOpen,
    },
    {
      id: 'cloud',
      label: 'Cloud',
      title: 'Cloud Drive',
      Icon: Cloud,
      onClick: onOpenCloudStorage,
    },
    {
      id: 'settings',
      label: 'Setting',
      title: 'Setting',
      Icon: Settings,
      onClick: () => onOpenSettings('profiles'),
    },
  ];

  return (
    <div className="flex h-full w-full flex-col overflow-hidden border-r border-slate-800 bg-slate-950">
      <div className="flex h-14 shrink-0 items-center justify-center border-b border-slate-800/70 px-2">
        <GeminiBrandMark />
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1 custom-scrollbar">
        {navModes.length === 0 && (
          <div className="px-2 py-3 text-center text-[11px] leading-tight text-slate-500">
            暂无可用模式
          </div>
        )}

        {navModes.map((mode) => {
          const isActive = currentMode === mode.id;
          const hasModels = mode.hasModels;
          const colors = MODE_COLOR_MAP[mode.id] || MODE_COLOR_MAP.chat;
          const Icon = MODE_ICON_MAP[mode.id] || LayoutGrid;
          const buttonTitle = !hasModels
            ? `${mode.label}（当前 provider 未配置该模式模型）`
            : (mode.description || mode.label);

          return (
            <button
              key={mode.id}
              onClick={() => setMode(mode.id as AppMode)}
              title={buttonTitle}
              className={`flex min-h-[52px] w-full flex-col items-center justify-center gap-1 rounded-md px-2 py-2 text-[11px] transition-colors ${
                isActive
                  ? `${colors.bg} text-white`
                  : !hasModels
                    ? 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
              }`}
            >
              <Icon size={15} />
              <span className="block w-full truncate text-center leading-tight">{mode.label}</span>
            </button>
          );
        })}
      </div>

      <div className="shrink-0 border-t border-slate-800/70 p-2 space-y-1">
        {utilityActions.map(({ id, label, title, Icon, onClick, active }) => (
          <button
            key={id}
            type="button"
            onClick={onClick}
            title={title}
            className={`flex min-h-[46px] w-full flex-col items-center justify-center gap-1 rounded-md px-2 py-2 text-[11px] transition-colors ${
              active
                ? 'bg-indigo-500/20 text-indigo-300'
                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
            }`}
          >
            <Icon size={15} />
            <span className="block w-full truncate text-center leading-tight">{label}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

export default InlineModeNavigation;
