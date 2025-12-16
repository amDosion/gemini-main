
import { ApiProtocol } from '../../types';

export interface AIProviderConfig {
  id: string;
  name: string;
  protocol: ApiProtocol;
  baseUrl: string;
  defaultModel?: string;
  icon?: string;
  description: string;
  isCustom?: boolean;
}

export const STATIC_AI_PROVIDERS: AIProviderConfig[] = [
  {
    id: 'google',
    name: 'Google Gemini',
    protocol: 'google',
    baseUrl: 'https://generativelanguage.googleapis.com',
    defaultModel: 'gemini-2.5-flash',
    description: 'Native Google SDK. Supports Vision, Search & Thinking.',
    icon: 'gemini'
  },
  {
    id: 'google-custom',
    name: 'Google Compatible',
    protocol: 'google',
    baseUrl: 'https://generativelanguage.googleapis.com', // Default, but editable
    defaultModel: 'gemini-2.5-flash',
    description: 'Custom Google Protocol endpoint (e.g. Vertex Proxy).',
    isCustom: true,
    icon: 'gemini'
  },
  {
    id: 'openai',
    name: 'OpenAI',
    protocol: 'openai',
    baseUrl: 'https://api.openai.com/v1',
    defaultModel: 'gpt-4o',
    description: 'Standard OpenAI API.',
    icon: 'openai'
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    protocol: 'openai',
    baseUrl: 'https://api.deepseek.com',
    defaultModel: 'deepseek-chat',
    description: 'DeepSeek V3 & R1 (Reasoning).',
    icon: 'deepseek'
  },
  {
    id: 'tongyi',
    name: 'Aliyun TongYi',
    protocol: 'openai',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    defaultModel: 'qwen-max',
    description: 'Qwen models via DashScope.',
    icon: 'qwen'
  },
  {
    id: 'siliconflow',
    name: 'SiliconFlow',
    protocol: 'openai',
    baseUrl: 'https://api.siliconflow.cn/v1',
    defaultModel: 'Qwen/Qwen2.5-7B-Instruct',
    description: 'High-performance inference (Qwen, DeepSeek, etc).',
    icon: 'silicon'
  },
  {
    id: 'moonshot',
    name: 'Moonshot',
    protocol: 'openai',
    baseUrl: 'https://api.moonshot.cn/v1',
    defaultModel: 'moonshot-v1-8k',
    description: 'Kimi AI models.',
    icon: 'moonshot'
  },
  {
    id: 'zhipu',
    name: 'ZhiPu AI',
    protocol: 'openai',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    defaultModel: 'glm-4-plus',
    description: 'ChatGLM models.',
    icon: 'glm'
  },
  {
    id: 'ollama',
    name: 'Ollama',
    protocol: 'openai',
    baseUrl: 'http://localhost:11434/v1',
    defaultModel: 'llama3',
    description: 'Local models. Ensure CORS is enabled.',
    icon: 'ollama'
  },
  {
    id: 'custom',
    name: 'Custom OpenAI',
    protocol: 'openai',
    baseUrl: '',
    description: 'Connect to any OpenAI compatible endpoint.',
    isCustom: true,
    icon: 'settings'
  }
];

// Helper to get static config
export const getStaticProviderConfig = (id: string) => STATIC_AI_PROVIDERS.find(p => p.id === id);
