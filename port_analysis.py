"""端口和路由分析"""
import requests

print("=" * 70)
print("🔍 端口和路由完整分析")
print("=" * 70)
print()

# 测试配置
tests = {
    "后端直接访问 (8000)": {
        "base": "http://localhost:8000",
        "endpoints": [
            "/",
            "/health", 
            "/api/profiles",
            "/api/sessions",
        ]
    },
    "前端代理访问 (5173)": {
        "base": "http://localhost:5173",
        "endpoints": [
            "/health",
            "/api/profiles", 
            "/api/sessions",
        ]
    }
}

for test_name, config in tests.items():
    print(f"\n{'='*70}")
    print(f"📍 {test_name}")
    print(f"   基础URL: {config['base']}")
    print(f"{'='*70}")
    
    for endpoint in config['endpoints']:
        url = f"{config['base']}{endpoint}"
        try:
            response = requests.get(url, timeout=3)
            status = "✅" if response.status_code == 200 else "❌"
            print(f"{status} {endpoint:25s} - 状态码: {response.status_code}")
            
            if response.status_code == 404:
                print(f"   响应: {response.text[:100]}")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ {endpoint:25s} - 连接失败")
        except Exception as e:
            print(f"❌ {endpoint:25s} - 错误: {e}")

print()
print("=" * 70)
print("📊 配置总结")
print("=" * 70)
print()
print("端口配置:")
print("  - 前端 Vite:  5173")
print("  - 后端 API:   8000")
print()
print("Vite 代理配置 (vite.config.ts):")
print("  /api/*    -> http://localhost:8000")
print("  /health   -> http://localhost:8000")
print()
print("预期行为:")
print("  1. 访问 http://localhost:5173/api/profiles")
print("  2. Vite 代理转发到 http://localhost:8000/api/profiles")
print("  3. 后端返回数据")
print()
