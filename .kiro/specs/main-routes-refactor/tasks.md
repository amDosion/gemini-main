# Implementation Plan

- [-] 1. 重构 `routers/health.py`



  - [x] 1.1 更新 health.py 添加完整的健康检查端点



    - 添加 `GET /` 根路径端点，返回服务可用性信息
    - 添加 `GET /health` 详细健康检查端点

    - 更新 `set_availability()` 函数支持 `worker_pool` 参数
    - _Requirements: 5.1, 5.2, 5.3_
  - [x] 1.2 编写 health.py 属性测试


    - **Property 2: Health endpoint reflects service availability**
    - **Validates: Requirements 5.1, 5.2, 5.3**

- [ ] 2. 重构 `routers/browse.py`
  - [x] 2.1 迁移辅助函数到 browse.py


    - 移动 `extract_title_from_html()` 函数
    - 移动 `html_to_markdown()` 函数
    - 移动 `take_screenshot_selenium()` 函数
    - _Requirements: 2.4_
  - [x] 2.2 实现完整的 browse 端点


    - 更新 `POST /api/browse` 端点，包含进度追踪和截图功能
    - 添加 `GET /api/browse/progress/{operation_id}` SSE 端点
    - 添加 `POST /api/search` 网页搜索端点
    - 更新 `set_browser_service()` 函数签名
    - _Requirements: 2.1, 2.2, 2.3_
  - [ ] 2.3 编写 browse.py 属性测试
    - **Property 1: Browse endpoint returns valid response structure**
    - **Validates: Requirements 2.1, 6.3**

- [ ] 3. 确认 `routers/pdf.py` 和 `routers/embedding.py`
  - [x] 3.1 验证 pdf.py 已包含所有必要功能


    - 确认 `model_id` 参数支持
    - 确认错误处理完整
    - _Requirements: 3.1, 3.2_
  - [x] 3.2 验证 embedding.py 已包含所有必要功能


    - 确认所有 5 个端点存在
    - 确认 Pydantic 模型定义完整
    - _Requirements: 4.1, 4.2_

- [x] 4. 精简 `main.py`


  - [ ] 4.1 移除内联端点和模型
    - 删除所有 `@app.get()` 和 `@app.post()` 装饰的函数
    - 删除 `BrowseRequest`、`BrowseResponse`、`AddDocumentRequest`、`SearchRequest` 模型



    - 删除辅助函数（已迁移到 browse.py）
    - _Requirements: 1.1, 1.2, 1.3_
  - [ ] 4.2 更新路由注册
    - 启用 `browse.router` 注册（取消注释）
    - 启用 `pdf.router` 注册（取消注释）
    - 更新 `health.set_availability()` 调用，添加 `worker_pool` 参数
    - 调用 `browse.set_browser_service()` 设置服务引用
    - _Requirements: 1.1_

- [ ] 5. Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. 编写向后兼容性属性测试
  - [ ] 6.1 编写 API 兼容性测试
    - **Property 3: API backward compatibility - URL paths preserved**
    - **Property 4: API backward compatibility - request parameters preserved**
    - **Property 5: API backward compatibility - response structure preserved**
    - **Validates: Requirements 6.1, 6.2, 6.3**

- [ ] 7. Final Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.
