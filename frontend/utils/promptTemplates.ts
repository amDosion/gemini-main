/**
 * @file This file contains utility functions for generating prompts for the Deep Research Agent.
 * It provides structured prompt templates for various research formats to ensure consistent
 * and high-quality output from the AI model.
 */

/**
 * 研究报告输出格式的枚举
 * @enum {string}
 */
export enum ResearchFormat {
  TECHNICAL_REPORT = 'TECHNICAL_REPORT',
  MARKET_ANALYSIS = 'MARKET_ANALYSIS',
  LITERATURE_REVIEW = 'LITERATURE_REVIEW',
}

/**
 * 获取技术报告的格式化指令
 * @returns {string} 技术报告的中文指令
 */
function getTechnicalReportInstructions(): string {
  return `
请根据以下结构生成一份技术报告：
- **摘要**: 对整个报告的核心内容进行简洁明了的概述。
- **详细分析**: 对研究主题进行深入、全面的分析，包括相关数据、技术细节和背景信息。
- **关键发现**: 列出研究过程中最重要的发现和结论。
- **战略建议**: 基于分析和发现，提出具体、可行的战略建议。
- **参考文献**: 注明所有引用的信息来源。
`;
}

/**
 * 获取市场分析报告的格式化指令
 * @returns {string} 市场分析报告的中文指令
 */
function getMarketAnalysisInstructions(): string {
  return `
请根据以下结构生成一份市场分析报告：
- **市场规模**: 评估当前市场的总体规模和增长潜力。
- **竞争格局**: 分析主要竞争对手及其市场份额、优势和劣势。
- **技术趋势**: 识别并分析影响市场的关键技术趋势。
- **投资机会**: 指出潜在的投资机会和相关风险。
`;
}

/**
 * 获取文献综述的格式化指令
 * @returns {string} 文献综述的中文指令
 */
function getLiteratureReviewInstructions(): string {
  return `
请根据以下结构生成一份文献综述：
- **研究背景**: 介绍相关研究领域的背景和重要性。
- **主要方法**: 概述该领域常用的研究方法和技术。
- **关键发现**: 总结现有文献中的主要发现和共识。
- **未来方向**: 探讨该领域未来的研究方向和潜在问题。
`;
}

/**
 * 根据指定的格式构建带有指令的提示
 * @param {string} query - 用户的原始查询
 * @param {ResearchFormat} format - 研究报告的输出格式
 * @returns {string} 包含查询和格式化指令的完整提示
 * @throws {Error} 如果查询内容为空，则抛出错误
 */
export function buildPromptWithFormat(query: string, format: ResearchFormat): string {
  // 验证查询内容
  if (!query || query.trim().length === 0) {
    throw new Error("查询内容不能为空");
  }

  let instructions: string;

  switch (format) {
    case ResearchFormat.TECHNICAL_REPORT:
      instructions = getTechnicalReportInstructions();
      break;
    case ResearchFormat.MARKET_ANALYSIS:
      instructions = getMarketAnalysisInstructions();
      break;
    case ResearchFormat.LITERATURE_REVIEW:
      instructions = getLiteratureReviewInstructions();
      break;
    default:
      return query;
  }

  return `
用户查询: "${query}"

${instructions}
`;
}
