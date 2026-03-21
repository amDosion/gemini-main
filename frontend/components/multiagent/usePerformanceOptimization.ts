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
  const {
    enableMetrics = true,
    debounceDelay = 300,
    largeWorkflowThreshold = 50,
  } = options;

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
    <T,>(fn: () => T, delay: number = debounceDelay) => {
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
      
      console.log(`[Performance] ${label}: ${(end - start).toFixed(2)}ms`);
    },
    [enableMetrics]
  );

  // Update metrics
  useEffect(() => {
    if (!enableMetrics) return;

    const updateMetrics = () => {
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

      requestAnimationFrame(updateMetrics);
    };

    const rafId = requestAnimationFrame(updateMetrics);
    return () => cancelAnimationFrame(rafId);
  }, [nodes.length, edges.length, enableMetrics]);

  // Log performance warnings
  useEffect(() => {
    if (!enableMetrics) return;

    if (nodes.length > 100) {
      console.warn(
        `[Performance] Large workflow detected: ${nodes.length} nodes. Consider enabling virtualization.`
      );
    }

    if (metrics.fps < 30) {
      console.warn(
        `[Performance] Low FPS detected: ${metrics.fps}. Performance may be degraded.`
      );
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
export const useMemoizedComputation = <T,>(
  computation: () => T,
  dependencies: any[]
): T => {
  const cache = useRef<{ deps: any[]; result: T } | null>(null);

  if (
    !cache.current ||
    !dependencies.every((dep, i) => dep === cache.current!.deps[i])
  ) {
    cache.current = {
      deps: dependencies,
      result: computation(),
    };
  }

  return cache.current.result;
};

// Throttle helper
export const useThrottle = <T extends (...args: any[]) => any>(
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
