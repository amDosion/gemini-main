/**
 * 内嵌模式导航组件
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

  type NavEntry =
    | { type: 'mode'; mode: ModeCatalogItem }
    | { type: 'action'; id: 'settings' | 'persona' | 'cloud' };

  const navEntries = useMemo<NavEntry[]>(() => {
    const entries: NavEntry[] = [];
    let personaInserted = false;

    navModes.forEach((mode) => {
      entries.push({ type: 'mode', mode });
      if (mode.id === 'pdf-extract') {
        entries.push({ type: 'action', id: 'persona' });
        personaInserted = true;
      }
    });

    if (!personaInserted) {
      entries.push({ type: 'action', id: 'persona' });
    }
    entries.push({ type: 'action', id: 'cloud' });
    entries.push({ type: 'action', id: 'settings' });

    return entries;
  }, [navModes]);

  return (
    <div className="flex-shrink-0 border-l border-slate-800 bg-slate-900/30 flex flex-col h-full overflow-hidden">
      <div className="px-3 py-3 border-b border-slate-800/50">
        <div className="flex items-center gap-2">
          <LayoutGrid size={14} className="text-indigo-400" />
          <span className="text-xs font-bold text-white">模式切换</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1 custom-scrollbar">
        {navModes.length === 0 && (
          <div className="px-2 py-3 text-[11px] text-slate-500">
            暂无可用模式
          </div>
        )}

        {navEntries.map((entry) => {
          if (entry.type === 'action') {
            if (entry.id === 'settings') {
              return (
                <button
                  key="action-settings"
                  type="button"
                  onClick={() => onOpenSettings('profiles')}
                  title="Setting"
                  className="w-full flex flex-col items-center justify-center gap-1 px-2 py-2 rounded-lg text-[11px] transition-all text-slate-400 hover:bg-slate-800 hover:text-white"
                >
                  <Settings size={15} />
                  <span className="w-full text-center leading-tight">Setting</span>
                </button>
              );
            }

            if (entry.id === 'cloud') {
              return (
                <button
                  key="action-cloud"
                  type="button"
                  onClick={onOpenCloudStorage}
                  title="Cloud Drive"
                  className="w-full flex flex-col items-center justify-center gap-1 px-2 py-2 rounded-lg text-[11px] transition-all text-slate-400 hover:bg-slate-800 hover:text-white"
                >
                  <Cloud size={15} />
                  <span className="w-full text-center leading-tight">Cloud</span>
                </button>
              );
            }

            return (
              <button
                key="action-persona"
                type="button"
                onClick={onOpenPersonaView}
                title="AI Persona & Roles"
                className={`w-full flex flex-col items-center justify-center gap-1 px-2 py-2 rounded-lg text-[11px] transition-all ${
                  isPersonaViewOpen
                    ? 'bg-indigo-500/20 text-indigo-400'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <UserCircle2 size={15} />
                <span className="w-full text-center leading-tight">Persona</span>
              </button>
            );
          }

          const { mode } = entry;
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
              className={`w-full flex flex-col items-center justify-center gap-1 px-2 py-2 rounded-lg text-[11px] transition-all ${
                isActive
                  ? `${colors.bg} text-white`
                  : !hasModels
                    ? 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
              }`}
            >
              <Icon size={15} />
              <span className="w-full text-center leading-tight">{mode.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default InlineModeNavigation;
