/**
 * Type Definitions for Multi-Agent Workflow Editor
 * 
 * Shared types used across all workflow components
 */

import type { Node, Edge } from 'reactflow';

// Node execution status
export type NodeStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped';

// Edge animation types
export type EdgeAnimationType = 'none' | 'pulse' | 'flow';
export type RouterStrategy = 'intent' | 'keyword' | 'llm';
export type ParallelJoinMode = 'wait_all' | 'race_first';
export type MergeStrategy = 'append' | 'json_merge' | 'latest';

export interface WorkflowNodePortLayout {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

// Custom node data interface
export interface WorkflowNodeData {
  label: string;
  description: string;
  icon: string;
  iconColor: string;
  type?: string;
  agentId?: string;
  agentName?: string;
  inlineUseActiveProfile?: boolean;
  inlineProviderId?: string;
  inlineModelId?: string;
  inlineProfileId?: string;
  inlineAgentName?: string;
  inlineSystemPrompt?: string;
  agentProviderId?: string;
  agentModelId?: string;
  modelOverrideProviderId?: string;
  modelOverrideModelId?: string;
  modelOverrideProfileId?: string;
  tools?: string[];
  // Per-node configuration
  instructions?: string;       // 节点级指令（追加到 agent system prompt）
  inputMapping?: string;       // 输入映射模板，如 {{prev.output.text}}
  // Agent task parameters
  agentTaskType?: string;      // 任务类型：chat / image-gen / image-edit / video-gen / audio-gen / data-analysis / ...
  agentTemperature?: number;   // 节点级温度覆盖
  agentMaxTokens?: number;     // 节点级最大输出 token 覆盖
  agentPreferLatestModel?: boolean; // 优先自动选择最新可用模型
  agentAspectRatio?: string;   // 图片宽高比
  agentImageSize?: string;     // 图片尺寸
  agentResolutionTier?: string; // 分辨率档位：1K / 2K / 4K
  agentNumberOfImages?: number; // 图片数量
  agentImageStyle?: string;    // 图片风格
  agentNegativePrompt?: string; // 反向提示词
  agentSeed?: number;          // 随机种子
  agentPromptExtend?: boolean; // 启用提示词优化（provider支持时生效）
  agentAddMagicSuffix?: boolean; // 启用提示词魔法后缀（provider支持时生效）
  agentVideoDurationSeconds?: number; // 视频时长（秒）
  agentVideoExtensionCount?: number; // 官方视频延长次数
  agentContinueFromPreviousVideo?: boolean; // 续接上一个视频结果
  agentContinueFromPreviousLastFrame?: boolean; // 使用上一段最后一帧作为下一段首帧
  agentSourceVideoUrl?: string; // 显式指定续接视频 URL
  agentLastFrameImageUrl?: string; // 显式指定末帧图片
  agentVideoMaskImageUrl?: string; // 视频编辑掩码图 URL
  agentVideoMaskMode?: string; // 视频编辑掩码模式
  agentGenerateAudio?: boolean; // 生成视频原生音频
  agentPersonGeneration?: string; // 人物生成策略
  agentSubtitleMode?: string; // 字幕模式
  agentSubtitleLanguage?: string; // 字幕语言
  agentSubtitleScript?: string; // 字幕脚本
  agentStoryboardPrompt?: string; // 明确分镜提示词
  agentSpeechSpeed?: number;   // 语音速度
  agentAudioFormat?: string;   // 音频格式
  agentVoice?: string;         // 语音 / 音色
  agentOutputFormat?: string;  // 输出格式：text / json / markdown
  agentOutputMimeType?: string; // 输出 MIME 类型
  agentReferenceImageUrl?: string; // 参考图片 URL（图生图）
  agentFileUrl?: string;       // 文件 URL（数据分析）
  agentEditPrompt?: string;    // 编辑指令（图片编辑）
  agentPreserveProductIdentity?: boolean;
  agentImageEditMaxRetries?: number;
  agentProductMatchThreshold?: number;
  expression?: string;         // condition 节点表达式
  routerStrategy?: RouterStrategy;
  routerPrompt?: string;
  mergeStrategy?: MergeStrategy;
  joinMode?: ParallelJoinMode;
  timeoutSeconds?: number;
  loopCondition?: string;
  maxIterations?: number;
  toolName?: string;
  toolArgsTemplate?: string;
  toolProviderId?: string;
  toolModelId?: string;
  // Tool-specific parameters (image_generate)
  toolNumberOfImages?: number;
  toolAspectRatio?: string;
  toolResolutionTier?: string;
  toolImageSize?: string;
  toolImageStyle?: string;
  toolOutputMimeType?: string;
  toolNegativePrompt?: string;
  toolPromptExtend?: boolean;
  toolAddMagicSuffix?: boolean;
  toolVideoDurationSeconds?: number;
  toolVideoExtensionCount?: number;
  toolSourceVideoUrl?: string;
  toolLastFrameImageUrl?: string;
  toolVideoMaskImageUrl?: string;
  toolVideoMaskMode?: string;
  toolGenerateAudio?: boolean;
  toolPersonGeneration?: string;
  toolSubtitleMode?: string;
  toolSubtitleLanguage?: string;
  toolSubtitleScript?: string;
  toolStoryboardPrompt?: string;
  // Tool-specific parameters (image_edit)
  toolEditMode?: string;
  toolEditPrompt?: string;
  toolReferenceImageUrl?: string;
  // Tool-specific parameters (table_analyze)
  toolAnalysisType?: string;
  approvalPrompt?: string;
  // Start node runtime input
  startTask?: string;
  startImageUrl?: string;
  startImageUrls?: string[];
  startVideoUrl?: string;
  startVideoUrls?: string[];
  startAudioUrl?: string;
  startAudioUrls?: string[];
  startFileUrl?: string;
  startFileUrls?: string[];
  continueOnError?: boolean;
  nodeWidth?: number;
  nodeHeight?: number;
  portLayout?: WorkflowNodePortLayout;
  // Execution state
  status?: NodeStatus;
  progress?: number;
  result?: unknown;
  error?: string;
  runtime?: string;
  startTime?: number;
  endTime?: number;
}

// Workflow Node type (compatible with React Flow)
export type WorkflowNode = Node<WorkflowNodeData>;

// Workflow Edge type (compatible with React Flow)
export type WorkflowEdge = Edge;

// Execution Status for workflow execution tracking
export interface ExecutionStatus {
  nodeStatuses: Record<string, NodeStatus>;
  nodeProgress: Record<string, number>;
  nodeResults: Record<string, unknown>;
  nodeErrors: Record<string, string>;
  nodeRuntimes?: Record<string, string>;
  executionId?: string;
  finalStatus?: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'workflow_paused';
  finalResult?: unknown;
  finalRuntime?: string;
  runtimeHints?: string[];
  resultPreviewImageUrls?: string[];
  resultPreviewAudioUrls?: string[];
  resultPreviewVideoUrls?: string[];
  finalError?: string;
  completedAt?: number;
  logs: Array<{
    timestamp: number;
    nodeId: string;
    message: string;
    level: 'info' | 'warn' | 'error';
  }>;
}

export interface AgentRuntimeMetadata {
  kind: string;
  label: string;
  supportsRun: boolean;
  supportsLiveRun: boolean;
  supportsSessions: boolean;
  supportsMemory: boolean;
  supportsOfficialOrchestration: boolean;
}

export interface AgentSourceMetadata {
  kind: string;
  label: string;
  isSystem: boolean;
}

// Workflow execution state
export interface WorkflowExecutionState {
  isExecuting: boolean;
  executionId: string | null;
  startTime: number | null;
  endTime: number | null;
}

// Node validation result
export interface NodeValidationResult {
  isValid: boolean;
  errors: string[];
  warnings: string[];
}

// Workflow validation result
export interface WorkflowValidationResult {
  isValid: boolean;
  nodeErrors: Record<string, string[]>;
  edgeErrors: string[];
  globalErrors: string[];
}

// Agent definition (unified across AgentManagerPanel, AgentSelector, etc.)
export interface AgentDef {
  id: string;
  name: string;
  description: string;
  agentType?: string;
  providerId: string;
  modelId: string;
  systemPrompt: string;
  temperature: number;
  maxTokens: number;
  icon: string;
  color: string;
  status: string;
  runtime?: AgentRuntimeMetadata;
  source?: AgentSourceMetadata;
  supportsRuntimeSessions?: boolean;
  supportsRuntimeLiveRun?: boolean;
  supportsRuntimeMemory?: boolean;
  supportsOfficialOrchestration?: boolean;
  agentCard?: {
    defaults?: {
      defaultTaskType?: 'chat' | 'image-gen' | 'image-edit' | 'video-gen' | 'audio-gen' | 'vision-understand' | 'data-analysis';
      imageGeneration?: {
        aspectRatio?: string;
        resolutionTier?: string;
        numberOfImages?: number;
        imageStyle?: string;
        outputMimeType?: string;
        negativePrompt?: string;
        promptExtend?: boolean;
        addMagicSuffix?: boolean;
      };
      imageEdit?: {
        editMode?: string;
        aspectRatio?: string;
        resolutionTier?: string;
        numberOfImages?: number;
        outputMimeType?: string;
        promptExtend?: boolean;
      };
      videoGeneration?: {
        aspectRatio?: string;
        resolution?: string;
        durationSeconds?: number;
        continueFromPreviousVideo?: boolean;
        continueFromPreviousLastFrame?: boolean;
      };
      audioGeneration?: {
        voice?: string;
        responseFormat?: string;
        speed?: number;
      };
      visionUnderstand?: {
        outputFormat?: string;
      };
      dataAnalysis?: {
        outputFormat?: string;
      };
      llm?: {
        providerId?: string;
        modelId?: string;
        profileId?: string;
        systemPrompt?: string;
        temperature?: number;
        maxTokens?: number;
        preferLatestModel?: boolean;
      };
    };
  };
}

// Workflow statistics
export interface WorkflowStatistics {
  totalNodes: number;
  totalEdges: number;
  nodesByType: Record<string, number>;
  executionTime?: number;
  successRate?: number;
}
