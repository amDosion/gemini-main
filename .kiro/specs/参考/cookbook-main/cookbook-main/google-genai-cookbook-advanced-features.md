# Google Gen AI Cookbook 高级功能示例

## 概述

`cookbook-main/examples` 目录包含了大量高级功能的实用示例，展示了 Gemini API 的各种强大能力。这些示例涵盖了从基础功能到企业级应用的各个方面。

## 核心高级功能分类

### 1. Live API 相关

#### Live API 绘图和映射
- **文件**: `LiveAPI_plotting_and_mapping.ipynb`
- **功能**: 使用 Live API 进行复杂图表绘制和地图生成
- **特性**:
  - 多工具集成（图表工具、Google Search、代码执行）
  - Gemini 2.X 多模态 Live API
  - 直接使用 WebSocket 协议
  - 支持实时交互式图表生成

#### Gradio 音频部署
- **文件**: `gradio_audio.py`
- **功能**: 使用 Gradio 部署 Live API 音频实例
- **特性**:
  - Web UI 界面
  - 实时音频处理
  - 易于部署和分享

#### 浏览器作为工具
- **文件**: `Browser_as_a_tool.ipynb`
- **功能**: 将浏览器作为工具集成到 Gemini API
- **特性**:
  - Live API 中使用浏览器工具获取实时数据
  - 函数调用返回网页图像
  - 连接本地网络/内网
  - 三种不同的实现方式

### 2. 搜索和研究功能

#### 搜索基础研究报告
- **文件**: `Search_grounding_for_research_report.ipynb`
- **功能**: 使用搜索工具生成高质量研究报告
- **特性**:
  - Google Search 工具集成
  - 实时信息获取
  - 公司报告生成
  - Gemini 2.0+ 搜索工具（比 search grounding 更强大）

#### Wikipedia ReAct 搜索
- **文件**: `Search_Wikipedia_using_ReAct.ipynb`
- **功能**: 使用 ReAct 提示模式交互式搜索 Wikipedia
- **特性**:
  - ReAct 推理模式
  - 交互式搜索
  - Gemini Flash 模型

### 3. 视频分析功能

#### 视频分类
- **文件**: `Analyze_a_Video_Classification.ipynb`
- **功能**: 使用多模态能力分类视频中的动物物种
- **特性**:
  - 视频内容理解
  - 物种识别
  - 多模态分析

#### 视频摘要
- **文件**: `Analyze_a_Video_Summarization.ipynb`
- **功能**: 生成视频内容摘要
- **特性**:
  - 视频内容提取
  - 自动摘要生成
  - 多模态处理

#### 历史事件识别
- **文件**: `Analyze_a_Video_Historic_Event_Recognition.ipynb`
- **功能**: 识别视频中发生的历史事件
- **特性**:
  - 时间识别
  - 事件检测
  - 历史背景理解

### 4. 图像生成和处理

#### 动画故事视频生成
- **文件**: `Animated_Story_Video_Generation_gemini.ipynb`
- **功能**: 结合故事生成、图像和音频创建动画视频
- **特性**:
  - Imagen 图像生成
  - Live API 集成
  - 结构化输出
  - 多模态内容创作

#### 书籍插图
- **文件**: `Book_illustration.ipynb`
- **功能**: 为开源书籍创建插图
- **特性**:
  - Gemini Image 生成
  - 结构化输出
  - 批量图像生成

#### 虚拟试穿
- **文件**: `Virtual_Try_On.ipynb`
- **功能**: 虚拟试穿应用
- **特性**:
  - Gemini 2.5 空间理解
  - 分割掩码生成
  - Imagen 3 图像生成和修复
  - 服装识别和替换

### 5. 空间和 3D 理解

#### 3D 空间理解
- **文件**: `Spatial_understanding_3d.ipynb`
- **功能**: 理解 3D 场景并回答问题
- **特性**:
  - 3D 场景分析
  - 空间关系理解
  - 多模态 3D 处理

