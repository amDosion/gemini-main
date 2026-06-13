// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactFlowInstance } from 'reactflow';
import { useWorkflowImageExport } from './useWorkflowImageExport';

const { getNodesBoundsMock, toPngMock, toSvgMock, triggerBrowserDownloadMock } = vi.hoisted(
  () => ({
    getNodesBoundsMock: vi.fn(),
    toPngMock: vi.fn(),
    toSvgMock: vi.fn(),
    triggerBrowserDownloadMock: vi.fn(),
  })
);

vi.mock('reactflow', () => ({
  getNodesBounds: getNodesBoundsMock,
}));

vi.mock('html-to-image', () => ({
  toPng: toPngMock,
  toSvg: toSvgMock,
}));

vi.mock('../../../services/downloadService', () => ({
  triggerBrowserDownload: triggerBrowserDownloadMock,
}));

describe('useWorkflowImageExport', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    getNodesBoundsMock.mockReset();
    toPngMock.mockReset();
    toSvgMock.mockReset();
    triggerBrowserDownloadMock.mockReset();

    getNodesBoundsMock.mockReturnValue({
      x: 10,
      y: 20,
      width: 200,
      height: 100,
    });
    toPngMock.mockResolvedValue('data:image/png;base64,workflow-export');
  });

  it('routes generated workflow image downloads through the shared browser download service', async () => {
    const wrapper = document.createElement('div');
    wrapper.innerHTML = '<div class="react-flow"><div class="react-flow__viewport"></div></div>';
    document.body.appendChild(wrapper);

    const reactFlowInstance = {
      getNodes: () => [{ id: 'node-1', position: { x: 0, y: 0 }, data: {} }],
    } as unknown as ReactFlowInstance;
    const addLog = vi.fn();

    const { result } = renderHook(() =>
      useWorkflowImageExport({
        reactFlowInstance,
        reactFlowWrapperRef: { current: wrapper },
        addLog,
        setExecuteErrorBanner: vi.fn(),
      })
    );

    await act(async () => {
      await result.current.handleDownloadWorkflowImage();
    });

    expect(toPngMock).toHaveBeenCalled();
    expect(toSvgMock).not.toHaveBeenCalled();
    expect(triggerBrowserDownloadMock).toHaveBeenCalledWith({
      href: 'data:image/png;base64,workflow-export',
      fileName: expect.stringMatching(/^workflow-\d+\.png$/),
    });
    expect(addLog).toHaveBeenCalledWith(
      'system',
      '系统',
      'info',
      expect.stringContaining('已下载工作流画布图片')
    );
  });
});
