#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书会议监控系统 V2 - 基于 lark-cli
搜索 → 读取 → AI分析 → 生成日报/周报 → 发群
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# ========== 配置 ==========

load_dotenv(Path(__file__).parent / ".env")

FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID", "")
SEARCH_PREFIX = os.getenv("SEARCH_PREFIX", "文字记录：")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
MODEL_TEMP = float(os.getenv("DEEPSEEK_TEMP", "0.3"))

# ========== lark-cli 封装 ==========

def run_cli(cmd: list[str], timeout: int = 20) -> str:
    """运行 lark-cli 命令，返回 stdout"""
    result = subprocess.run(
        ["lark-cli"] + cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=Path(__file__).parent
    )
    if result.returncode != 0 and result.stderr:
        print(f"    ⚠️ CLI 警告: {result.stderr[:200]}")
    return result.stdout


def search_docs(query: str = SEARCH_PREFIX, limit: int = 20) -> list[dict]:
    """搜索文档，返回 [{token, title, create_time_iso}]"""
    output = run_cli([
        "docs", "+search",
        "--query", query,
        "--page-size", str(limit),
        "--format", "json"
    ])
    try:
        data = json.loads(output)
        results = data.get("data", {}).get("results", [])
        return [
            {
                "token": r.get("result_meta", {}).get("token", ""),
                "title": r.get("title_highlighted", "").replace("<h>", "").replace("</h>", ""),
                "create_time": r.get("result_meta", {}).get("create_time", 0),
                "create_time_iso": r.get("result_meta", {}).get("create_time_iso", ""),
                "url": r.get("result_meta", {}).get("url", ""),
            }
            for r in results
            if r.get("result_meta", {}).get("token")
        ]
    except Exception as e:
        print(f"    ⚠️ 搜索解析失败: {e}")
        return []


def fetch_doc(token: str, limit: int = 8000) -> str:
    """读取文档内容，返回 markdown 文本"""
    output = run_cli([
        "docs", "+fetch",
        "--doc", token,
        "--limit", str(limit),
        "--format", "json"
    ])
    try:
        data = json.loads(output)
        text = data.get("data", {}).get("markdown", "")
        # 清理控制字符
        text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
        return text
    except Exception as e:
        print(f"    ⚠️ 文档读取失败: {e}")
        return ""


# ========== DeepSeek AI 分析 ==========

def analyze_with_deepseek(content: str, prompt: str) -> str:
    """调用 DeepSeek 分析文本内容"""
    import requests

    resp = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        },
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": content[:12000]}
            ],
            "temperature": MODEL_TEMP
        },
        timeout=60
    )
    result = resp.json()
    return result.get("choices", [{}])[0].get("message", {}).get("content", "")


# ========== 日报生成 Prompt ==========

DAILY_PROMPT = """# 会议周报生成器（管理层决策版）

## 核心任务
从会议记录中提取信息，执行业务升维四步法，生成可直接决策的日报。

## 四步法重构

### 第1步：硬信息提取
将模糊表述转化为具体量化

### 第2步：价值量化翻译
技术语言翻译为业务价值

### 第3步：风险三要素
概率、影响、预案

### 第4步：行动SMART化
具体产出物（责任人，DDL，验收标准）

## 输出结构

### 📌 执行摘要
动作 + 量化影响 + 决策需求

### 🎯 决策清单
已确定 / 待决策

### 🚀 项目进展
项目名称、进度、成果、阻塞、下周目标

### ⚠️ 风险预警
风险描述 + 概率 + 影响 + 应对 + 预案

### 💡 管理层决策需求
🔴 需立即决策 / 🟡 需要知晓 / 🟢 需要支持

## 自检清单
- [ ] 数字有来源或估算依据
- [ ] 风险有应对预案
- [ ] 行动项有责任人+DDL+标准
- [ ] 业务价值已量化
- [ ] 决策需求明确具体

要求：
- 从会议文本提取信息
- 严格按四步法重构
- 不虚构
- 中文输出"""