#### 多光谱遥感
- **文件**: `multi_spectral_remote_sensing.ipynb`
- **功能**: 使用图像理解能力进行多光谱分析和遥感
- **特性**:
  - 多光谱图像处理
  - 遥感数据分析
  - 专业领域应用

### 6. 嵌入向量和检索

#### 文档对话
- **文件**: `Talk_to_documents_with_embeddings.ipynb`
- **功能**: 使用嵌入向量搜索自定义数据库
- **特性**:
  - RAG (检索增强生成) 基础
  - 嵌入向量搜索
  - 文档检索

#### 异常检测
- **文件**: `Anomaly_detection_with_embeddings.ipynb`
- **功能**: 使用嵌入向量检测数据集中的异常
- **特性**:
  - 异常检测算法
  - 嵌入向量分析
  - 数据质量监控

#### 搜索重排序
- **文件**: `Search_reranking_using_embeddings.ipynb`
- **功能**: 使用嵌入向量重排序搜索结果
- **特性**:
  - 搜索结果优化
  - 语义相似度排序
  - 提升搜索质量

#### 文本分类
- **文件**: `Classify_text_with_embeddings.ipynb`
- **功能**: 使用 Gemini API 嵌入向量与 Keras 进行文本分类
- **特性**:
  - 机器学习集成
  - 文本分类模型
  - 嵌入向量特征提取

#### 聚类分析
- **文件**: `clustering_with_embeddings.ipynb`
- **功能**: 使用嵌入向量对文本数据集进行聚类
- **特性**:
  - 无监督学习
  - 文本聚类
  - 数据分组分析

### 7. 实体提取和信息抽取

#### 实体提取
- **文件**: `Entity_Extraction.ipynb`
- **功能**: 从文本中提取所需信息
- **特性**:
  - 命名实体识别
  - 结构化信息提取
  - 自定义输出格式

#### PDF 结构化输出
- **文件**: `Pdf_structured_outputs_on_invoices_and_forms.ipynb`
- **功能**: 从 PDF 发票和表单中提取信息
- **特性**:
  - File API 集成
  - 结构化输出
  - 表单数据提取
  - 发票处理

### 8. 代理和函数调用

#### Barista Bot 代理
- **文件**: `Agents_Function_Calling_Barista_Bot.ipynb`
- **功能**: 使用自动函数调用构建咖啡订购代理
- **特性**:
  - 自动函数调用 (AFC)
  - 代理循环
  - 多步骤交互
  - 实际应用示例

### 9. 批量处理和数据集

#### 数据集处理
- **文件**: `Datasets.ipynb`
- **功能**: 使用 Batch API 处理收集的日志数据集
- **特性**:
  - Batch API
  - 大规模数据处理
  - 异步批处理
  - 数据集管理

#### Apollo 11 长上下文
- **文件**: `Apollo_11.ipynb`
- **功能**: 搜索 400 页 Apollo 11 转录稿
- **特性**:
  - File API
  - 长上下文处理
  - 大文档搜索
  - 历史文档分析

### 10. 集成框架

#### LangChain 集成
- **目录**: `langchain/`
- **功能**: 多个使用 Gemini 与 LangChain 的示例
- **包含**:
  - SQL 对话
  - 代码分析（使用 DeepLake）
  - QA 系统（Chroma/Pinecone）
  - 网页加载和摘要

#### LlamaIndex 集成
- **目录**: `llamaindex/`
- **功能**: Gemini 与 LlamaIndex 的 QA 系统
- **特性**:
  - Chroma 向量数据库
  - 网页读取器
  - RAG 实现

#### Weaviate 集成
- **目录**: `weaviate/`
- **功能**: 个性化产品描述生成
- **特性**:
  - Weaviate 向量数据库
  - 语义搜索
  - 知识图谱
  - 个性化内容生成

#### Qdrant 集成
- **目录**: `qdrant/`
- **功能**: 相似度搜索和电影推荐
- **包含**:
  - 相似度搜索
  - 电影推荐系统
  - 向量数据库集成

