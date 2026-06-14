import React from 'react';
import { Shirt, User, Layers, Bot, AlertCircle } from 'lucide-react';
import { Message, Role } from '../../../types/types';
import { CachedImage } from '../../common/CachedImage';
import { getAttachmentStableKey, mapDisplayImageAttachments } from './tryOnAttachments';
import { isPlaceholderMessage } from '../../../utils/messageFilters';

const TRY_ON_HISTORY_TIME_OPTIONS: Intl.DateTimeFormatOptions = {
  hour: '2-digit',
  minute: '2-digit',
};
const TRY_ON_HISTORY_TIME_FORMATTER = new Intl.DateTimeFormat([], TRY_ON_HISTORY_TIME_OPTIONS);

const formatTryOnHistoryTime = (timestamp: Message['timestamp']) => {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return date.toLocaleTimeString([], TRY_ON_HISTORY_TIME_OPTIONS);
  }
  return TRY_ON_HISTORY_TIME_FORMATTER.format(date);
};

interface TryOnHistorySidebarProps {
  scrollRef: React.Ref<HTMLDivElement>;
  messages: Message[];
  activeBatchId?: string;
  modelName?: string;
  isLoading: boolean;
  loadingState: string;
  onSelectMessage: (id: string) => void;
}

/**
 * Virtual Try-On 历史侧边栏。
 *
 * 1:1 抽离自 `VirtualTryOnView` 的 `sidebarContent`。包裹在 `React.memo` 中以保留原本
 * `useMemo` 的渲染边界（仅当 messages / 选中批次 / 模型名 / 加载状态变化时重渲染），
 * 避免右侧面板的高频状态（如滑块、上传槽）触发整段历史列表重渲染。
 */
export const TryOnHistorySidebar = React.memo(function TryOnHistorySidebar({
  scrollRef,
  messages,
  activeBatchId,
  modelName,
  isLoading,
  loadingState,
  onSelectMessage,
}: TryOnHistorySidebarProps) {
  return (
    <div ref={scrollRef} className="flex-1 p-4 space-y-6 overflow-y-auto custom-scrollbar">
      {messages.map((msg) => {
        // 过滤空占位消息
        if (isPlaceholderMessage(msg)) return null;

        const isSelected = msg.role === Role.MODEL && activeBatchId === msg.id;

        return (
          <div
            key={msg.id}
            className={`flex flex-col gap-2 ${msg.role === Role.USER ? 'items-end' : 'items-start'}`}
          >
            <div className="flex items-center gap-2 text-xs text-slate-500 px-1">
              {msg.role === Role.USER ? <User size={12} /> : <Bot size={12} />}
              <span>{msg.role === Role.USER ? '输入' : modelName || 'AI'}</span>
            </div>
            <div
              className={`p-3 rounded-2xl max-w-full text-sm shadow-sm cursor-pointer transition-all ${
                msg.role === Role.USER
                  ? 'bg-slate-800 text-slate-200 rounded-tr-sm'
                  : `bg-slate-800/50 text-slate-300 border rounded-tl-sm ${
                      isSelected
                        ? 'ring-2 ring-rose-500 border-transparent'
                        : 'border-slate-700/50 hover:border-slate-600'
                    }`
              }`}
              onClick={() => {
                if (msg.role === Role.MODEL && msg.attachments?.length) {
                  onSelectMessage(msg.id);
                }
              }}
            >
              {msg.content && <p className="mb-2">{msg.content}</p>}

              {/* 附件显示 */}
              {mapDisplayImageAttachments(msg.attachments, msg.id).map((att, idx) => (
                <div
                  key={`${msg.id}:${getAttachmentStableKey(att)}`}
                  className="relative group mt-1 rounded-lg overflow-hidden border border-slate-700 hover:border-slate-500"
                >
                  <CachedImage
                    source={{
                      ...att,
                      attachmentId: att.id,
                    }}
                    src={att.url}
                    className="w-full h-24 object-cover bg-slate-900"
                    alt={
                      msg.role === Role.USER
                        ? idx === 0
                          ? '人物图'
                          : '服装图'
                        : `试衣结果 ${idx + 1}`
                    }
                  />
                  {/* 标签 */}
                  <div className="absolute bottom-1 left-1 bg-black/60 text-[10px] text-slate-300 px-1.5 py-0.5 rounded">
                    {msg.role === Role.USER
                      ? idx === 0
                        ? '👤 人物'
                        : '👕 服装'
                      : `结果 ${idx + 1}`}
                  </div>
                </div>
              ))}

              {/* 多图标识 */}
              {msg.role === Role.MODEL && (msg.attachments?.length || 0) > 1 && (
                <div className="mt-2 text-[10px] text-slate-500 flex items-center gap-1">
                  <Layers size={10} />
                  {msg.attachments?.length} 张图片
                </div>
              )}

              {msg.isError && (
                <div className="flex items-center gap-2 text-red-400 text-xs mt-1">
                  <AlertCircle size={12} /> 生成失败
                </div>
              )}
            </div>
            <div className="text-[10px] text-slate-500 px-1">
              {formatTryOnHistoryTime(msg.timestamp)}
            </div>
          </div>
        );
      })}

      {/* 加载状态 */}
      {isLoading && (
        <div className="flex items-start gap-2">
          <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center flex-shrink-0">
            <Shirt size={16} className="text-rose-400" />
          </div>
          <div className="bg-slate-800/50 rounded-xl p-3 text-xs text-slate-400 flex-1">
            <div className="font-medium mb-1 animate-pulse">
              {loadingState === 'uploading' ? '上传图片中...' : 'AI 正在生成试衣结果...'}
            </div>
          </div>
        </div>
      )}

      {/* 空状态提示 */}
      {messages.length === 0 && !isLoading && (
        <div className="text-center py-10 text-slate-500 text-xs">
          <p>上传人物图和服装图开始试衣</p>
          <p className="mt-1 opacity-60">第一张图为人物，第二张图为服装</p>
        </div>
      )}
    </div>
  );
});
