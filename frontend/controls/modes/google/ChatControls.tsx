import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Globe, Brain, BrainCircuit, Code2, Link2, MonitorDot, Zap, Database, Search, UserCircle2, Wrench, Sparkles } from 'lucide-react';
import { ChatControlsProps } from '../../types';
import { getPersonaIcon } from '../../../utils/iconUtils';
import mcpConfigService from '../../../services/mcpConfigService';

interface IconButtonProps {
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  title: string;
  activeClass: string;
}

const IconButton: React.FC<IconButtonProps> = ({
  active,
  disabled = false,
  onClick,
  icon,
  title,
  activeClass
}) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`grid place-items-center h-9 w-9 rounded-xl shrink-0 transition-colors ${
        disabled
          ? 'text-slate-600 cursor-not-allowed opacity-40'
          : active
            ? `${activeClass} text-white`
            : 'text-slate-400 hover:bg-slate-800/70 hover:text-slate-100'
      }`}
    >
      {icon}
    </button>
  );
};

type JsonObject = Record<string, any>;
type TransportType = 'stdio' | 'sse' | 'http' | 'streamable-http' | 'unknown';
type MenuPosition = { top: number; left: number; maxHeight: number };

interface McpServerOption {
  key: string;
  label: string;
  transport: TransportType;
}

const isPlainObject = (value: unknown): value is JsonObject =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const isRootServerMap = (root: JsonObject): boolean => {
  const entries = Object.entries(root);
  if (entries.length === 0) return false;
  return entries.every(([, value]) => isPlainObject(value));
};

const detectTransport = (config: JsonObject): TransportType => {
  const explicit = String(
    config.serverType ?? config.server_type ?? config.type ?? ''
  ).trim().toLowerCase();

  if (explicit === 'stdio' || explicit === 'sse' || explicit === 'http') {
    return explicit;
  }
  if (explicit === 'streamablehttp' || explicit === 'streamable_http' || explicit === 'streamable-http') {
    return 'streamable-http';
  }
  if (config.command) return 'stdio';
  if (config.url) return 'http';
  return 'unknown';
};

const isValidServerConfig = (transport: TransportType, config: JsonObject): boolean => {
  if (transport === 'stdio') return !!String(config.command || '').trim();
  if (transport === 'sse' || transport === 'http' || transport === 'streamable-http') {
    return !!String(config.url || '').trim();
  }
  return false;
};

const parseMcpServerOptions = (configJson: string): McpServerOption[] => {
  try {
    const parsed = JSON.parse((configJson || '').trim() || '{}');
    if (!isPlainObject(parsed)) return [];

    let serverMap: Record<string, JsonObject> = {};
    if (isPlainObject(parsed.mcpServers)) {
      Object.entries(parsed.mcpServers).forEach(([key, value]) => {
        if (isPlainObject(value)) serverMap[key] = value;
      });
    } else if (isRootServerMap(parsed)) {
      Object.entries(parsed).forEach(([key, value]) => {
        if (isPlainObject(value)) serverMap[key] = value;
      });
    }

    return Object.entries(serverMap)
      .filter(([, config]) => !(config.disabled === true || config.enabled === false))
      .map(([key, config]) => {
        const label = typeof config.name === 'string' && config.name.trim() ? config.name.trim() : key;
        const transport = detectTransport(config);
        return { key, label, transport, valid: isValidServerConfig(transport, config) };
      })
      .filter((item) => item.valid)
      .map(({ key, label, transport }) => ({ key, label, transport }))
      .sort((a, b) => a.label.localeCompare(b.label));
  } catch {
    return [];
  }
};

