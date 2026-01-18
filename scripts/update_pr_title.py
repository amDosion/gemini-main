#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub PR 标题更新脚本
用于更新 Pull Request 的标题（例如：将中文改为英文以通过 CI 检查）
"""

import json
import sys
import os
import requests

# 配置
OWNER = "amDosion"
REPO = "gemini-main"
BRANCH = "file-ops-arch-b75fb"  # 当前分支名
NEW_TITLE = "docs: complete attachment processing analysis and add unified backend design"


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


def find_pr_by_branch(token, branch):
    """根据分支名查找对应的 PR"""
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    params = {
        "head": f"{OWNER}:{branch}",
        "state": "open"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        prs = response.json()
        
        if prs:
            return prs[0]  # 返回第一个匹配的 PR
        return None
    except Exception as e:
        print(f"查找 PR 失败: {e}")
        return None


def update_pr_title(token, pr_number, new_title):
    """更新 PR 标题"""
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls/{pr_number}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }
    
    data = {
        "title": new_title
    }
    
    try:
        response = requests.patch(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        error_msg = e.response.text if hasattr(e, 'response') and e.response else str(e)
        print(f"更新 PR 标题失败: {error_msg}")
        raise


def main():
    """主函数"""
    token = get_token()
    if not token:
        print("错误: 未找到 GitHub Personal Access Token")
        print("请设置环境变量 GITHUB_PERSONAL_ACCESS_TOKEN 或在 .kiro/settings/mcp.json 中配置")
        sys.exit(1)
    
    print(f"正在查找分支 '{BRANCH}' 的 PR...")
    pr = find_pr_by_branch(token, BRANCH)
    
    if not pr:
        print(f"错误: 未找到分支 '{BRANCH}' 的 PR")
        print(f"请访问: https://github.com/{OWNER}/{REPO}/pulls")
        sys.exit(1)
    
    print(f"找到 PR: #{pr['number']} - {pr['title']}")
    print(f"当前标题: {pr['title']}")
    print(f"新标题: {NEW_TITLE}")
    print()
    
    if pr['title'] == NEW_TITLE:
        print("PR 标题已经是目标标题，无需更新。")
        return
    
    print("正在更新 PR 标题...")
    updated_pr = update_pr_title(token, pr['number'], NEW_TITLE)
    
    print("PR 标题更新成功！")
    print()
    print("更新后的 PR 信息:")
    print(f"  编号: #{updated_pr['number']}")
    print(f"  标题: {updated_pr['title']}")
    print(f"  URL: {updated_pr['html_url']}")


if __name__ == "__main__":
    main()
