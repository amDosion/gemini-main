// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// mcpConfigService.getConfig drives parseMcpServerOptions (the parser is module-private,
// so we exercise it through the rendered MCP menu). A controllable mock lets each test
// feed a specific configJson string and assert the parsed/filtered/sorted result.
const getConfigMock = vi.hoisted(() => vi.fn());

vi.mock('../../../services/mcpConfigService', () => ({
  default: { getConfig: getConfigMock },
}));

import { ChatControls } from './ChatControls';
import type { ChatControlsProps } from '../../types';
import type { ModelConfig } from '../../../types/types';

const chatModel: ModelConfig = {
  id: 'gemini-2.5-flash',
  name: 'Gemini 2.5 Flash',
  description: '',
  capabilities: {
    vision: true,
    search: true,
    reasoning: true,
    coding: true,
  },
};

const imagenModel: ModelConfig = {
  id: 'imagen-3.0-generate',
  name: 'Imagen 3',
  description: '',
  capabilities: {
    vision: false,
    search: false,
    reasoning: false,
    coding: false,
  },
};

const baseProps = (): ChatControlsProps => ({
  currentModel: chatModel,
  enableSearch: false,
  setEnableSearch: vi.fn(),
  enableThinking: false,
  setEnableThinking: vi.fn(),
  enableCodeExecution: false,
  setEnableCodeExecution: vi.fn(),
  enableUrlContext: false,
  setEnableUrlContext: vi.fn(),
  enableEnhancedRetrieval: false,
  setEnableEnhancedRetrieval: vi.fn(),
  enableDeepResearch: false,
  setEnableDeepResearch: vi.fn(),
  enableAutoDeepResearch: false,
  setEnableAutoDeepResearch: vi.fn(),
  deepResearchAgentId: '',
  setDeepResearchAgentId: vi.fn(),
});

const renderControls = (overrides: Partial<ChatControlsProps> = {}) => {
  const props = { ...baseProps(), ...overrides };
  return { props, ...render(<ChatControls {...props} />) };
};

beforeEach(() => {
  // Default: empty config so loadMcpServers resolves to no servers unless a test overrides it.
  getConfigMock.mockReset();
  getConfigMock.mockResolvedValue({ configJson: '{}' });
});

afterEach(() => {
  cleanup();
});

