graph TD
    %% ======================================================================================
    %% 阶段 1: 流式累积与状态管理 (Data Accumulation)
    %% 文件: frontend/hooks/useChat.ts
    %% ======================================================================================
    subgraph Stage_Accumulation [阶段 1: 流式累积 (useChat.ts)]
        direction TB
        API[LLM API Stream] -->|Chunk Update| StreamLoop{Stream Loop}
        
        StreamLoop -->|1. Text Chunk| AppendText[text += chunk.text]
        StreamLoop -->|2. Tool/Metadata| MergeMeta[Merge Metadata]
        StreamLoop -->|3. Attachments| AppendMedia[Append Generated Media]
        
        AppendText & MergeMeta & AppendMedia --> MsgState[React State: messages<br/>(Message Object)]
        
        note1[核心逻辑: sendMessageStream<br/>实时更新 React State 触发重绘]
        style note1 fill:#fff,stroke:#333,stroke-dasharray: 5 5
    end

    %% ======================================================================================
    %% 阶段 2: 实时解析与分离 (Real-time Parsing)
    %% 文件: frontend/hooks/useMessageProcessor.ts
    %% ======================================================================================
    subgraph Stage_Parsing [阶段 2: 实时解析 (useMessageProcessor.ts)]
        direction TB
        MsgState -->|Input| ProcessorHook[useMessageProcessor]
        
        %% A. 思维链解析
        ProcessorHook -->|Regex| CheckThinking{Has &lt;thinking&gt;?}
        CheckThinking -- Yes --> ParseThink[提取 thinkingContent]
        CheckThinking -- No --> NullThink[thinkingContent = null]
        
        %% B. 正文内容分离
        CheckThinking -->|Remove Tags| CleanContent[提取 displayContent]
        
        %% C. 特殊模式解析 (针对 PDF 提取)
        CleanContent --> CheckJSON{Is JSON Format?<br/>(PDF Mode)}
        CheckJSON -- Yes --> ParseJSON[解析为 Object Data]
        CheckJSON -- No --> KeepText[保持 Markdown 文本]
        
        %% D. 元数据提取
        ProcessorHook --> ExtractMeta[提取 groundingMetadata &<br/>urlContextMetadata]
    end

    %% ======================================================================================
    %% 阶段 3: 组件分层组装 (Layered Rendering)
    %% 文件: frontend/components/chat/MessageItem.tsx
    %% ======================================================================================
    subgraph Stage_Rendering [阶段 3: 组件分层渲染 (MessageItem.tsx)]
        direction TB
        
        %% 1. 搜索过程层 (最顶部)
        ExtractMeta -->|Props| Comp_Search[SearchProcess 组件<br/>(显示搜索查询词/状态)]
        
        %% 2. 思维链层 (可折叠)
        ParseThink -->|Props| Comp_Thinking[ThinkingBlock 组件<br/>(灰色背景/折叠动画)]
        
        %% 3. 内容层 (核心展示 - 分歧)
        KeepText -->|Markdown String| Comp_MD[MarkdownRenderer 组件]
        Comp_MD -->|Plugin| SyntaxHighlighter[代码高亮]
        Comp_MD -->|Visual| BlinkingCursor[流式光标]
        
        ParseJSON -->|Data Object| Comp_PDF[PdfExtractionResult 组件<br/>(结构化表格/JSON视图)]
        
        %% 4. 引用来源层
        ExtractMeta -->|Citations| Comp_Sources[GroundingSources 组件<br/>(底部引用卡片)]
        ExtractMeta -->|URL Status| Comp_UrlStatus[UrlContextStatus 组件]
        
        %% 5. 媒体附件层 (最底部)
        MsgState -->|message.attachments| Comp_Media[AttachmentGrid 组件]
        Comp_Media --> RenderImg[图片预览/下载]
        Comp_Media --> RenderVid[视频播放器]
        Comp_Media --> RenderAud[音频播放器/歌词]
    end

    %% ======================================================================================
    %% 最终视图组合
    %% ======================================================================================
    subgraph Final_View [最终 UI 视图堆栈]
        direction TB
        Stack1[1. Search Process]
        Stack2[2. Thinking Block]
        Stack3[3. Main Content (MD / PDF)]
        Stack4[4. Sources / Context]
        Stack5[5. Media Attachments]
    end

    %% 连接组件到最终视图
    Comp_Search --> Stack1
    Comp_Thinking --> Stack2
    Comp_MD & Comp_PDF --> Stack3
    Comp_Sources & Comp_UrlStatus --> Stack4
    Comp_Media --> Stack5

    %% 样式定义
    style Stage_Accumulation fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    style Stage_Parsing fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style Stage_Rendering fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    style Final_View fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    
    %% 关键节点样式
    style ProcessorHook fill:#ffe0b2,stroke:#f57c00
    style Comp_MD fill:#e1bee7,stroke:#8e24aa
    style Comp_PDF fill:#e1bee7,stroke:#8e24aa
    style Comp_Thinking fill:#e1bee7,stroke:#8e24aa

