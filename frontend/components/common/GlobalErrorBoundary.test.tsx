// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';

const telemetryMocks = vi.hoisted(() => ({
  captureFrontendError: vi.fn(),
}));

vi.mock('../../services/frontendTelemetry', () => ({
  captureFrontendError: telemetryMocks.captureFrontendError,
}));

import { GlobalErrorBoundary } from './GlobalErrorBoundary';

const ThrowOnRender: React.FC = () => {
  throw new Error('render failed in test');
};

describe('GlobalErrorBoundary', () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    consoleErrorSpy.mockRestore();
  });

  it('catches render errors and shows fallback UI', () => {
    render(
      <GlobalErrorBoundary>
        <ThrowOnRender />
      </GlobalErrorBoundary>,
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('应用遇到问题')).toBeInTheDocument();
    expect(screen.getByText('重试渲染')).toBeInTheDocument();
    expect(telemetryMocks.captureFrontendError).toHaveBeenCalledTimes(1);
    expect(telemetryMocks.captureFrontendError).toHaveBeenCalledWith(
      expect.any(Error),
      expect.objectContaining({
        boundary: 'GlobalErrorBoundary',
        componentStack: expect.any(String),
      }),
    );
  });
});

