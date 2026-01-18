#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub PR 自动化创建脚本
使用 GitHub API 创建 Pull Request
"""

import json
import sys
import os
import requests
import webbrowser

# 配置
OWNER = "amDosion"
REPO = "gemini-main"
HEAD = "docs/git-pr-setup"
BASE = "master"
TITLE = "docs: 添加 GitHub PR 模板和工作流配置"

# PR 描述
BODY = """# Pull Request

## 📋 描述 (Description)

本次 PR 为项目添加了完整的 GitHub 配置，包括 Issue 模板、Pull Request 模板、GitHub Actions 工作流和相关文档。

## 🔗 相关 Issue (Related Issue)

- N/A

## 🎯 变更类型 (Type of Change)

- [x] 📝 文档更新 (Documentation update)
- [x] 🔧 构建/配置相关 (Build/Config)

## 🔍 变更内容 (Changes)

### 主要变更
- 添加 Issue 模板（Bug 报告和功能请求）
- 添加 Pull Request 模板
- 配置 GitHub Actions 工作流
- 添加贡献指南和 Git 使用文档
- 更新 .gitignore

### 代码变更
- `.github/ISSUE_TEMPLATE/bug_report.md` - Bug 报告模板
- `.github/ISSUE_TEMPLATE/feature_request.md` - 功能请求模板
- `.github/PULL_REQUEST_TEMPLATE/default.md` - PR 模板
- `.github/workflows/pr-check.yml` - PR 检查工作流
- `.github/workflows/code-quality.yml` - 代码质量检查工作流
- `.github/CONTRIBUTING.md` - 贡献指南
- `.github/README.md` - GitHub 配置说明
- `docs/GIT_SETUP.md` - Git 配置和使用指南
- `docs/GIT_PR_SETUP_SUMMARY.md` - 配置总结文档
- `.gitignore` - 更新忽略规则

## 🧪 测试 (Testing)

- [x] 已进行手动测试 (Manual testing performed)
- [x] 测试通过 (All tests pass)

### 测试步骤
1. 验证所有模板文件格式正确
2. 验证 GitHub Actions 工作流语法正确
3. 验证文档链接和格式

## ✅ 检查清单 (Checklist)

- [x] 代码遵循项目的代码风格
- [x] 已进行自我审查
- [x] 文档已相应更新
- [x] 变更不会产生新的警告
- [x] 已检查代码安全性

## 🔐 安全注意事项 (Security Considerations)

- [x] 不涉及安全问题
- [x] 已审查安全影响

## 📝 额外说明 (Additional Notes)

本次配置为项目建立了标准的贡献流程和 PR 检查机制，将有助于：
- 规范 Issue 和 PR 的格式
- 自动检查 PR 标题格式（Conventional Commits）
- 自动运行代码质量检查
- 提供清晰的贡献指南
"""


def get_token():
    """从环境变量或 MCP 配置文件中获取 GitHub Token"""
    # 首先尝试环境变量
    token = os.environ.get('GITHUB_PERSONAL_ACCESS_TOKEN')
    if token:
        return token
    
    # 从 MCP 配置文件读取
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    mcp_config_path = os.path.join(repo_root, '.kiro', 'settings', 'mcp.json')
    
    if os.path.exists(mcp_config_path):
        try:
            with open(mcp_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                token = config.get('mcpServers', {}).get('github', {}).get('env', {}).get('GITHUB_PERSONAL_ACCESS_TOKEN')
                if token:
                    return token
        except Exception as e:
            print(f"警告: 无法读取 MCP 配置文件: {e}")
    
    return None


def create_pr():
    """创建 Pull Request"""
    token = get_token()
    if not token:
        print("错误: 未找到 GitHub Personal Access Token")
        print("请设置环境变量 GITHUB_PERSONAL_ACCESS_TOKEN 或在 .kiro/settings/mcp.json 中配置")
        sys.exit(1)
    
    # API 端点
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls"
    
    # 请求头
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }
    
    # 请求体
    data = {
        "title": TITLE,
        "head": HEAD,
        "base": BASE,
        "body": BODY
    }
    
    # 设置控制台编码为 UTF-8
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    print("正在创建 Pull Request...")
    print(f"  仓库: {OWNER}/{REPO}")
    print(f"  源分支: {HEAD}")
    print(f"  目标分支: {BASE}")
    print(f"  标题: {TITLE}")
    print()
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        pr_data = response.json()
        
        print("Pull Request 创建成功！")
        print()
        print("PR 信息:")
        print(f"  编号: #{pr_data['number']}")
        print(f"  标题: {pr_data['title']}")
        print(f"  状态: {pr_data['state']}")
        print(f"  URL: {pr_data['html_url']}")
        print()
        print(f"查看 PR: {pr_data['html_url']}")
        
        # 在浏览器中打开 PR
        webbrowser.open(pr_data['html_url'])
        
        return pr_data
        
    except requests.exceptions.HTTPError as e:
        error_msg = e.response.text if e.response else str(e)
        print("创建 PR 失败")
        print(f"错误信息: {error_msg}")
        
        if "already exists" in error_msg.lower():
            print()
            print("提示: 该分支的 PR 可能已存在")
            print(f"请访问: https://github.com/{OWNER}/{REPO}/pulls")
        
        sys.exit(1)
    except Exception as e:
        print(f"发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    create_pr()