#### MLflow 可观测性
- **目录**: `mlflow/`
- **功能**: 使用 MLflow 追踪捕获与 Google GenAI API 交互的详细信息
- **特性**:
  - 追踪和监控
  - 可观测性
  - 性能分析

### 11. JSON 能力

- **目录**: `json_capabilities/`
- **功能**: 使用 JSON Schema 的各种任务
- **包含**:
  - 实体提取 JSON
  - 情感分析
  - 文本分类
  - 文本摘要

### 12. 提示工程

- **目录**: `prompting/`
- **功能**: 各种提示技术的示例
- **包含**:
  - 零样本提示
  - 少样本提示
  - 链式思考 (Chain-of-Thought)
  - 自我提问 (Self-Ask)
  - 角色提示
  - 上下文信息添加
  - 基础案例提供

### 13. 其他高级功能

#### 图表、图形和幻灯片
- **文件**: `Working_with_Charts_Graphs_and_Slide_Decks.ipynb`
- **功能**: 从各种图像中提取数据
- **特性**:
  - 图表数据提取
  - 图形理解
  - 幻灯片分析

#### 语音备忘录
- **文件**: `Voice_memos.ipynb`
- **功能**: 基于语音备忘录和之前文章生成博客创意
- **特性**:
  - 音频处理
  - 内容生成
  - 创意辅助

#### 营销活动生成
- **文件**: `Market_a_Jet_Backpack.ipynb`
- **功能**: 从产品草图创建营销活动
- **特性**:
  - 多模态输入
  - 营销内容生成
  - 创意生成

#### Google I/O 2025 Live Coding
- **文件**: `Google_IO2025_Live_Coding.ipynb`
- **功能**: Google I/O 2025 现场编码会话使用的笔记本
- **特性**:
  - Gemini API SDK 实践
  - GenMedia 模型
  - 思考能力模型
  - Gemini API 工具使用

## 技术栈分类

### 向量数据库集成
- **ChromaDB**: `chromadb/`
- **Qdrant**: `qdrant/`
- **Weaviate**: `weaviate/`
- **Pinecone**: LangChain 示例中

### 框架集成
- **LangChain**: `langchain/`
- **LlamaIndex**: `llamaindex/`
- **MLflow**: `mlflow/`
- **Gradio**: `gradio_audio.py`

### API 类型
- **Live API**: 实时交互
- **Batch API**: 批量处理
- **File API**: 文件处理
- **Interactions API**: 深度研究（Deep Research）

## 推荐学习路径

### 初学者
1. 提示工程 (`prompting/`)
2. JSON 能力 (`json_capabilities/`)
3. 基础嵌入向量示例

### 中级
1. Live API 示例
2. 函数调用和代理 (`Agents_Function_Calling_Barista_Bot.ipynb`)
3. 向量数据库集成

### 高级
1. 多模态视频分析
2. 3D 空间理解
3. 企业级集成（MLflow、LangChain）
4. Deep Research Agent

## 关键发现

### 1. Live API 的强大能力
- 支持实时音频、视频、文本交互
- 可以集成多种工具（浏览器、搜索、代码执行）
- 适合构建交互式应用

### 2. 搜索和研究功能
- Google Search 工具比 search grounding 更强大
- 支持实时信息获取
- 适合生成高质量研究报告

### 3. 多模态能力
- 视频分析（分类、摘要、事件识别）
- 3D 空间理解
- 图像生成和处理
- 虚拟试穿等创新应用

### 4. 企业级集成
- 与主流框架集成（LangChain、LlamaIndex）
- 向量数据库支持
- 可观测性和监控（MLflow）

### 5. 实际应用场景
- 文档处理和分析
- 内容生成和创作
- 数据分析和异常检测
- 搜索和推荐系统

---

**最后更新**: 2025年1月  
**来源**: `cookbook-main/examples` 目录