describe('Google ChatControls — rendering', () => {
  it('renders the capability toolbar with search/url/thinking/code buttons enabled for a capable model', () => {
    renderControls();

    const search = screen.getByTitle('联网搜索');
    const url = screen.getByTitle('URL 上下文读取');
    const thinking = screen.getByTitle('推理模式');
    const code = screen.getByTitle('代码执行');

    expect(search).toBeInTheDocument();
    expect(search).not.toBeDisabled();
    expect(url).not.toBeDisabled();
    expect(thinking).not.toBeDisabled();
    expect(code).not.toBeDisabled();
  });

  it('disables search/thinking/code buttons when the model lacks the capability', () => {
    renderControls({
      currentModel: {
        ...chatModel,
        capabilities: { vision: true, search: false, reasoning: false, coding: false },
      },
    });

    expect(screen.getByTitle('联网搜索')).toBeDisabled();
    expect(screen.getByTitle('推理模式')).toBeDisabled();
    expect(screen.getByTitle('代码执行')).toBeDisabled();
  });

  it('hides research/url/mcp affordances for imagen/veo models', () => {
    renderControls({
      currentModel: imagenModel,
      setSelectedMcpServerKey: vi.fn(),
      enableEnhancedRetrieval: false,
    });

    // URL context button is rendered but disabled for imagen.
    expect(screen.getByTitle('URL 上下文读取')).toBeDisabled();
    // Research buttons are not rendered at all for imagen.
    expect(screen.queryByTitle('增强检索')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Deep Research')).not.toBeInTheDocument();
    // MCP selector is disabled for imagen.
    expect(screen.getByTitle('MCP 工具选择')).toBeDisabled();
  });

  it('only shows the cache toggle for gemini models when setGoogleCacheMode is provided', () => {
    const { unmount } = renderControls({
      setGoogleCacheMode: vi.fn(),
      googleCacheMode: 'none',
    });
    expect(screen.getByTitle('上下文缓存：关闭')).toBeInTheDocument();
    unmount();
    cleanup();

    // Without the setter, no cache toggle is rendered.
    renderControls({ googleCacheMode: 'none' });
    expect(screen.queryByTitle('上下文缓存：关闭')).not.toBeInTheDocument();
  });
});

describe('Google ChatControls — capability toggles', () => {
  it('toggles search on when enabled and capable', () => {
    const setEnableSearch = vi.fn();
    renderControls({ setEnableSearch, enableSearch: false });

    fireEvent.click(screen.getByTitle('联网搜索'));
    expect(setEnableSearch).toHaveBeenCalledWith(true);
  });

  it('does not toggle search when the model cannot search', () => {
    const setEnableSearch = vi.fn();
    renderControls({
      setEnableSearch,
      currentModel: {
        ...chatModel,
        capabilities: { vision: true, search: false, reasoning: true, coding: true },
      },
    });

    fireEvent.click(screen.getByTitle('联网搜索'));
    expect(setEnableSearch).not.toHaveBeenCalled();
  });

  it('cycles the google cache mode none -> exact -> semantic -> none', () => {
    const setGoogleCacheMode = vi.fn();
    const { rerender } = render(
      <ChatControls {...baseProps()} setGoogleCacheMode={setGoogleCacheMode} googleCacheMode="none" />
    );

    fireEvent.click(screen.getByTitle('上下文缓存：关闭'));
    expect(setGoogleCacheMode).toHaveBeenLastCalledWith('exact');

    rerender(
      <ChatControls
        {...baseProps()}
        setGoogleCacheMode={setGoogleCacheMode}
        googleCacheMode="exact"
      />
    );
    fireEvent.click(screen.getByTitle('上下文缓存：精确匹配'));
    expect(setGoogleCacheMode).toHaveBeenLastCalledWith('semantic');

    rerender(
      <ChatControls
        {...baseProps()}
        setGoogleCacheMode={setGoogleCacheMode}
        googleCacheMode="semantic"
      />
    );
    fireEvent.click(screen.getByTitle('上下文缓存：语义匹配'));
    expect(setGoogleCacheMode).toHaveBeenLastCalledWith('none');
  });
});

describe('Google ChatControls — mutually exclusive research modes', () => {
  it('turning on enhanced retrieval turns off deep research', () => {
    const setEnableEnhancedRetrieval = vi.fn();
    const setEnableDeepResearch = vi.fn();
    renderControls({
      enableEnhancedRetrieval: false,
      enableDeepResearch: true,
      setEnableEnhancedRetrieval,
      setEnableDeepResearch,
    });

    fireEvent.click(screen.getByTitle('增强检索'));
    expect(setEnableEnhancedRetrieval).toHaveBeenCalledWith(true);
    expect(setEnableDeepResearch).toHaveBeenCalledWith(false);
  });

  it('turning on deep research turns off enhanced retrieval and auto deep research', () => {
    const setEnableEnhancedRetrieval = vi.fn();
    const setEnableDeepResearch = vi.fn();
    const setEnableAutoDeepResearch = vi.fn();
    renderControls({
      enableDeepResearch: false,
      enableEnhancedRetrieval: true,
      enableAutoDeepResearch: true,
      setEnableDeepResearch,
      setEnableEnhancedRetrieval,
      setEnableAutoDeepResearch,
    });

    fireEvent.click(screen.getByTitle('Deep Research'));
    expect(setEnableDeepResearch).toHaveBeenCalledWith(true);
    expect(setEnableEnhancedRetrieval).toHaveBeenCalledWith(false);
    expect(setEnableAutoDeepResearch).toHaveBeenCalledWith(false);
  });

  it('selecting an auto deep research model activates auto mode and disables manual deep research', () => {
    const setDeepResearchAgentId = vi.fn();
    const setEnableAutoDeepResearch = vi.fn();
    const setEnableDeepResearch = vi.fn();
    renderControls({
      enableDeepResearch: true,
      setDeepResearchAgentId,
      setEnableAutoDeepResearch,
      setEnableDeepResearch,
      deepResearchModelCandidates: [
        { ...chatModel, id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro' },
      ],
    });

    // Open the auto-deep-research menu.
    fireEvent.click(screen.getByTitle('自动深挖（选择模型即启用）'));
    fireEvent.click(screen.getByText('Gemini 2.5 Pro'));

    expect(setDeepResearchAgentId).toHaveBeenCalledWith('gemini-2.5-pro');
    expect(setEnableAutoDeepResearch).toHaveBeenCalledWith(true);
    expect(setEnableDeepResearch).toHaveBeenCalledWith(false);
  });
});

describe('Google ChatControls — persona menu', () => {
  const personas = [
    {
      id: 'p-zeta',
      name: 'Zeta Persona',
      description: 'last alpha',
      icon: 'Brain',
      systemPrompt: '',
      category: 'general',
    },
    {
      id: 'p-alpha',
      name: 'Alpha Persona',
      description: 'first alpha',
      icon: 'Code2',
      systemPrompt: '',
      category: 'general',
    },
  ];

  it('opens the persona menu and selecting a persona invokes onSelectPersona and closes the menu', () => {
    const onSelectPersona = vi.fn();
    renderControls({ personas, activePersonaId: 'p-alpha', onSelectPersona });

    fireEvent.click(screen.getByTitle('Alpha Persona'));
    expect(screen.getByText('选择 AI 角色')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Zeta Persona'));
    expect(onSelectPersona).toHaveBeenCalledWith('p-zeta');
    expect(screen.queryByText('选择 AI 角色')).not.toBeInTheDocument();
  });

  it('disables the persona button when there are no personas', () => {
    renderControls({ personas: [], onSelectPersona: vi.fn() });
    expect(screen.getByTitle('AI 角色选择')).toBeDisabled();
  });
});

describe('Google ChatControls — MCP config parsing (parseMcpServerOptions via the menu)', () => {
  const openMcpMenu = () => fireEvent.click(screen.getByTitle('MCP 工具选择'));

  it('parses the mcpServers map, filters invalid/disabled servers, and sorts by label', async () => {
    getConfigMock.mockResolvedValue({
      configJson: JSON.stringify({
        mcpServers: {
          // valid stdio (has command)
          zulu: { command: 'run-zulu', name: 'Zulu Tools' },
          // valid http (has url)
          alpha: { url: 'https://alpha.example/mcp', name: 'Alpha Tools' },
          // invalid stdio: no command
          broken: { serverType: 'stdio' },
          // disabled -> filtered out even though valid
          off: { command: 'x', name: 'Off Tools', disabled: true },
          // enabled:false -> filtered out
          off2: { url: 'https://x', name: 'Off2', enabled: false },
        },
      }),
    });

    renderControls({ setSelectedMcpServerKey: vi.fn() });
    await waitFor(() => expect(getConfigMock).toHaveBeenCalled());

    openMcpMenu();
    const menu = await screen.findByText('选择 MCP 服务');
    const container = menu.parentElement as HTMLElement;

    // Both valid servers present by their display label.
    expect(within(container).getByText('Alpha Tools')).toBeInTheDocument();
    expect(within(container).getByText('Zulu Tools')).toBeInTheDocument();
    // Invalid + disabled servers are filtered out.
    expect(within(container).queryByText('Off Tools')).not.toBeInTheDocument();
    expect(within(container).queryByText('Off2')).not.toBeInTheDocument();
    expect(within(container).queryByText('broken')).not.toBeInTheDocument();

    // Sorted ascending by label: Alpha Tools must come before Zulu Tools.
    const labels = within(container)
      .getAllByText(/Tools$/)
      .map((el) => el.textContent);
    expect(labels.indexOf('Alpha Tools')).toBeLessThan(labels.indexOf('Zulu Tools'));

    // Transport metadata is surfaced (stdio for command, http for url).
    expect(within(container).getByText(/alpha · http/)).toBeInTheDocument();
    expect(within(container).getByText(/zulu · stdio/)).toBeInTheDocument();
  });

  it('treats a root-level server map (no mcpServers wrapper) as the server collection', async () => {
    getConfigMock.mockResolvedValue({
      configJson: JSON.stringify({
        bravo: { url: 'https://bravo.example', serverType: 'sse' },
      }),
    });

    renderControls({ setSelectedMcpServerKey: vi.fn() });
    await waitFor(() => expect(getConfigMock).toHaveBeenCalled());

    openMcpMenu();
    const menu = await screen.findByText('选择 MCP 服务');
    const container = menu.parentElement as HTMLElement;
    // Falls back to the key as label when no name is provided.
    expect(within(container).getByText('bravo')).toBeInTheDocument();
    expect(within(container).getByText(/bravo · sse/)).toBeInTheDocument();
  });

  it('shows the empty-state message when config JSON is invalid', async () => {
    getConfigMock.mockResolvedValue({ configJson: '{ not valid json' });

    renderControls({ setSelectedMcpServerKey: vi.fn() });
    await waitFor(() => expect(getConfigMock).toHaveBeenCalled());

    openMcpMenu();
    expect(
      await screen.findByText('暂无可用 MCP，请先在 Settings → MCP 中配置并启用服务。')
    ).toBeInTheDocument();
  });

  it('shows the empty-state message when getConfig rejects', async () => {
    getConfigMock.mockRejectedValue(new Error('network down'));

    renderControls({ setSelectedMcpServerKey: vi.fn() });
    await waitFor(() => expect(getConfigMock).toHaveBeenCalled());

    openMcpMenu();
    expect(
      await screen.findByText('暂无可用 MCP，请先在 Settings → MCP 中配置并启用服务。')
    ).toBeInTheDocument();
  });

  it('selecting an MCP server invokes setSelectedMcpServerKey with its key and closes the menu', async () => {
    getConfigMock.mockResolvedValue({
      configJson: JSON.stringify({
        mcpServers: { alpha: { url: 'https://alpha.example', name: 'Alpha Tools' } },
      }),
    });
    const setSelectedMcpServerKey = vi.fn();

    renderControls({ setSelectedMcpServerKey });
    await waitFor(() => expect(getConfigMock).toHaveBeenCalled());

    openMcpMenu();
    fireEvent.click(await screen.findByText('Alpha Tools'));

    expect(setSelectedMcpServerKey).toHaveBeenCalledWith('alpha');
    expect(screen.queryByText('选择 MCP 服务')).not.toBeInTheDocument();
  });

  it('resets a stale selectedMcpServerKey that no longer exists in the parsed server list', async () => {
    getConfigMock.mockResolvedValue({
      configJson: JSON.stringify({
        mcpServers: { alpha: { url: 'https://alpha.example', name: 'Alpha Tools' } },
      }),
    });
    const setSelectedMcpServerKey = vi.fn();

    renderControls({ selectedMcpServerKey: 'ghost-server', setSelectedMcpServerKey });

    // The reconciliation effect clears the selection because 'ghost-server' is absent.
    await waitFor(() => expect(setSelectedMcpServerKey).toHaveBeenCalledWith(''));
  });
});

describe('Google ChatControls — deep research model reconciliation', () => {
  it('clears a stale deepResearchAgentId and disables auto research when the model is gone', async () => {
    const setDeepResearchAgentId = vi.fn();
    const setEnableAutoDeepResearch = vi.fn();

    renderControls({
      deepResearchAgentId: 'removed-model',
      enableAutoDeepResearch: true,
      deepResearchModelCandidates: [{ ...chatModel, id: 'still-here', name: 'Still Here' }],
      setDeepResearchAgentId,
      setEnableAutoDeepResearch,
    });

    await waitFor(() => expect(setDeepResearchAgentId).toHaveBeenCalledWith(''));
    expect(setEnableAutoDeepResearch).toHaveBeenCalledWith(false);
  });
});
