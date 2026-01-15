"""
Tongyi Image API 测试脚本

测试文生图迁移是否成功：
1. 登录获取 access_token
2. 调用 /api/tongyi/image/generate 端点
3. 验证图像生成结果
"""
import requests
import json
import sys

# 配置
BACKEND_URL = "http://localhost:21574"
USERNAME = "xcgrmini@example.com"
PASSWORD = "rRMRbChRoAWt&@5Rs!rYNGO8dg42gk"


def log_info(msg: str):
    print(f"[INFO] {msg}")


def log_success(msg: str):
    print(f"[SUCCESS] {msg}")


def log_error(msg: str):
    print(f"[ERROR] {msg}")


def login() -> str:
    """登录并获取 access_token"""
    log_info(f"正在登录: {USERNAME}")

    response = requests.post(
        f"{BACKEND_URL}/api/auth/login",
        json={
            "email": USERNAME,
            "password": PASSWORD
        },
        headers={"Content-Type": "application/json"}
    )

    if response.status_code != 200:
        log_error(f"登录失败: HTTP {response.status_code}")
        log_error(f"响应: {response.text}")
        sys.exit(1)

    data = response.json()
    access_token = data.get("access_token")

    if not access_token:
        log_error(f"未获取到 access_token: {data}")
        sys.exit(1)

    log_success(f"登录成功，获取到 access_token: {access_token[:20]}...")
    return access_token


def test_image_generation(access_token: str):
    """测试文生图 API"""
    log_info("正在测试文生图 API...")

    # 测试请求参数
    request_body = {
        "model_id": "wan2.6-t2i",
        "prompt": "一个美丽的中国女孩，穿着传统服饰，站在樱花树下",
        "aspect_ratio": "1:1",
        "resolution": "1.25K",
        "num_images": 1
    }

    log_info(f"请求参数: {json.dumps(request_body, ensure_ascii=False, indent=2)}")

    response = requests.post(
        f"{BACKEND_URL}/api/tongyi/image/generate",
        json=request_body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        },
        timeout=300  # 图像生成可能需要较长时间
    )

    log_info(f"响应状态码: {response.status_code}")

    if response.status_code != 200:
        log_error(f"文生图失败: HTTP {response.status_code}")
        try:
            error_data = response.json()
            log_error(f"错误详情: {json.dumps(error_data, ensure_ascii=False, indent=2)}")
        except:
            log_error(f"响应内容: {response.text}")
        return False

    data = response.json()
    log_success(f"文生图成功！")
    log_info(f"响应数据: {json.dumps(data, ensure_ascii=False, indent=2)}")

    # 验证响应结构
    if data.get("success") and data.get("images"):
        log_success(f"生成了 {len(data['images'])} 张图片")
        for i, img in enumerate(data["images"]):
            log_success(f"  图片 {i+1}: {img.get('url', 'N/A')[:80]}...")
        return True
    else:
        log_error("响应结构不符合预期")
        return False


def test_without_auth():
    """测试无认证请求（应该返回 401）"""
    log_info("测试无认证请求...")

    response = requests.post(
        f"{BACKEND_URL}/api/tongyi/image/generate",
        json={"model_id": "wan2.6-t2i", "prompt": "test"},
        headers={"Content-Type": "application/json"},
        timeout=10
    )

    if response.status_code == 401:
        log_success("无认证请求正确返回 401")
        return True
    else:
        log_error(f"无认证请求返回了意外的状态码: {response.status_code}")
        return False


def check_backend_running():
    """检查后端服务是否运行"""
    log_info("检查后端服务...")
    try:
        # 使用 auth/config 端点检查后端状态（该端点始终可用）
        response = requests.get(f"{BACKEND_URL}/api/auth/config", timeout=5)
        if response.status_code == 200:
            log_success("后端服务运行中")
            return True
        else:
            log_error(f"后端服务响应异常: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        log_error("无法连接到后端服务")
        log_error(f"请确保后端服务正在运行: cd backend && python -m uvicorn app.main:app --port 21574")
        return False
    except Exception as e:
        log_error(f"检查后端失败: {e}")
        return False


def main():
    print("=" * 60)
    print("Tongyi Image API 测试")
    print("=" * 60)

    # 前置检查: 后端服务是否运行
    print("\n--- 前置检查: 后端服务 ---")
    if not check_backend_running():
        log_error("请先启动后端服务后再运行测试")
        return 1

    # 测试 1: 无认证请求
    print("\n--- 测试 1: 无认证请求 ---")
    test_without_auth()

    # 测试 2: 登录
    print("\n--- 测试 2: 登录 ---")
    access_token = login()

    # 测试 3: 文生图
    print("\n--- 测试 3: 文生图 ---")
    success = test_image_generation(access_token)

    print("\n" + "=" * 60)
    if success:
        log_success("所有测试通过！文生图迁移成功！")
    else:
        log_error("测试失败，请检查错误日志")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
