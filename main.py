#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书会议监控系统 - 主程序
搜索会议纪要 -> 读取内容 -> AI分析 -> 生成报告
"""

import argparse
import json
import re
import sys
import time
import requests
from datetime import datetime
from pathlib import Path

from config import get_config, Config

# ========== 飞书 API ==========

def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    """获取应用 tenant_access_token"""
    url = f"{Config.FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
    data = {"app_id": app_id, "app_secret": app_secret}
    response = requests.post(url, json=data)
    result = response.json()
    return result.get("tenant_access_token", "")


def refresh_access_token(app_id: str, app_secret: str, refresh_token: str) -> dict:
    """刷新用户 access_token"""
    url = f"{Config.FEISHU_API_BASE}/authen/v1/refresh_access_token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    headers = {
        "Authorization": f"Bearer {get_tenant_access_token(app_id, app_secret)}"
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()


def search_documents(token: str, query: str = "a", page_size: int = 50) -> list:
    """搜索文档"""
    url = f"{Config.FEISHU_API_BASE}/search/v2/doc_wiki/search"
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "query": query,
        "wiki_filter": {"doc_types": ["DOCX", "DOC"]},
        "page_size": page_size,
        "sort_type": "CREATE_TIME"
    }
    response = requests.post(url, headers=headers, json=data)
    result = response.json()
    return result.get("data", {}).get("res_units", [])


def read_document_content(tenant_token: str, doc_token: str) -> str:
    """读取文档内容"""
    url = f"{Config.FEISHU_API_BASE}/docx/v1/documents/{doc_token}/blocks"
    headers = {"Authorization": f"Bearer {tenant_token}"}
    params = {"page_size": 100}

    all_text = []
    while url:
        response = requests.get(url, headers=headers, params=params)
        data = response.json().get("data", {})

        for block in data.get("items", []):
            text = extract_block_text(block)
            if text:
                all_text.append(text)

        # 分页
        page_token = data.get("page_token")
        if page_token:
            params["page_token"] = page_token
        else:
            break

    return "\n".join(all_text[:100])  # 限制长度


def extract_block_text(block: dict) -> str:
    """从 block 中提取文本"""
    block_type = block.get("block_type")
    text = ""

    if block_type == 2:  # text
        elements = block.get("text", {}).get("elements", [])
        for elem in elements:
            text += elem.get("text_run", {}).get("content", "")

    elif block_type in [1, 3, 4]:  # heading1, heading2, heading3
        heading = block.get("heading1") or block.get("heading2") or block.get("heading3")
        if heading:
            for elem in heading.get("elements", []):
                text += elem.get("text_run", {}).get("content", "")

    elif block_type == 12:  # bullet
        for elem in block.get("bullet", {}).get("elements", []):
            text += elem.get("text_run", {}).get("content", "")

    return text.strip()


# ========== DeepSeek API ==========

def analyze_with_deepseek(text: str, api_key: str) -> dict:
    """用 DeepSeek 分析会议内容"""
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    prompt = """你是一个会议分析助手。请分析以下会议纪要，提取：
1. 会议主题
2. 关键决策（不超过3条）
3. 风险问题（不超过3条）
4. 待办事项（包含负责人）
5. 涉及的项目名称

请用 JSON 格式输出：
{
    "主题": "...",
    "关键决策": ["...", "..."],
    "风险问题": ["...", "..."],
    "待办事项": [{"任务": "...", "负责人": "..."}],
    "涉及项目": ["...", "..."]
}"""

    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text[:8000]}
        ]
    }

    response = requests.post(url, headers=headers, json=data, timeout=30)
    result = response.json()

    try:
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        # 尝试解析 JSON
        return json.loads(content)
    except:
        return {"error": "解析失败", "raw": content}


# ========== 主流程 ==========

def search_and_filter(config: Config) -> list:
    """搜索文档并筛选"""
    print("\n[1] 搜索文档...")

    # 尝试用用户 token 搜索
    docs = search_documents(config.USER_ACCESS_TOKEN, config.SEARCH_QUERY)
    total = len(docs)
    print(f"    搜索到 {total} 个文档")

    if not docs:
        print("    ⚠️ 未找到文档，可能 token 已过期")
        return []

    print("\n[2] 筛选「文字记录：」开头的文档...")
    filtered = []
    for item in docs:
        title = re.sub(r'<[^>]+>', '', item.get('title_highlighted', ''))
        if title.startswith(config.SEARCH_PREFIX):
            meta = item.get('result_meta', {})
            filtered.append({
                'title': title,
                'token': meta.get('token', ''),
                'create_time': meta.get('create_time', 0),
                'url': meta.get('url', '')
            })

    print(f"    筛选出 {len(filtered)} 个文档")

    for i, doc in enumerate(filtered[:5], 1):
        date = datetime.fromtimestamp(doc['create_time']).strftime('%Y-%m-%d')
        print(f"    {i}. [{date}] {doc['title']}")

    return filtered


def analyze_documents(filtered_docs: list, config: Config):
    """分析文档"""
    if not filtered_docs:
        print("\n⚠️ 没有文档可分析")
        return

    print("\n[3] 读取文档内容并分析...")

    # 获取 tenant token 用于读取文档
    tenant_token = get_tenant_access_token(config.APP_ID, config.APP_SECRET)

    results = []
    for i, doc in enumerate(filtered_docs[:3], 1):  # 只分析前3个
        print(f"    分析 {i}/{min(3, len(filtered_docs))}: {doc['title'][:30]}...")

        # 读取内容
        content = read_document_content(tenant_token, doc['token'])
        if not content:
            print(f"    ⚠️ 无法读取文档内容")
            continue

        # AI 分析
        analysis = analyze_with_deepseek(content, config.DEEPSEEK_API_KEY)
        analysis['document_title'] = doc['title']
        analysis['document_url'] = doc['url']
        results.append(analysis)

        time.sleep(1)  # 避免 API 限流

    print(f"\n    完成 {len(results)} 个文档的分析")

    # 输出结果
    print("\n" + "=" * 50)
    print("分析结果")
    print("=" * 50)
    for r in results:
        print(f"\n📄 {r.get('document_title', 'N/A')}")
        print(json.dumps(r, ensure_ascii=False, indent=2))

    return results


def main():
    parser = argparse.ArgumentParser(description="飞书会议监控系统")
    parser.add_argument("--search", action="store_true", help="仅搜索和筛选")
    parser.add_argument("--analyze", action="store_true", help="仅分析")
    parser.add_argument("--all", action="store_true", help="完整流程")
    args = parser.parse_args()

    # 加载配置
    config = get_config()
    if not config.validate():
        sys.exit(1)

    # 检查是否需要刷新 token
    if config.REFRESH_TOKEN and not config.USER_ACCESS_TOKEN:
        print("\n[0] 尝试刷新 token...")
        result = refresh_access_token(config.APP_ID, config.APP_SECRET, config.REFRESH_TOKEN)
        if result.get("code") == 0:
            new_token = result.get("data", {}).get("access_token")
            new_refresh = result.get("data", {}).get("refresh_token")
            config.save_token(new_token, new_refresh)
            config.USER_ACCESS_TOKEN = new_token
            print("    ✅ Token 刷新成功")
        else:
            print(f"    ⚠️ Token 刷新失败: {result.get('msg')}")

    # 执行
    if args.search or args.all:
        filtered = search_and_filter(config)
        if args.search:
            return

    if args.analyze or args.all:
        analyze_documents(filtered if 'filtered' in dir() else [], config)


if __name__ == "__main__":
    main()