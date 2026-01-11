#!/usr/bin/env python3
"""
验证文件是否遵循模块化目录结构
"""
import sys
import os
import re

def validate_backend_service(file_path):
    """验证后端服务结构"""
    # 检查是否在服务目录中
    if 'backend/app/services/' not in file_path:
        return True, "不在服务目录中，跳过检查"
    
    # 提取服务名称
    match = re.search(r'backend/app/services/([^/]+)/', file_path)
    if not match:
        # 直接在 services/ 下的文件（如 base_provider.py, provider_factory.py）
        return True, "顶层服务文件"
    
    service_name = match.group(1)
    file_name = os.path.basename(file_path)
    
    # 检查是否是主协调器
    is_coordinator = file_name in [f'{service_name}_service.py', 'google_service.py', 'openai_service.py']
    
    if is_coordinator:
        # 主协调器应该组装子模块
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否导入了子模块
        has_imports = bool(re.search(r'from\s+\.\s+import\s+', content))
        
        if not has_imports:
            return False, f"主协调器 {file_name} 应该导入并组装子模块"
    
    return True, "结构正确"

def validate_frontend_component(file_path):
    """验证前端组件结构"""
    # 检查是否在组件目录中
    if 'frontend/components/' not in file_path:
        return True, "不在组件目录中，跳过检查"
    
    file_name = os.path.basename(file_path)
    
    # 检查是否是协调组件（通常是 View 或主组件）
    is_coordinator = 'View.tsx' in file_name or file_name in ['ChatView.tsx', 'ImageGenView.tsx']
    
    if is_coordinator:
        # 协调组件应该导入子组件
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否导入了子组件
        has_imports = bool(re.search(r'import\s+.*\s+from\s+[\'"]\./', content))
        
        if not has_imports:
            return False, f"协调组件 {file_name} 应该导入并组装子组件"
    
    return True, "结构正确"

def validate_modular_structure(file_path):
    """验证模块化结构"""
    if not os.path.exists(file_path):
        return 1, f"文件不存在: {file_path}"
    
    # 后端服务
    if 'backend/app/services/' in file_path:
        is_valid, message = validate_backend_service(file_path)
        if not is_valid:
            print(f"⚠️  {message}")
            print(f"   参考：.kiro/steering/structure.md 的模块化组织原则")
            return 0  # 警告但不阻止
        else:
            print(f"✅ 后端服务结构正确: {message}")
            return 0
    
    # 前端组件
    elif 'frontend/components/' in file_path:
        is_valid, message = validate_frontend_component(file_path)
        if not is_valid:
            print(f"⚠️  {message}")
            print(f"   参考：.kiro/steering/structure.md 的模块化组织原则")
            return 0  # 警告但不阻止
        else:
            print(f"✅ 前端组件结构正确: {message}")
            return 0
    
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python validate_modular_structure.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    exit_code, _ = validate_modular_structure(file_path)
    sys.exit(exit_code)
