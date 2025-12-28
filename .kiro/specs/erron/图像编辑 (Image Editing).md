这份文档对应的（或您正在研究的）是阿里云百炼平台上的 **“图像编辑 (Image Editing)”** 或 **“智能图像编辑”** 能力。虽然 URL 中包含 `qwen`，但在阿里云目前的分类中，**图像生成的修改与编辑**通常仍由 **通义万相 (Wanx)** 系列模型或其与 **Qwen-VL (视觉理解)** 的组合能力提供支持。

简单来说，上一个 API 是“无中生有”（文生图），这一个 API 是 **“锦上添花”或“移花接木”（图生图/修图）**。

以下是该 API 的核心功能、关键参数和使用代码总结：

### 1. 核心功能简介
该 API 允许你上传一张现有的图片，并通过文字指令对图片进行修改。主要场景包括：
*   **涂抹编辑 (Inpainting/Repainting):** 指定图片中的某个区域（通过 Mask 蒙版），将该区域的内容修改为提示词描述的内容（例如：把图片里的“狗”换成“猫”，或者给人物“戴上墨镜”）。
*   **图像扩展 (Outpainting):** 将图片向四周延伸，模型会自动补全画面内容。
*   **风格迁移/指令编辑:** 部分高级模式支持直接通过自然语言指令修改全图（例如：“把天气变成下雨”、“变成梵高风格”）。

### 2. API 关键差异 (与文生图相比)
与文生图（Generation）相比，图像编辑（Editing）最大的不同在于**输入参数**：
1.  **必须提供原图:** 需要传入 `input.image_url`（必须是公网可访问的 URL）。
2.  **通常需要蒙版 (Mask):** 为了精确控制修改范围，通常需要上传一张黑白蒙版图（`mask_url`），白色代表“要修改的区域”，黑色代表“保持原样的区域”。
3.  **模型参数:** 模型名称通常仍涉及 `wanx` 系列，但调用方式略有不同。

---

### 3. 关键参数详解

| 参数名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| **model** | String | 是 | 通常为 `wanx-v1` (需指定 specific task) 或特定的编辑模型版本。 |
| **input.prompt** | String | 是 | 修改意图的描述。例如：“换成一只红色的狐狸”。 |
| **input.image_url** | String | **是** | **原图链接**。支持 JPEG, PNG 等格式。 |
| **input.mask_url** | String | 否 | **蒙版链接**。黑白图，白色区域会被重绘。如果不传，某些模式下可能默认为全图重绘或智能识别。 |
| **parameters.style** | String | 否 | 输出风格，如 `<auto>`, `photography`, `anime` 等。 |

---

### 4. 代码示例 (Python SDK)

图像编辑通常使用 `ImageSynthesis` 类，但参数结构中增加了 `image_url` 和 `mask_url`。

> **注意：** 您需要先将本地图片上传到 OSS 或其他对象存储，获取 http/https 开头的 **URL** 才能调用此 API。

```python
import dashscope
from dashscope import ImageSynthesis
from http import HTTPStatus

# 1. 设置 API KEY
dashscope.api_key = 'YOUR_DASHSCOPE_API_KEY'

def edit_image():
    # 假设你已经有了原图和蒙版的 URL
    # 原图：一张照片
    orig_image_url = "https://your-domain.com/original.jpg"
    # 蒙版：一张黑白图，白色区域是你想修改的地方（比如你想修改照片里的一只狗，就把狗的位置涂白）
    mask_image_url = "https://your-domain.com/mask.jpg"

    prompt = "一只可爱的机器狗，赛博朋克风格"

    try:
        # 2. 调用编辑接口
        # 注意：通义万相的编辑功能通常也是通过 ImageSynthesis 调用
        # 但部分新版 API 可能有独立入口，请以文档最新 model 参数为准
        rsp = ImageSynthesis.call(
            model='wanx-v1',   # 或者是文档中指定的编辑专用模型
            prompt=prompt,
            image_url=orig_image_url,  # 传入原图
            mask_url=mask_image_url,   # 传入蒙版 (指定修改区域)
            style='photography',       # 保持摄影风格
            n=1,
            size='1024*1024'
        )

        # 3. 获取结果
        if rsp.status_code == HTTPStatus.OK:
            # 同样，这里可能是异步任务ID，也可能是直接结果，视具体 API 版本而定
            if rsp.output and rsp.output.task_id:
                print(f"编辑任务已提交，Task ID: {rsp.output.task_id}")
                # 这里需要配合 task_id 查询接口获取最终图片
            elif rsp.output and rsp.output.results:
                print(f"编辑成功，图片URL: {rsp.output.results[0].url}")
        else:
            print(f"请求失败: code={rsp.code}, message={rsp.message}")

    except Exception as e:
        print(f"发生异常: {e}")

if __name__ == '__main__':
    edit_image()
```

### 5. 常见应用场景与技巧

1.  **电商换模特/换背景:**
    *   **技巧:** 制作一张蒙版，将模特身上的衣服区域涂黑（保护），背景或模特头部涂白。
    *   **Prompt:** "一个在沙滩上的外国模特"（衣服保持不变，背景变了）。
2.  **去除路人 (Smart Erasure):**
    *   如果你不需要“生成新物体”只是想“擦除”，Prompt 可以留空或写“背景，无物体”，模型会尝试用背景填充蒙版区域。
3.  **Qwen-VL 的辅助作用:**
    *   虽然这个 API 用来画图，但你可以先调用 **Qwen-VL (视觉理解模型)** 来**自动生成 Mask**。
    *   *流程:* 发送图片给 Qwen-VL -> 问它“请给出图片中‘猫’的坐标或蒙版” -> 拿到坐标/蒙版 -> 传给 Wanx Image Edit API 进行修改。这实现了“全自动智能修图”。

### 6. 总结
这个链接对应的 API 重点在于 **“基于原图的修改”**。
*   如果你想**从零开始**画图，用上一个 `wan-image-generation`。
*   如果你想**把照片里的衣服换颜色、把背景换掉、或者去除多余元素**，就用这个 `image-edit` API。