WEEKLY_PROMPT = """# 会议周报生成器（管理层决策版）

## 核心任务
从会议记录中提取信息，执行业务升维四步法，生成可直接决策的周报。

## 四步法重构（必须严格执行）

### 第1步：硬信息提取
将所有模糊表述转化为具体量化：
- 早期阶段 → 具体周期和里程碑日期
- 需要支持 → 缺口资源类型和数量，明确影响
- 有风险 → 具体耗时/成本，参考依据

### 第2步：价值量化翻译（关键）
技术语言强制翻译为业务价值：
- 解放产能 → 释放X人/月，价值¥Y万/月，可重投入XX项目
- 建知识库 → 减少重复咨询X%，响应从A小时缩短至B分钟
- 孵化模式 → 试错成本X人天，失败可控，成功可规模化

### 第3步：风险三要素计算
每个风险必须量化：
- 概率：基于什么判断（数据/历史）
- 影响：延迟多久/多花多少/影响多少人
- 预案：Plan B具体方案，触发条件

### 第4步：行动SMART化
- [ ] 具体产出物（责任人，DDL，验收标准）

---

## 输出结构（严格排序）

### 📌 执行摘要
格式：动作 + 量化影响 + 决策需求

### 🎯 决策清单
**已确定：**
- ✅ 明确结论1
- ✅ 明确结论2

**待决策：**
- ❓ 待确认事项1（影响范围）
- ❓ 待确认事项2（资源需求）

### 🚀 项目进展
**项目名称 - 状态标识**
- 进度：X%（完成内容）
- 本周成果：具体产出1；具体产出2
- 关键阻塞：具体问题，影响，负责人
- 下周目标：具体交付物

### ⚠️ 风险预警
**风险1：风险描述**
- 概率：高/中/低（依据）
- 影响：具体量化指标
- 应对：具体动作
- 预案：触发条件 + 备选方案

### 💡 管理层决策需求
🔴 需立即决策：
- 决策事项（影响）

🟡 需要知晓：
- 重要信息同步

🟢 需要支持：
- 协调事项（如有）

---

## 自检清单（生成后核对）
- [ ] 所有数字都有来源或估算依据
- [ ] 每个风险都有应对预案
- [ ] 每个行动项都有责任人+DDL+标准
- [ ] 业务价值已量化（成本/收入/效率）
- [ ] 决策需求明确具体
- [ ] 无模糊表述（"待定"、"待明确"等）

要求：
- 从提供的会议文本中提取信息
- 严格按四步法重构
- 只描述会议中实际讨论的内容，不虚构
- 中文输出"""


# ========== 主流程 ==========

def get_docs_by_date(days: int = 0, weekday_only: bool = True) -> list[dict]:
    """获取指定日期范围的文档"""
    docs = search_docs(limit=50)
    
    filtered = []
    now = datetime.now()
    
    for doc in docs:
        if not doc.get("token"):
            continue
        if SEARCH_PREFIX and not doc["title"].startswith(SEARCH_PREFIX):
            continue
        
        if days == 0:
            # 当天
            doc_date = datetime.fromtimestamp(doc["create_time"]) if doc["create_time"] else None
            if doc_date and doc_date.date() == now.date():
                filtered.append(doc)
        else:
            # 最近 N 天
            doc_date = datetime.fromtimestamp(doc["create_time"]) if doc["create_time"] else None
            if doc_date:
                days_ago = (now - doc_date).days
                in_range = days_ago <= days
                is_weekday = doc_date.weekday() < 5 if weekday_only else True
                if in_range and is_weekday:
                    filtered.append(doc)
    
    return filtered


