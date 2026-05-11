/**
 * Performance Optimization Hook
 *
 * Provides performance optimization utilities for large workflows:
 * - Virtualization for large node counts
 * - Debounced updates
 * - Memoization helpers
 * - Performance monitoring
 */

import { useCallback, useRef, useEffect, useState } from 'react';
import { Node, Edge } from 'reactflow';

interface PerformanceMetrics {
  nodeCount: number;
  edgeCount: number;
  renderTime: number;
  updateTime: number;
  fps: number;
}

interface UsePerformanceOptimizationOptions {
  enableMetrics?: boolean;
  debounceDelay?: number;
  largeWorkflowThreshold?: number;
}

interface UsePerformanceOptimizationResult {
  metrics: PerformanceMetrics;
  isLargeWorkflow: boolean;
  debouncedUpdate: <T>(fn: () => T, delay?: number) => void;
  measurePerformance: (label: string, fn: () => void) => void;
}

export const usePerformanceOptimization = (
  nodes: Node[],
  edges: Edge[],
  options: UsePerformanceOptimizationOptions = {}
): UsePerformanceOptimizationResult => {
  const { enableMetrics = true, debounceDelay = 300, largeWorkflowThreshold = 50 } = options;

  const [metrics, setMetrics] = useState<PerformanceMetrics>({
    nodeCount: 0,
    edgeCount: 0,
    renderTime: 0,
    updateTime: 0,
    fps: 60,
  });

  const debounceTimers = useRef<Map<string, NodeJS.Timeout>>(new Map());
  const frameCount = useRef(0);
  const lastFrameTime = useRef(Date.now());

  // Check if workflow is large
  const isLargeWorkflow = nodes.length > largeWorkflowThreshold;

  // Debounced update function
  const debouncedUpdate = useCallback(
    <T>(fn: () => T, delay: number = debounceDelay) => {
      const timerId = setTimeout(() => {
        fn();
      }, delay);

      return () => clearTimeout(timerId);
    },
    [debounceDelay]
  );

  // Performance measurement
  const measurePerformance = useCallback(
    (label: string, fn: () => void) => {
      if (!enableMetrics) {
        fn();
        return;
      }

      const start = performance.now();
      fn();
      const end = performance.now();
    },
    [enableMetrics]
  );

  // Update metrics — rAF 递归用 stopped flag + 最新 currentRafId 让 cleanup 真正中断
  // （修原：cleanup 仅 cancel 第一个 rafId，递归内部启动的新 rafId 未被跟踪 → StrictMode
  //  双 mount 或 deps 变化时上一条 rAF 链继续跑，可能产生重复 metric 计算）
  useEffect(() => {
    if (!enableMetrics) return;
    let stopped = false;
    let currentRafId: number | null = null;
    const updateMetrics = () => {
      if (stopped) return;
      const now = Date.now();
      const delta = now - lastFrameTime.current;

      if (delta >= 1000) {
        const fps = Math.round((frameCount.current * 1000) / delta);

        setMetrics((prev) => ({
          ...prev,
          nodeCount: nodes.length,
          edgeCount: edges.length,
          fps,
        }));

        frameCount.current = 0;
        lastFrameTime.current = now;
      } else {
        frameCount.current++;
      }

      currentRafId = requestAnimationFrame(updateMetrics);
    };
    currentRafId = requestAnimationFrame(updateMetrics);
    return () => {
      stopped = true;
      if (currentRafId !== null) cancelAnimationFrame(currentRafId);
    };
  }, [nodes.length, edges.length, enableMetrics]);

  // Log performance warnings
  useEffect(() => {
    if (!enableMetrics) return;

    if (nodes.length > 100) {
    }

    if (metrics.fps < 30) {
    }
  }, [nodes.length, metrics.fps, enableMetrics]);

  return {
    metrics,
    isLargeWorkflow,
    debouncedUpdate,
    measurePerformance,
  };
};

// Memoization helper for expensive computations
export const useMemoizedComputation = <T>(computation: () => T, dependencies: unknown[]): T => {
  const cache = useRef<{ deps: unknown[]; result: T } | null>(null);

  if (!cache.current || !dependencies.every((dep, i) => dep === cache.current!.deps[i])) {
    cache.current = {
      deps: dependencies,
      result: computation(),
    };
  }

  return cache.current.result;
};

// Throttle helper
export const useThrottle = <T extends (...args: unknown[]) => unknown>(
  callback: T,
  delay: number
): T => {
  const lastRun = useRef(Date.now());

  return useCallback(
    ((...args) => {
      const now = Date.now();
      if (now - lastRun.current >= delay) {
        lastRun.current = now;
        return callback(...args);
      }
    }) as T,
    [callback, delay]
  );
};

export default usePerformanceOptimization;
