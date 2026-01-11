/**
 * Ollama 模型管理类型定义
 */

/**
 * 模型详情信息
 */
export interface OllamaModelDetails {
    format: string;            // 格式 (如 "gguf")
    family: string;            // 模型家族 (如 "llama")
    parameter_size: string;    // 参数量 (如 "8B")
    quantization_level: string; // 量化级别 (如 "Q4_K_M")
}

/**
 * 本地模型信息
 */
export interface OllamaModel {
    name: string;              // 模型名称 (如 "llama3:latest")
    model: string;             // 模型标识符
    size: number;              // 模型大小 (bytes)
    digest: string;            // SHA256 摘要
    modified_at: string;       // 修改时间 (ISO 8601)
    details: OllamaModelDetails;
}

/**
 * 模型详细信息 (从 /api/show 获取)
 */
export interface OllamaModelInfo {
    modelfile: string;         // Modelfile 内容
    parameters: string;        // 参数字符串
    template: string;          // 提示词模板
    details: OllamaModelDetails;
    model_info: Record<string, unknown>;  // 模型架构信息
    capabilities: string[];    // 能力列表 (如 ["completion", "vision"])
}

/**
 * 模型下载进度
 */
export interface PullProgress {
    status: string;           // 状态描述
    digest?: string;          // 当前下载的文件摘要
    total?: number;           // 总大小 (bytes)
    completed?: number;       // 已完成大小 (bytes)
    error?: string;           // 错误信息 (如果失败)
}

/**
 * 模型列表响应
 */
export interface OllamaModelsResponse {
    models: OllamaModel[];
}

/**
 * 模型删除响应
 */
export interface DeleteModelResponse {
    success: boolean;
    message: string;
}

/**
 * 模型下载请求
 */
export interface PullModelRequest {
    model: string;
    base_url: string;
    api_key?: string;
}
