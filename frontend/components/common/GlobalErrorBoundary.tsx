import React from 'react';
import { captureFrontendError } from '../../services/frontendTelemetry';

interface GlobalErrorBoundaryProps {
  children: React.ReactNode;
}

interface GlobalErrorBoundaryState {
  hasError: boolean;
  retryKey: number;
}

export class GlobalErrorBoundary extends React.Component<
  GlobalErrorBoundaryProps,
  GlobalErrorBoundaryState
> {
  state: GlobalErrorBoundaryState = {
    hasError: false,
    retryKey: 0,
  };

  static getDerivedStateFromError(): Partial<GlobalErrorBoundaryState> {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    captureFrontendError(error, {
      boundary: 'GlobalErrorBoundary',
      componentStack: errorInfo?.componentStack || '',
    });
  }

  private handleRetry = () => {
    this.setState((prev) => ({
      hasError: false,
      retryKey: prev.retryKey + 1,
    }));
  };

  private handleReload = () => {
    if (typeof window !== 'undefined') {
      window.location.reload();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6">
          <section
            role="alert"
            className="w-full max-w-xl rounded-2xl border border-slate-700 bg-slate-900/90 shadow-2xl p-6 space-y-4"
          >
            <header className="space-y-2">
              <p className="text-xs uppercase tracking-[0.2em] text-rose-300">Render Recovery</p>
              <h1 className="text-2xl font-semibold">应用遇到问题</h1>
              <p className="text-sm text-slate-300">
                已拦截渲染异常，避免整个应用 shell 崩溃。你可以重试渲染或刷新页面。
              </p>
            </header>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={this.handleRetry}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors"
              >
                重试渲染
              </button>
              <button
                type="button"
                onClick={this.handleReload}
                className="px-4 py-2 rounded-lg border border-slate-600 hover:border-slate-500 hover:bg-slate-800 text-slate-200 text-sm font-medium transition-colors"
              >
                刷新页面
              </button>
            </div>
          </section>
        </div>
      );
    }

    return <React.Fragment key={this.state.retryKey}>{this.props.children}</React.Fragment>;
  }
}

export default GlobalErrorBoundary;

