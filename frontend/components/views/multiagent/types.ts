import type { WorkflowEdge, WorkflowNode } from '../../multiagent/types';

export interface WorkflowHistoryItem {
  id: string;
  status: string;
  title: string;
  source?: string;
  task: string;
  resultPreview: string;
  resultImageCount: number;
  resultImageUrls: string[];
  resultAudioCount: number;
  resultAudioUrls: string[];
  resultVideoCount: number;
  resultVideoUrls: string[];
  continuationStrategy?: string;
  videoExtensionCount?: number;
  videoExtensionApplied?: number;
  totalDurationSeconds?: number;
  continuedFromVideo?: boolean;
  subtitleMode?: string;
  subtitleFileCount?: number;
  primaryRuntime?: string;
  runtimeHints?: string[];
  startedAt: number;
  completedAt?: number;
  durationMs?: number;
  error?: string;
  nodeCount: number;
  edgeCount: number;
}

export interface WorkflowLoadRequest {
  token: string;
  name: string;
  prompt: string;
  input?: Record<string, any>;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}
