/**
 * Multi-agent workflow 节点/边数据通用字符串列表工具集。
 *
 * 1:1 抽离自 `MultiAgentWorkflowEditorReactFlow.tsx` L172-189
 * （JIRA-frontend-view-decomposition.md P1 #3 Step 2）。
 *
 * 用于处理节点数据中的字符串列表字段（结果文本、依赖节点 ID、标签等）：
 * - 容错的 array 规范化（非 array 返回空数组，元素 trim + filter Boolean）
 * - 多源去重合并（保留首次出现顺序）
 */

/**
 * 将任意输入规范化为非空字符串数组：
 * - 非 array → []
 * - 元素 String 化、trim，过滤空串
 */
export const normalizeStringList = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || '').trim()).filter(Boolean);
};

/**
 * 合并多个字符串数组，去重且保留首次出现的顺序。
 */
export const mergeUniqueStringList = (...sources: string[][]): string[] =>
  Array.from(new Set(sources.flat()));
