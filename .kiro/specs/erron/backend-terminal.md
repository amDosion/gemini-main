D:\gemini-main\gemini-main>pnpm run dev

> gemini-flux-chat-local@1.2.1 dev D:\gemini-main\gemini-main
> node --no-deprecation ./node_modules/concurrently/dist/bin/concurrently.js "npm run server" "vite"

[0] npm warn Unknown env config "verify-deps-before-run". This will stop working in the next major version of npm.
[0] npm warn Unknown env config "_jsr-registry". This will stop working in the next major version of npm.
[0]
[0] > gemini-flux-chat-local@1.2.1 server
[0] > cd backend && set PYTHONUNBUFFERED=1 && uvicorn app.main:app --reload --reload-dir app --port 8000 --log-level info
[0]
[1] 
[1]   VITE v6.4.1  ready in 165 ms
[1]
[1]   ➜  Local:   http://localhost:5173/
[1]   ➜  Network: http://192.168.50.22:5173/
[0] INFO:     Will watch for changes in these directories: ['D:\\gemini-main\\gemini-main\\backend\\app']
[0] INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
[0] INFO:     Started reloader process [37248] using WatchFiles
[0] 2025-12-18 16:16:54 - main - INFO - [INFO] Database tables initialized
[0] INFO:     Finished server process [30204]
[0] ERROR:    Traceback (most recent call last):
[0]   File "C:\Python314\Lib\asyncio\runners.py", line 204, in run
[0]     return runner.run(main)
[0]            ~~~~~~~~~~^^^^^^
[0]   File "C:\Python314\Lib\asyncio\runners.py", line 127, in run
[0]     return self._loop.run_until_complete(task)
[0]            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
[0]   File "C:\Python314\Lib\asyncio\base_events.py", line 706, in run_until_complete
[0]     self.run_forever()
[0]     ~~~~~~~~~~~~~~~~^^
[0]   File "C:\Python314\Lib\asyncio\base_events.py", line 677, in run_forever
[0]     self._run_once()
[0]     ~~~~~~~~~~~~~~^^
[0]   File "C:\Python314\Lib\asyncio\base_events.py", line 2046, in _run_once
[0]     handle._run()
[0]     ~~~~~~~~~~~^^
[0]   File "C:\Python314\Lib\asyncio\events.py", line 94, in _run
[0]     self._context.run(self._callback, *self._args)
[0]     ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\uvicorn\server.py", line 70, in serve
[0]     with self.capture_signals():
[0]          ~~~~~~~~~~~~~~~~~~~~^^
[0]   File "C:\Python314\Lib\contextlib.py", line 148, in __exit__
[0]     next(self.gen)
[0]     ~~~~^^^^^^^^^^
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\uvicorn\server.py", line 331, in capture_signals
[0]     signal.raise_signal(captured_signal)
[0]     ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^
[0]   File "C:\Python314\Lib\asyncio\runners.py", line 166, in _on_sigint
[0]     raise KeyboardInterrupt()
[0] KeyboardInterrupt
[0]
[0] During handling of the above exception, another exception occurred:
[0]
[0] Traceback (most recent call last):
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\starlette\routing.py", line 701, in lifespan
[0]     await receive()
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\uvicorn\lifespan\on.py", line 137, in receive
[0]     return await self.receive_queue.get()
[0]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[0]   File "C:\Python314\Lib\asyncio\queues.py", line 186, in get
[0]     await getter
[0] asyncio.exceptions.CancelledError
[0]
[0] ERROR:    Exception in ASGI application
[0] Traceback (most recent call last):
[0]   File "C:\Python314\Lib\asyncio\runners.py", line 204, in run
[0]     return runner.run(main)
[0]            ~~~~~~~~~~^^^^^^
[0]   File "C:\Python314\Lib\asyncio\runners.py", line 127, in run
[0]     return self._loop.run_until_complete(task)
[0]            ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
[0]   File "C:\Python314\Lib\asyncio\base_events.py", line 706, in run_until_complete
[0]     self.run_forever()
[0]     ~~~~~~~~~~~~~~~~^^
[0]   File "C:\Python314\Lib\asyncio\base_events.py", line 677, in run_forever
[0]     self._run_once()
[0]     ~~~~~~~~~~~~~~^^
[0]   File "C:\Python314\Lib\asyncio\base_events.py", line 2046, in _run_once
[0]     handle._run()
[0]     ~~~~~~~~~~~^^
[0]   File "C:\Python314\Lib\asyncio\events.py", line 94, in _run
[0]     self._context.run(self._callback, *self._args)
[0]     ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\uvicorn\server.py", line 70, in serve
[0]     with self.capture_signals():
[0]          ~~~~~~~~~~~~~~~~~~~~^^
[0]   File "C:\Python314\Lib\contextlib.py", line 148, in __exit__
[0]     next(self.gen)
[0]     ~~~~^^^^^^^^^^
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\uvicorn\server.py", line 331, in capture_signals
[0]     signal.raise_signal(captured_signal)
[0]     ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^
[0]   File "C:\Python314\Lib\asyncio\runners.py", line 166, in _on_sigint
[0]     raise KeyboardInterrupt()
[0] KeyboardInterrupt
[0]
[0] During handling of the above exception, another exception occurred:
[0]
[0] Traceback (most recent call last):
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\uvicorn\protocols\http\httptools_impl.py", line 409, in run_asgi
[0]     result = await app(  # type: ignore[func-returns-value]
[0]              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[0]         self.scope, self.receive, self.send
[0]         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[0]     )
[0]     ^
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\uvicorn\middleware\proxy_headers.py", line 60, in __call__
[0]     return await self.app(scope, receive, send)
[0]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\fastapi\applications.py", line 1054, in __call__
[0]     await super().__call__(scope, receive, send)
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\starlette\applications.py", line 113, in __call__
[0]     await self.middleware_stack(scope, receive, send)
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\starlette\middleware\errors.py", line 164, in __call__
[0]     await self.app(scope, receive, _send)
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\starlette\middleware\cors.py", line 93, in __call__
[0]     await self.simple_response(scope, receive, send, request_headers=headers)
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\starlette\middleware\cors.py", line 144, in simple_response
[0]     await self.app(scope, receive, send)
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\starlette\middleware\exceptions.py", line 63, in __call__
[0]     await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
[0]     await app(scope, receive, sender)
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\starlette\routing.py", line 716, in __call__
[0]     await self.middleware_stack(scope, receive, send)
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\starlette\routing.py", line 736, in app
[0]     await route.handle(scope, receive, send)
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\starlette\routing.py", line 290, in handle
[0]     await self.app(scope, receive, send)
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\starlette\routing.py", line 78, in app
[0]     await wrap_app_handling_exceptions(app, request)(scope, receive, send)
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
[0]     await app(scope, receive, sender)
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\starlette\routing.py", line 76, in app
[0]     await response(scope, receive, send)
[0]   File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\starlette\responses.py", line 271, in __call__
[0]     async with anyio.create_task_group() as task_group:
[0]                ~~~~~~~~~~~~~~~~~~~~~~~^^
[0]   File "C:\Python314\Lib\site-packages\anyio\_backends\_asyncio.py", line 785, in __aexit__
[0]     raise exc_val
[0]   File "C:\Python314\Lib\site-packages\anyio\_backends\_asyncio.py", line 753, in __aexit__
[0]     await self._on_completed_fut
[0] asyncio.exceptions.CancelledError
[0] [Storage Router] TEMP_DIR initialized: D:\gemini-main\gemini-main\backend\temp
[0] [Storage Router] TEMP_DIR initialized: D:\gemini-main\gemini-main\backend\temp
[0] 2025-12-18 16:16:54 - main - INFO - [INFO] API routes imported via relative import
[0] 2025-12-18 16:16:54 - main - INFO - [INFO] Worker pool imported via relative import
[0] 2025-12-18 16:16:54 - main - INFO - [INFO] API routes registered (profiles, sessions, personas, storage, image_expand)
[0] 2025-12-18 16:16:54 - main - INFO - ============================================================
[0] 2025-12-18 16:16:54 - main - INFO - >>> Gemini Chat Backend Starting...
[0] 2025-12-18 16:16:54 - main - INFO - ============================================================
[0] 2025-12-18 16:16:54 - main - INFO - Selenium Available: [YES]
[0] 2025-12-18 16:16:54 - main - INFO - PDF Extraction Available: [YES]
[0] 2025-12-18 16:16:54 - main - INFO - Embedding Service Available: [YES]
[0] 2025-12-18 16:16:54 - main - INFO - Upload Worker Pool Available: [YES]
[0] 2025-12-18 16:16:54 - main - INFO - ============================================================
[0] INFO:     Started server process [25984]
[0] 2025-12-18 16:16:54 - main - INFO - [INFO] Starting upload worker pool...
[0] INFO:     Waiting for application startup.
[0] ================================================================================
[0] [WorkerPool] STARTING UPLOAD WORKER POOL...
[0] ================================================================================
[0] [WorkerPool] Connecting to Redis: 192.168.50.175:6379
[0] [WorkerPool] Redis connected successfully
[0] [WorkerPool] Recovering interrupted tasks...
[0] [WorkerPool] Recovered 0 tasks
[0] 2025-12-18 16:16:54 - main - INFO - [OK] Upload worker pool started successfully
[0] [WorkerPool] Starting 5 workers...
[0] [WorkerPool] All 5 workers started successfully
[0] ================================================================================
[0] [WorkerPool] WORKER POOL READY
[0] ================================================================================
[0] [WorkerPool] Reconciler started (interval=15.0s, limit=500)
[0] [Worker-0] Started, listening for tasks...
[0] [Worker-1] Started, listening for tasks...
[0] [Worker-2] Started, listening for tasks...
[0] [Worker-3] Started, listening for tasks...
[0] [Worker-4] Started, listening for tasks...
[0] INFO:     Stopping reloader process [35344]
[0] npm run server exited with code 1
[0] 2025-12-18 16:16:55 - main - WARNING - [OK] Worker pool startup verification passed
[0] INFO:     Application startup complete.
[0] INFO:     127.0.0.1:65293 - "GET /health?t=1766045817989 HTTP/1.1" 200 OK
[1] → 发送请求: GET /api/profiles
[1] → 发送请求: GET /api/storage/configs
[0] INFO:     127.0.0.1:65295 - "GET /api/profiles HTTP/1.1" 200 OK
[1] ← 收到响应: 200 /api/profiles
[0] INFO:     127.0.0.1:65297 - "GET /api/storage/configs HTTP/1.1" 200 OK
[1] ← 收到响应: 200 /api/storage/configs
[1] → 发送请求: GET /api/profiles
[0] INFO:     127.0.0.1:65299 - "GET /api/profiles HTTP/1.1" 200 OK
[1] ← 收到响应: 200 /api/profiles
[1] → 发送请求: GET /api/active-profile
[1] → 发送请求: GET /api/storage/active
[0] INFO:     127.0.0.1:55664 - "GET /api/active-profile HTTP/1.1" 200 OK
[1] ← 收到响应: 200 /api/active-profile
[0] INFO:     127.0.0.1:55665 - "GET /api/storage/active HTTP/1.1" 200 OK
[1] ← 收到响应: 200 /api/storage/active
[1] → 发送请求: GET /api/active-profile
[0] INFO:     127.0.0.1:60390 - "GET /api/active-profile HTTP/1.1" 200 OK
[1] ← 收到响应: 200 /api/active-profile
[1] → 发送请求: GET /api/active-profile
[0] INFO:     127.0.0.1:51168 - "GET /api/active-profile HTTP/1.1" 200 OK
[1] ← 收到响应: 200 /api/active-profile
[1] → 发送请求: GET /api/active-profile
[1] → 发送请求: GET /api/profiles
[0] INFO:     127.0.0.1:55829 - "GET /api/profiles HTTP/1.1" 200 OK
[1] ← 收到响应: 200 /api/profiles
[0] INFO:     127.0.0.1:55828 - "GET /api/active-profile HTTP/1.1" 200 OK
[1] ← 收到响应: 200 /api/active-profile
[1] → 发送请求: GET /api/profiles
[0] INFO:     127.0.0.1:61537 - "GET /api/profiles HTTP/1.1" 200 OK
[1] ← 收到响应: 200 /api/profiles
[1] → 发送请求: GET /api/profiles
[0] INFO:     127.0.0.1:62403 - "GET /api/profiles HTTP/1.1" 200 OK
[1] ← 收到响应: 200 /api/profiles
[1] → 发送请求: GET /api/profiles
[0] INFO:     127.0.0.1:54105 - "GET /api/profiles HTTP/1.1" 200 OK
[1] ← 收到响应: 200 /api/profiles
[0] INFO:     127.0.0.1:63045 - "GET /api/browse/progress/477f53cf-ced2-4f13-86dd-da6141f1cc4c HTTP/1.1" 200 OK