Mermaid 图表：多模式 (Chat / Media / PDF) 内容组装分流
前端根据 AppMode 的不同，使用不同的策略来组装和展示内容。
    graph TD
    %% --- 入口 ---
    Start[User Send Action] -->|InputArea.tsx| Handler_OnSend{Check AppMode}

    %% --- 1. 聊天模式 ---
    Handler_OnSend -- "Chat Mode" --> Path_Chat[useChat.ts: sendMessageStream]
    Path_Chat -->|Stream Text| Logic_ChatProcess[useMessageProcessor]
    Logic_ChatProcess -->|Text & Thinking| Comp_MD[MarkdownRenderer]
    Logic_ChatProcess -->|Web Search| Comp_Search[SearchProcess]
    
    %% --- 2. 媒体生成模式 ---
    Handler_OnSend -- "Image/Video/Audio Gen" --> Path_Media[useChat.ts: generateImage/Video/Speech]
    Path_Media -->|Wait for API| API_Media[LLM Service API]
    API_Media -->|Return URL| State_Attach[Message.attachments]
    State_Attach -->|Prop: attachments| Comp_Grid[AttachmentGrid.tsx]
    Comp_Grid -->|MimeType Check| Render_Media{Media Type}
    Render_Media -- image/* --> View_Img[Image Preview + Download]
    Render_Media -- video/* --> View_Vid[Video Player]
    Render_Media -- audio/* --> View_Aud[Audio Player + Waveform]

    %% --- 3. PDF 提取模式 ---
    Handler_OnSend -- "PDF Extract" --> Path_PDF[useChat.ts: PDF Logic]
    Path_PDF -->|File + Template| Service_PDF[PdfExtractionService.ts]
    Service_PDF -->|Backend API| JSON_Result[JSON Data Object]
    JSON_Result -->|JSON.stringify| State_Content[Message.content]
    
    State_Content -->|MessageItem.tsx| Check_JSON{Is Valid JSON?}
    Check_JSON -- Yes --> View_Extract[PdfExtractView.tsx / PdfExtractionResult.tsx]
    View_Extract -->|Render Key-Value| UI_Structured[结构化数据表格/列表]
    Check_JSON -- No (Error/Text) --> Comp_MD

    %% --- 最终汇总 ---
    Comp_MD --> Container[Message Container]
    Comp_Search --> Container
    Comp_Grid --> Container
    UI_Structured --> Container

    %% 样式
    style Handler_OnSend fill:#212121,stroke:#fff,color:#fff
    style Path_Chat fill:#e3f2fd,stroke:#1565c0
    style Path_Media fill:#fce4ec,stroke:#c2185b
    style Path_PDF fill:#f3e5f5,stroke:#7b1fa2
    style Container fill:#eeeeee,stroke:#333,stroke-dasharray: 5 5