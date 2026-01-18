# HTTP URL优化方案：使用临时文件上传到Google Files API

## 关键发现

### 1. 官方示例支持HTTP URL

从 `nano_banana_recipes.ipynb` 可以看到，Google SDK支持多种方式处理图片：

**方式1：直接使用HTTP URL（from_uri）**
```python
# Cell 17-19示例
image_to_edit_path = "https://storage.googleapis.com/..."
source_image = types.Part.from_uri(file_uri=image_to_edit_path)
```

**方式2：从bytes创建（from_bytes）**
```python
# 官方示例
image = Image.open("/path/to/cat_image.png")
response = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents=[prompt, image],  # 直接传递PIL Image对象
)
```

**方式3：从bytes创建Part**
```python
# Cell 11示例
buffer = io.BytesIO()
image.save(buffer, format="PNG")
return types.Part.from_bytes(data=buffer.getvalue(), mime_type="image/png")
```

### 2. 当前实现

**SimpleImageEditService** (`simple_image_edit_service.py:150-186`)
```python
# HTTP URL下载后，可选择上传到Google Files API
if use_google_files_api:
    try:
        file_uri = await self._upload_bytes_to_google_files(image_bytes, mime_type)
        return {'type': 'fileData', 'data': {'fileUri': file_uri}}
    except Exception as e:
        logger.warning(f"Google Files API upload failed: {e}")

# 回退到Base64
base64_str = base64.b64encode(image_bytes).decode('utf-8')
return {'type': 'inlineData', 'data': {'data': base64_str}}
```

**ConversationalImageEditService** (`conversational_image_edit_service.py:386-424`)
```python
# 当前：下载后直接使用Part.from_bytes()或转为base64
# ❌ 没有尝试上传到Google Files API
image_bytes = await response.read()
message_parts.append(genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
```

## 优化方案

### 方案1：直接使用HTTP URL（如果SDK支持）

**优点**:
- ✅ 无需下载
- ✅ 无需临时文件
- ✅ 无需上传

**实现**:
```python
# 尝试直接使用HTTP URL
if url.startswith('http://') or url.startswith('https://'):
    try:
        # 尝试直接使用HTTP URL（如果SDK支持）
        message_parts.append(genai_types.Part.from_uri(
            file_uri=url,
            mime_type=ref_img.get('mimeType', 'image/png')
        ))
        logger.info(f"[ConversationalImageEdit] ✅ 直接使用HTTP URL: {url[:60]}...")
    except Exception as e:
        logger.warning(f"[ConversationalImageEdit] from_uri不支持HTTP URL，降级到下载: {e}")
        # 降级到方案2
```

**注意**: 需要验证 `Part.from_uri()` 是否真的支持HTTP URL，还是只支持 `gs://` URI。

### 方案2：下载后上传到Google Files API（推荐）

**优点**:
- ✅ 减少数据传输（file_uri比base64小得多）
- ✅ 与SimpleImageEditService保持一致
- ✅ 已有实现可以参考

**实现**:
```python
elif url.startswith('http://') or url.startswith('https://'):
    logger.info(f"[ConversationalImageEdit] 下载 HTTP URL 图片: {url[:60]}...")
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    image_bytes = await response.read()
                    mime_type = ref_img.get('mimeType') or response.headers.get('Content-Type', 'image/png')
                    
                    # ✅ 优化：尝试上传到Google Files API
                    if self.file_handler:
                        try:
                            # 使用临时文件上传到Google Files API
                            file_uri = await self._upload_bytes_to_google_files(
                                image_bytes,
                                mime_type
                            )
                            
                            if genai_types:
                                # 使用file_uri（更高效）
                                message_parts.append(genai_types.Part(file_data=genai_types.FileData(
                                    file_uri=file_uri,
                                    mime_type=mime_type
                                )))
                                logger.info(f"[ConversationalImageEdit] ✅ 已上传到Google Files API: {file_uri}")
                            else:
                                message_parts.append({
                                    'file_data': {
                                        'file_uri': file_uri,
                                        'mime_type': mime_type
                                    }
                                })
                            continue  # 成功上传，跳过base64回退
                        except Exception as e:
                            logger.warning(f"[ConversationalImageEdit] Google Files API上传失败，使用base64: {e}")
                    
                    # 回退到base64（如果上传失败或不支持）
                    if genai_types:
                        try:
                            message_parts.append(genai_types.Part.from_bytes(
                                data=image_bytes,
                                mime_type=mime_type
                            ))
                        except AttributeError:
                            base64_str = base64.b64encode(image_bytes).decode('utf-8')
                            message_parts.append(genai_types.Part(inline_data=genai_types.Blob(
                                data=image_bytes,
                                mime_type=mime_type
                            )))
                    else:
                        base64_str = base64.b64encode(image_bytes).decode('utf-8')
                        message_parts.append({
                            'inline_data': {
                                'mime_type': mime_type,
                                'data': base64_str
                            }
                        })
```

**需要添加的方法**:
```python
async def _upload_bytes_to_google_files(
    self,
    image_bytes: bytes,
    mime_type: str
) -> str:
    """将字节数据上传到 Google Files API"""
    # 创建临时文件
    suffix = '.png'
    if 'jpeg' in mime_type or 'jpg' in mime_type:
        suffix = '.jpg'
    elif 'webp' in mime_type:
        suffix = '.webp'
    
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(image_bytes)
        tmp_path = tmp_file.name
    
    try:
        # 上传文件
        file_info = await self.file_handler.upload_file(
            tmp_path,
            display_name=f"image_edit_{int(time.time())}",
            mime_type=mime_type
        )
        return file_info['uri']
    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
```

## 完整修复计划

### 步骤1：修复base64错误（必需）

修复 `_convert_reference_images` 中的HTTP URL识别错误

### 步骤2：优化HTTP URL处理（推荐）

在 `send_edit_message` 中，下载HTTP URL后：
1. 尝试上传到Google Files API（如果有file_handler）
2. 成功则使用file_uri（更高效）
3. 失败则回退到base64（当前方式）

### 步骤3：验证Part.from_uri是否支持HTTP URL（可选）

测试 `Part.from_uri()` 是否直接支持HTTP URL，如果支持，可以跳过下载步骤。

## 文件修改清单

### 1. 修复base64错误
- `backend/app/services/gemini/conversational_image_edit_service.py`
  - 修改 `_convert_reference_images()` 方法（第724-729行）

### 2. 添加字节上传方法
- `backend/app/services/gemini/conversational_image_edit_service.py`
  - 添加 `_upload_bytes_to_google_files()` 方法（参考SimpleImageEditService）

### 3. 优化HTTP URL处理
- `backend/app/services/gemini/conversational_image_edit_service.py`
  - 修改 `send_edit_message()` 中的HTTP URL处理逻辑（第386-424行）
  - 添加Google Files API上传逻辑

## 优点总结

1. **减少数据传输**：使用file_uri代替base64，请求体更小
2. **保持一致性**：与SimpleImageEditService的处理方式一致
3. **优雅降级**：上传失败时回退到base64，不影响功能
4. **利用临时文件**：下载后的临时文件可以直接用于上传，无需重复读取

## 注意事项

1. **临时文件清理**：确保上传后清理临时文件
2. **错误处理**：上传失败时要优雅降级到base64
3. **file_handler检查**：确保ConversationalImageEditService有file_handler实例
4. **性能考虑**：上传会增加延迟，但对于大文件来说，减少数据传输的好处更大