def send_to_chat(message: str):
    """发送消息到飞书群"""
    if not TARGET_CHAT_ID:
        print("    ⚠️ 未配置 TARGET_CHAT_ID，跳过发送")
        return False
    
    output = run_cli([
        "im", "+messages-send",
        "--chat-id", TARGET_CHAT_ID,
        "--text", message,
        "--as", "bot",
        "--format", "json"
    ], timeout=15)
    
    try:
        data = json.loads(output)
        if data.get("ok"):
            print("    ✅ 消息已发送")
            return True
        else:
            print(f"    ⚠️ 发送失败: {data.get('error', {}).get('message', output[:200])}")
            return False
    except:
        print(f"    ⚠️ 发送结果解析失败: {output[:200]}")
        return False


def main():
    parser = argparse.ArgumentParser(description="飞书会议监控系统 V2")
    parser.add_argument("--today", action="store_true", help="分析当天会议，生成日报")
    parser.add_argument("--week", action="store_true", help="分析上周所有会议，生成周报")
    parser.add_argument("--analyze", metavar="TOKEN", help="分析指定文档 token")
    parser.add_argument("--send", action="store_true", help="生成后发送到飞书群")
    parser.add_argument("--quiet", action="store_true", help="静默模式，减少输出")
    args = parser.parse_args()

    if not DEEPSEEK_API_KEY:
        print("❌ 未配置 DEEPSEEK_API_KEY")
        sys.exit(1)

    log = lambda x: print(x) if not args.quiet else None

    # 分析指定文档
    if args.analyze:
        log(f"\n[1] 读取文档: {args.analyze}")
        content = fetch_doc(args.analyze)
        if not content:
            print("❌ 文档内容为空")
            sys.exit(1)
        log(f"    已读取 {len(content)} 字符")
        log("\n[2] AI 分析中...")
        result = analyze_with_deepseek(content, DAILY_PROMPT)
        print(f"\n{result}")
        if args.send:
            send_to_chat(result)
        return

    # 日报（当天）
    if args.today:
        log("\n📋 生成日报...")
        docs = get_docs_by_date(days=0)
        log(f"    找到 {len(docs)} 篇当天文档")
        
        if not docs:
            print("⚠️ 当天没有会议记录")
            return

        # 读取所有文档
        all_content = ""
        for i, doc in enumerate(docs, 1):
            log(f"    [{i}/{len(docs)}] 读取: {doc['title'][:30]}...")
            content = fetch_doc(doc["token"])
            if content:
                all_content += f"\n\n--- 会议{i} ---\n{content[:6000]}"
            time.sleep(1)

        log("\n[2] AI 分析中...")
        result = analyze_with_deepseek(all_content, DAILY_PROMPT)
        
        log("\n[3] 输出结果")
        print(f"\n{'='*60}\n{result}\n{'='*60}")
        
        if args.send:
            send_to_chat(result)
        return

    # 周报（上周）
    if args.week:
        log("\n📊 生成周报...")
        today = datetime.now()
        # 上周：7-13天前的工作日
        docs = get_docs_by_date(days=7 + (today.weekday() + 6) % 7)
        # 过滤只保留上周（7-13天前）
        week_ago = today - timedelta(days=13)
        docs = [d for d in docs if datetime.fromtimestamp(d["create_time"]) >= week_ago]
        log(f"    找到 {len(docs)} 篇上周文档")

        if not docs:
            print("⚠️ 上周没有会议记录")
            return

        all_content = ""
        for i, doc in enumerate(docs, 1):
            log(f"    [{i}/{len(docs)}] 读取: {doc['title'][:30]}...")
            content = fetch_doc(doc["token"])
            if content:
                all_content += f"\n\n--- 会议{i} ---\n{content[:6000]}"
            time.sleep(1)

        log("\n[2] AI 分析中...")
        result = analyze_with_deepseek(all_content, WEEKLY_PROMPT)
        
        log("\n[3] 输出结果")
        print(f"\n{'='*60}\n{result}\n{'='*60}")
        
        if args.send:
            send_to_chat(result)
        return

    # 无参数，显示帮助
    parser.print_help()


if __name__ == "__main__":
    main()