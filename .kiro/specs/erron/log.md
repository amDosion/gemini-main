INFO:     Will watch for changes in these directories: ['D:\\gemini-main\\gemini-main']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [123652] using WatchFiles
2025-12-27 21:34:25 - main - INFO - [INFO] Database tables initialized
[Storage Router] TEMP_DIR initialized: D:\gemini-main\gemini-main\backend\temp
[Storage Router] TEMP_DIR initialized: D:\gemini-main\gemini-main\backend\temp
D:\gemini-main\gemini-main\backend\app\routers\research.py:61: UserWarning: Field name "schema" in "ResearchFormatRequest" shadows an attribute in parent "BaseModel"
  class ResearchFormatRequest(BaseModel):
C:\Python314\Lib\site-packages\pydantic\_internal\_config.py:383: UserWarning: Valid config keys have changed in V2:
* 'schema_extra' has been renamed to 'json_schema_extra'
  warnings.warn(message, UserWarning)
[TryOnService] Vertex AI SDK not available, will use Gemini API fallback
2025-12-27 21:34:25 - main - INFO - [INFO] API routes imported via relative import
2025-12-27 21:34:25 - main - INFO - [INFO] Worker pool imported via relative import
Process SpawnProcess-1:
Traceback (most recent call last):
  File "C:\Python314\Lib\multiprocessing\process.py", line 320, in _bootstrap
    self.run()
    ~~~~~~~~^^
  File "C:\Python314\Lib\multiprocessing\process.py", line 108, in run
    self._target(*self._args, **self._kwargs)
    ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\uvicorn\_subprocess.py", line 80, in subprocess_started
    target(sockets=sockets)
    ~~~~~~^^^^^^^^^^^^^^^^^
  File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\uvicorn\server.py", line 67, in run
    return asyncio.run(self.serve(sockets=sockets))
           ~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Python314\Lib\asyncio\runners.py", line 204, in run
    return runner.run(main)
           ~~~~~~~~~~^^^^^^
  File "C:\Python314\Lib\asyncio\runners.py", line 127, in run
    return self._loop.run_until_complete(task)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "C:\Python314\Lib\asyncio\base_events.py", line 719, in run_until_complete
    return future.result()
           ~~~~~~~~~~~~~^^
  File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\uvicorn\server.py", line 71, in serve
    await self._serve(sockets)
  File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\uvicorn\server.py", line 78, in _serve
    config.load()
    ~~~~~~~~~~~^^
  File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\uvicorn\config.py", line 436, in load
    self.loaded_app = import_from_string(self.app)
                      ~~~~~~~~~~~~~~~~~~^^^^^^^^^^
  File "C:\Users\12180\AppData\Roaming\Python\Python314\site-packages\uvicorn\importer.py", line 19, in import_from_string
    module = importlib.import_module(module_str)
  File "C:\Python314\Lib\importlib\__init__.py", line 88, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1398, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1371, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1342, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 938, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 762, in exec_module
  File "<frozen importlib._bootstrap>", line 491, in _call_with_frames_removed
  File "D:\gemini-main\gemini-main\backend\app\main.py", line 342, in <module>
    app.include_router(file_search.router)
                       ^^^^^^^^^^^
NameError: name 'file_search' is not defined