export const ChatControls: React.FC<ChatControlsProps> = ({
  currentModel,
  personas = [],
  activePersonaId,
  onSelectPersona,
  selectedMcpServerKey = '',
  setSelectedMcpServerKey,
  enableSearch, setEnableSearch,
  enableThinking, setEnableThinking,
  enableCodeExecution, setEnableCodeExecution,
  enableUrlContext, setEnableUrlContext,
  enableBrowser, setEnableBrowser,
  enableRAG, setEnableRAG,
  enableEnhancedRetrieval, setEnableEnhancedRetrieval,
  enableDeepResearch, setEnableDeepResearch,
  enableAutoDeepResearch, setEnableAutoDeepResearch,
  deepResearchAgentId, setDeepResearchAgentId,
  deepResearchModelCandidates = [],
  onOpenDocuments,
  googleCacheMode = 'none', setGoogleCacheMode
}) => {
  const canSearch = currentModel?.capabilities.search || false;
  const canThink = currentModel?.capabilities.reasoning || false;
  const canCode = currentModel?.capabilities.coding || false;
  const canUrlContext = !currentModel?.id.includes('imagen') && !currentModel?.id.includes('veo');
  const canBrowse = !currentModel?.id.includes('imagen') && !currentModel?.id.includes('veo') && setEnableBrowser;
  const canRAG = !currentModel?.id.includes('imagen') && !currentModel?.id.includes('veo') && setEnableRAG;
  const canResearch = !currentModel?.id.includes('imagen') && !currentModel?.id.includes('veo');
  const canCache = currentModel?.id.includes('gemini') && setGoogleCacheMode;
  const canSelectPersona = typeof onSelectPersona === 'function' && personas.length > 0;
  const canSelectMcp = !currentModel?.id.includes('imagen') && !currentModel?.id.includes('veo') && typeof setSelectedMcpServerKey === 'function';
  const [isPersonaMenuOpen, setIsPersonaMenuOpen] = useState(false);
  const [isMcpMenuOpen, setIsMcpMenuOpen] = useState(false);
  const [isAutoResearchMenuOpen, setIsAutoResearchMenuOpen] = useState(false);
  const [personaMenuPosition, setPersonaMenuPosition] = useState<MenuPosition | null>(null);
  const [mcpMenuPosition, setMcpMenuPosition] = useState<MenuPosition | null>(null);
  const [autoResearchMenuPosition, setAutoResearchMenuPosition] = useState<MenuPosition | null>(null);
  const [mcpServers, setMcpServers] = useState<McpServerOption[]>([]);
  const personaButtonRef = useRef<HTMLButtonElement>(null);
  const personaMenuRef = useRef<HTMLDivElement>(null);
  const mcpButtonRef = useRef<HTMLButtonElement>(null);
  const mcpMenuRef = useRef<HTMLDivElement>(null);
  const autoResearchButtonRef = useRef<HTMLButtonElement>(null);
  const autoResearchMenuRef = useRef<HTMLDivElement>(null);

  const activePersona = useMemo(
    () => personas.find((persona) => persona.id === activePersonaId) || personas[0],
    [personas, activePersonaId]
  );
  const activeMcpServer = useMemo(
    () => mcpServers.find((server) => server.key === selectedMcpServerKey),
    [mcpServers, selectedMcpServerKey]
  );
  const activeDeepResearchModel = useMemo(
    () => deepResearchModelCandidates.find((model) => model.id === deepResearchAgentId),
    [deepResearchModelCandidates, deepResearchAgentId]
  );
  const ActivePersonaIcon = useMemo(
    () => getPersonaIcon(activePersona?.icon || 'User'),
    [activePersona?.icon]
  );

  const cycleCacheMode = () => {
    if (!setGoogleCacheMode) return;
    if (googleCacheMode === 'none') setGoogleCacheMode('exact');
    else if (googleCacheMode === 'exact') setGoogleCacheMode('semantic');
    else setGoogleCacheMode('none');
  };

  const getCacheTitle = () => {
    if (googleCacheMode === 'exact') return '上下文缓存：精确匹配';
    if (googleCacheMode === 'semantic') return '上下文缓存：语义匹配';
    return '上下文缓存：关闭';
  };

  const toggleEnhancedRetrieval = useCallback(() => {
    const next = !enableEnhancedRetrieval;
    setEnableEnhancedRetrieval(next);
    if (next && enableDeepResearch) {
      setEnableDeepResearch(false);
    }
  }, [
    enableDeepResearch,
    enableEnhancedRetrieval,
    setEnableDeepResearch,
    setEnableEnhancedRetrieval
  ]);

  const toggleDeepResearch = useCallback(() => {
    const next = !enableDeepResearch;
    setEnableDeepResearch(next);
    if (next && enableEnhancedRetrieval) {
      setEnableEnhancedRetrieval(false);
    }
    if (next && enableAutoDeepResearch) {
      setEnableAutoDeepResearch(false);
    }
  }, [
    enableAutoDeepResearch,
    enableDeepResearch,
    enableEnhancedRetrieval,
    setEnableAutoDeepResearch,
    setEnableDeepResearch,
    setEnableEnhancedRetrieval
  ]);

  const activateAutoDeepResearchWithModel = useCallback((modelId: string) => {
    const normalizedModelId = modelId.trim();
    if (!normalizedModelId) return;

    setDeepResearchAgentId(normalizedModelId);
    setEnableAutoDeepResearch(true);
    if (enableDeepResearch) {
      setEnableDeepResearch(false);
    }
  }, [
    enableDeepResearch,
    setDeepResearchAgentId,
    setEnableAutoDeepResearch,
    setEnableDeepResearch
  ]);

  const getMenuPosition = useCallback((button: HTMLButtonElement | null): MenuPosition | null => {
    if (!button) return null;
    const rect = button.getBoundingClientRect();
    const menuWidth = 288;
    const viewportPadding = 8;
    let left = rect.right - menuWidth;
    if (left < viewportPadding) left = viewportPadding;
    if (left + menuWidth > window.innerWidth - viewportPadding) {
      left = Math.max(viewportPadding, window.innerWidth - viewportPadding - menuWidth);
    }

    return {
      top: rect.top - 8,
      left,
      maxHeight: Math.max(72, Math.min(320, rect.top - 24)),
    };
  }, []);

  const updatePersonaMenuPosition = useCallback(() => {
    const position = getMenuPosition(personaButtonRef.current);
    setPersonaMenuPosition(position);
  }, [getMenuPosition]);

  const updateMcpMenuPosition = useCallback(() => {
    const position = getMenuPosition(mcpButtonRef.current);
    setMcpMenuPosition(position);
  }, [getMenuPosition]);

  const updateAutoResearchMenuPosition = useCallback(() => {
    const position = getMenuPosition(autoResearchButtonRef.current);
    setAutoResearchMenuPosition(position);
  }, [getMenuPosition]);

  const loadMcpServers = useCallback(async () => {
    try {
      const payload = await mcpConfigService.getConfig();
      setMcpServers(parseMcpServerOptions(payload.configJson || '{}'));
    } catch {
      setMcpServers([]);
    }
  }, []);

  useEffect(() => {
    loadMcpServers();
  }, [loadMcpServers]);

  useEffect(() => {
    if (!isMcpMenuOpen) return;
    loadMcpServers();
  }, [isMcpMenuOpen, loadMcpServers]);

  useEffect(() => {
    if (!selectedMcpServerKey || !setSelectedMcpServerKey) return;
    const exists = mcpServers.some((server) => server.key === selectedMcpServerKey);
    if (!exists) {
      setSelectedMcpServerKey('');
    }
  }, [mcpServers, selectedMcpServerKey, setSelectedMcpServerKey]);

  useEffect(() => {
    if (!deepResearchAgentId || !setDeepResearchAgentId) return;
    const exists = deepResearchModelCandidates.some((model) => model.id === deepResearchAgentId);
    if (!exists) {
      setDeepResearchAgentId('');
      if (enableAutoDeepResearch) {
        setEnableAutoDeepResearch(false);
      }
    }
  }, [
    deepResearchAgentId,
    deepResearchModelCandidates,
    enableAutoDeepResearch,
    setDeepResearchAgentId,
    setEnableAutoDeepResearch
  ]);

  useEffect(() => {
    if (!isPersonaMenuOpen) return;

    updatePersonaMenuPosition();

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (personaMenuRef.current?.contains(target)) return;
      if (personaButtonRef.current?.contains(target)) return;
      setIsPersonaMenuOpen(false);
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsPersonaMenuOpen(false);
    };
    const handleReposition = () => updatePersonaMenuPosition();

    document.addEventListener('mousedown', handleClickOutside, true);
    window.addEventListener('keydown', handleEscape);
    window.addEventListener('resize', handleReposition);
    window.addEventListener('scroll', handleReposition, true);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside, true);
      window.removeEventListener('keydown', handleEscape);
      window.removeEventListener('resize', handleReposition);
      window.removeEventListener('scroll', handleReposition, true);
    };
  }, [isPersonaMenuOpen, updatePersonaMenuPosition]);

  useEffect(() => {
    if (!isMcpMenuOpen) return;

    updateMcpMenuPosition();

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (mcpMenuRef.current?.contains(target)) return;
      if (mcpButtonRef.current?.contains(target)) return;
      setIsMcpMenuOpen(false);
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsMcpMenuOpen(false);
    };
    const handleReposition = () => updateMcpMenuPosition();

    document.addEventListener('mousedown', handleClickOutside, true);
    window.addEventListener('keydown', handleEscape);
    window.addEventListener('resize', handleReposition);
    window.addEventListener('scroll', handleReposition, true);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside, true);
      window.removeEventListener('keydown', handleEscape);
      window.removeEventListener('resize', handleReposition);
      window.removeEventListener('scroll', handleReposition, true);
    };
  }, [isMcpMenuOpen, updateMcpMenuPosition]);

  useEffect(() => {
    if (!isAutoResearchMenuOpen) return;

    updateAutoResearchMenuPosition();

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (autoResearchMenuRef.current?.contains(target)) return;
      if (autoResearchButtonRef.current?.contains(target)) return;
      setIsAutoResearchMenuOpen(false);
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsAutoResearchMenuOpen(false);
    };
    const handleReposition = () => updateAutoResearchMenuPosition();

    document.addEventListener('mousedown', handleClickOutside, true);
    window.addEventListener('keydown', handleEscape);
    window.addEventListener('resize', handleReposition);
    window.addEventListener('scroll', handleReposition, true);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside, true);
      window.removeEventListener('keydown', handleEscape);
      window.removeEventListener('resize', handleReposition);
      window.removeEventListener('scroll', handleReposition, true);
    };
  }, [isAutoResearchMenuOpen, updateAutoResearchMenuPosition]);

  return (
    <>
      <div className="mx-auto max-w-full rounded-2xl bg-slate-900/70 px-2 py-1.5 shadow-[0_6px_20px_rgba(0,0,0,0.24)]">
        <div className="flex flex-wrap items-center justify-center gap-1.5">
          <IconButton
            active={enableSearch}
            disabled={!canSearch}
            onClick={() => canSearch && setEnableSearch(!enableSearch)}
            icon={<Globe size={15} strokeWidth={2.4} />}
            activeClass="bg-blue-600"
            title="联网搜索"
          />

          {canBrowse && (
            <IconButton
              active={!!enableBrowser}
              onClick={() => setEnableBrowser && setEnableBrowser(!enableBrowser)}
              icon={<MonitorDot size={15} strokeWidth={2.4} />}
              activeClass="bg-blue-600"
              title="浏览器检索"
            />
          )}

          <IconButton
            active={enableUrlContext}
            disabled={!canUrlContext}
            onClick={() => canUrlContext && setEnableUrlContext(!enableUrlContext)}
            icon={<Link2 size={15} strokeWidth={2.4} />}
            activeClass="bg-blue-600"
            title="URL 上下文读取"
          />

          {canResearch && (
            <IconButton
              active={enableEnhancedRetrieval}
              disabled={!canResearch}
              onClick={toggleEnhancedRetrieval}
              icon={<Search size={15} strokeWidth={2.4} />}
              activeClass="bg-blue-600"
              title="增强检索"
            />
          )}

          {canResearch && (
            <IconButton
              active={enableDeepResearch}
              disabled={!canResearch}
              onClick={toggleDeepResearch}
              icon={<BrainCircuit size={15} strokeWidth={2.4} />}
              activeClass="bg-blue-600"
              title="Deep Research"
            />
          )}

          {canResearch && (
            <button
              ref={autoResearchButtonRef}
              onClick={() => {
                setIsPersonaMenuOpen(false);
                setIsMcpMenuOpen(false);
                setIsAutoResearchMenuOpen((prev) => !prev);
              }}
              title={
                activeDeepResearchModel && enableAutoDeepResearch
                  ? `自动深挖已启用：${activeDeepResearchModel.name}`
                  : '自动深挖（选择模型即启用）'
              }
              className={`relative grid place-items-center h-9 w-9 rounded-xl shrink-0 transition-colors ${
                enableAutoDeepResearch
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:bg-slate-800/70 hover:text-slate-100'
              } ${isAutoResearchMenuOpen ? 'ring-2 ring-blue-400/60' : ''}`}
            >
              <Sparkles size={15} strokeWidth={2.4} />
            </button>
          )}

          {canRAG && (
            <IconButton
              active={!!enableRAG}
              onClick={() => {
                if (onOpenDocuments && !enableRAG) onOpenDocuments();
                setEnableRAG && setEnableRAG(!enableRAG);
              }}
              icon={<Database size={15} strokeWidth={2.4} />}
              activeClass="bg-blue-600"
              title="知识库问答"
            />
          )}

          {canCache && (
            <IconButton
              active={googleCacheMode !== 'none'}
              onClick={cycleCacheMode}
              icon={<Zap size={15} strokeWidth={2.4} className={googleCacheMode !== 'none' ? 'fill-current' : ''} />}
              activeClass="bg-blue-600"
              title={getCacheTitle()}
            />
          )}

          <IconButton
            active={enableThinking}
            disabled={!canThink}
            onClick={() => canThink && setEnableThinking(!enableThinking)}
            icon={<Brain size={15} strokeWidth={2.4} />}
            activeClass="bg-blue-600"
            title="推理模式"
          />

          <IconButton
            active={enableCodeExecution}
            disabled={!canCode}
            onClick={() => canCode && setEnableCodeExecution(!enableCodeExecution)}
            icon={<Code2 size={15} strokeWidth={2.4} />}
            activeClass="bg-blue-600"
            title="代码执行"
          />

          <button
            ref={personaButtonRef}
            onClick={() => {
              if (!canSelectPersona) return;
              setIsMcpMenuOpen(false);
              setIsAutoResearchMenuOpen(false);
              setIsPersonaMenuOpen((prev) => !prev);
            }}
            disabled={!canSelectPersona}
            title={activePersona?.name || 'AI 角色选择'}
            className={`relative grid place-items-center h-9 w-9 rounded-xl shrink-0 transition-colors ${
              canSelectPersona
                ? (activePersona || isPersonaMenuOpen)
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-300 hover:bg-slate-800/70 hover:text-slate-100'
                : 'text-slate-600 cursor-not-allowed opacity-40'
            }`}
          >
            {activePersona ? (
              <ActivePersonaIcon size={15} strokeWidth={2.4} />
            ) : (
              <UserCircle2 size={15} strokeWidth={2.4} />
            )}
          </button>

          <button
            ref={mcpButtonRef}
            onClick={() => {
              if (!canSelectMcp) return;
              setIsPersonaMenuOpen(false);
              setIsAutoResearchMenuOpen(false);
              setIsMcpMenuOpen((prev) => !prev);
            }}
            disabled={!canSelectMcp}
            title={activeMcpServer ? `MCP: ${activeMcpServer.label}` : 'MCP 工具选择'}
            className={`relative grid place-items-center h-9 w-9 rounded-xl shrink-0 transition-colors ${
              canSelectMcp
                ? (activeMcpServer || isMcpMenuOpen)
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-300 hover:bg-slate-800/70 hover:text-slate-100'
                : 'text-slate-600 cursor-not-allowed opacity-40'
            }`}
          >
            <Wrench size={15} strokeWidth={2.4} />
          </button>
        </div>
      </div>

      {isPersonaMenuOpen && canSelectPersona && personaMenuPosition && createPortal(
        <div
          ref={personaMenuRef}
          className="fixed z-[9999] w-72 max-w-[92vw] rounded-xl border border-slate-700 bg-slate-900 shadow-2xl p-1"
          style={{ top: personaMenuPosition.top, left: personaMenuPosition.left, transform: 'translateY(-100%)', transformOrigin: 'bottom right' }}
        >
          <div className="px-3 py-2 text-[11px] text-slate-400 border-b border-slate-800">
            选择 AI 角色
          </div>
          <div className="overflow-y-auto custom-scrollbar py-1" style={{ maxHeight: personaMenuPosition.maxHeight }}>
            {personas.map((persona) => {
              const selected = persona.id === activePersona?.id;
              return (
                <button
                  key={persona.id}
                  onClick={() => {
                    onSelectPersona?.(persona.id);
                    setIsPersonaMenuOpen(false);
                  }}
                  title={`切换到：${persona.name}`}
                  className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                    selected
                      ? 'bg-blue-600/20 text-blue-300'
                      : 'text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  <div className="text-xs font-medium truncate">{persona.name}</div>
                  <div className="text-[10px] text-slate-500 truncate">{persona.description}</div>
                </button>
              );
            })}
          </div>
        </div>,
        document.body
      )}

      {isMcpMenuOpen && canSelectMcp && mcpMenuPosition && createPortal(
        <div
          ref={mcpMenuRef}
          className="fixed z-[9999] w-72 max-w-[92vw] rounded-xl border border-slate-700 bg-slate-900 shadow-2xl p-1"
          style={{ top: mcpMenuPosition.top, left: mcpMenuPosition.left, transform: 'translateY(-100%)', transformOrigin: 'bottom right' }}
        >
          <div className="px-3 py-2 text-[11px] text-slate-400 border-b border-slate-800">
            选择 MCP 服务
          </div>
          <div className="overflow-y-auto custom-scrollbar py-1" style={{ maxHeight: mcpMenuPosition.maxHeight }}>
            <button
              onClick={() => {
                setSelectedMcpServerKey?.('');
                setIsMcpMenuOpen(false);
              }}
              className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                !selectedMcpServerKey
                  ? 'bg-blue-600/20 text-blue-300'
                  : 'text-slate-300 hover:bg-slate-800'
              }`}
            >
              <div className="text-xs font-medium truncate">不使用 MCP</div>
              <div className="text-[10px] text-slate-500 truncate">仅使用模型内置能力</div>
            </button>

            {mcpServers.map((server) => {
              const selected = server.key === selectedMcpServerKey;
              return (
                <button
                  key={server.key}
                  onClick={() => {
                    setSelectedMcpServerKey?.(server.key);
                    setIsMcpMenuOpen(false);
                  }}
                  title={`切换到 MCP：${server.label}`}
                  className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                    selected
                      ? 'bg-blue-600/20 text-blue-300'
                      : 'text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  <div className="text-xs font-medium truncate">{server.label}</div>
                  <div className="text-[10px] text-slate-500 truncate">
                    {server.key} · {server.transport}
                  </div>
                </button>
              );
            })}

            {mcpServers.length === 0 && (
              <div className="px-3 py-3 text-[11px] text-slate-500">
                暂无可用 MCP，请先在 Settings → MCP 中配置并启用服务。
              </div>
            )}
          </div>
        </div>,
        document.body
      )}

      {isAutoResearchMenuOpen && canResearch && autoResearchMenuPosition && createPortal(
        <div
          ref={autoResearchMenuRef}
          className="fixed z-[9999] w-80 max-w-[92vw] rounded-xl border border-slate-700 bg-slate-900 shadow-2xl p-1"
          style={{ top: autoResearchMenuPosition.top, left: autoResearchMenuPosition.left, transform: 'translateY(-100%)', transformOrigin: 'bottom right' }}
        >
          <div className="px-3 py-2 text-[11px] text-slate-400 border-b border-slate-800">
            选择模型后自动启用深挖
          </div>
          <div className="overflow-y-auto custom-scrollbar py-1" style={{ maxHeight: autoResearchMenuPosition.maxHeight }}>
            <div className="px-3 pt-2 pb-1 text-[11px] text-slate-400">
              选择自动深挖模型
            </div>

            {enableAutoDeepResearch && (
              <button
                onClick={() => {
                  setEnableAutoDeepResearch(false);
                  setIsAutoResearchMenuOpen(false);
                }}
                className="w-full text-left px-3 py-2 rounded-lg transition-colors bg-blue-600/20 text-blue-300 hover:bg-blue-600/30"
              >
                <div className="text-xs font-medium truncate">关闭自动深挖</div>
                <div className="text-[10px] text-slate-300 truncate">
                  当前模型：{activeDeepResearchModel?.name || deepResearchAgentId || '未选择'}
                </div>
              </button>
            )}

            {deepResearchModelCandidates.map((model) => {
              const selected = model.id === deepResearchAgentId;
              return (
                <button
                  key={model.id}
                  onClick={() => {
                    activateAutoDeepResearchWithModel(model.id);
                    setIsAutoResearchMenuOpen(false);
                  }}
                  className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                    selected && enableAutoDeepResearch
                      ? 'bg-blue-600/20 text-blue-300'
                      : selected
                        ? 'bg-blue-600/20 text-blue-300'
                      : 'text-slate-300 hover:bg-slate-800'
                  }`}
                  title={model.name}
                >
                  <div className="text-xs font-medium truncate">{model.name}</div>
                  <div className="text-[10px] text-slate-500 truncate">{model.id}</div>
                </button>
              );
            })}

            {deepResearchModelCandidates.length === 0 && (
              <div className="px-3 py-3 text-[11px] text-slate-500">
                当前模式下没有可用的思考型模型。
              </div>
            )}
          </div>
        </div>,
        document.body
      )}
    </>
  );
};

export default ChatControls;
