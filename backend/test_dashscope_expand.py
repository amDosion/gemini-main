"""
测试 DashScope 扩图 API
使用官方示例代码，测试用户云存储 URL 是否能正常调用

参考官方文档：https://help.aliyun.com/zh/model-studio/image-scaling-api
"""
import requests
import time
from http import HTTPStatus

# API Key（直接赋值）
api_key = "sk-19e01649859646c1904ee21fa08dc3ef"

# 测试用的云存储 URL（用户的兰空图床）
test_image_url = "https://img.dicry.com/2025/12/16/6940ed87ce65a.png"


def submit_task():
    """提交一个扩图任务（官方示例代码）"""
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2image/out-painting"

    # ✅ 官方示例的请求头（不包含 X-DashScope-OssResourceResolve）
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable"  # 异步调用
    }

    body = {
        "model": "image-out-painting",
        "input": {
            "image_url": test_image_url
        },
        "parameters": {
            "angle": 90,
            "x_scale": 1.5,
            "y_scale": 1.5
        }
    }

    print(f"提交扩图任务...")
    print(f"图片 URL: {test_image_url}")
    print(f"请求头: {headers}")
    
    response = requests.post(url, headers=headers, json=body)

    if response.status_code == HTTPStatus.OK:
        task_id = response.json().get('output', {}).get('task_id')
        print(f"✅ 任务提交成功，任务ID为: {task_id}")
        return task_id
    else:
        print(f"❌ 任务提交失败，状态码: {response.status_code}")
        print(f"响应: {response.text}")
        return None


def query_task_result(task_id):
    """根据任务ID轮询查询结果"""
    if not task_id:
        return

    url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    print("\n开始查询任务状态...")
    while True:
        response = requests.get(url, headers=headers)
        if response.status_code != HTTPStatus.OK:
            print(f"❌ 查询失败，状态码: {response.status_code}, 响应: {response.text}")
            break

        response_data = response.json()
        task_status = response_data.get('output', {}).get('task_status')

        if task_status == 'SUCCEEDED':
            print("✅ 任务成功完成！")
            print(f"任务成功响应数据: {response_data}")
            output_url = response_data.get('output', {}).get('output_image_url', "")
            print(f"生成图片 URL: {output_url}")
            return output_url
        elif task_status == 'FAILED':
            error_msg = response_data.get('output', {}).get('message', '')
            error_code = response_data.get('output', {}).get('code', '')
            print(f"❌ 任务失败。错误码: {error_code}, 错误信息: {error_msg}")
            break
        else:
            print(f"⏳ 任务正在处理中，当前状态: {task_status}...")
            time.sleep(5)  # 等待5秒后再次查询

    return None


if __name__ == '__main__':
    print("=" * 60)
    print("DashScope 扩图 API 测试（官方示例）")
    print("=" * 60)
    
    task_id = submit_task()
    if task_id:
        result_url = query_task_result(task_id)
        if result_url:
            print("\n" + "=" * 60)
            print("测试成功！")
            print(f"结果图片: {result_url}")
            print("=" * 60)
