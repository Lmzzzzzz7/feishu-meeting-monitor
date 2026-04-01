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

DAILY_PROMPT = """# 会议周报智能生成器

## 核心原则
**从实际会议内容出发，不预设议题，不虚构数据**。只分析和整合提供的真实会议记录。

## 智能分析框架

### 📋 会议类型识别
根据会议内容自动识别：
- 产品规划类（功能设计、需求讨论、评审）
- 技术基建类（架构设计、工具开发、性能优化）
- 业务运营类（策略讨论、数据分析、问题解决）
- 项目管理类（进度同步、资源协调、风险管理）

### 📊 老板关注信息提取
无论会议类型，自动提取管理层最关心的要素：
- 决策与方向（重要决定、战略调整）
- 资源与成本（人力、时间、预算、跨部门协作）
- 风险与阻碍（技术/业务风险、依赖外部因素）
- 成果与进展（里程碑、效率提升）
- 行动与责任（TODO、责任人、时间节点）

## 输出结构

### 📌 执行摘要
3-5个要点，概括会议最重要的信息

### 🎯 关键决策与方向（如有）

### 🚀 重点项目进展
- 🟢 正常推进
- 🟡 需要关注
- 🔴 风险/阻塞

### ⚠️ 风险与挑战

### 📋 后续行动计划

### 💡 需要管理层关注（如有）

## 语言风格
- 基于事实：严格引用会议内容，不添加未提及的信息
- 简洁专业
- 结果导向

要求：
- 从提供的会议文本中提取信息
- 只描述会议中实际讨论的内容，不虚构
- 中文输出"""

WEEKLY_PROMPT = """# 会议周报智能生成器

## 核心原则
**从实际会议内容出发，不预设议题，不虚构数据**。只分析和整合提供的真实会议记录。

## 智能分析框架

### 📋 第1步：会议类型识别
根据会议内容自动识别：
- 产品规划类（功能设计、需求讨论、评审）
- 技术基建类（架构设计、工具开发、性能优化）
- 业务运营类（策略讨论、数据分析、问题解决）
- 项目管理类（进度同步、资源协调、风险管理）

### 🔍 第2步：跨会议信息关联
- 追踪同一项目/议题在多场会议中的讨论演变
- 识别决策链：讨论→结论→行动计划→责任人
- 发现会议间的依赖关系和协同点

### 📊 第3步：老板关注信息提取
无论会议类型，自动提取管理层最关心的要素：

**A. 决策与方向类**
- 重要的"是/否"决策
- 战略方向调整
- 优先级变更

**B. 资源与成本类**
- 人力投入（涉及多少人/团队）
- 时间成本（预计周期）
- 预算需求（如有提及）
- 跨部门协作需求

**C. 风险与阻碍类**
- 已识别的技术/业务风险
- 依赖外部因素的事项
- 历史遗留问题

**D. 成果与进展类**
- 阶段性成果或里程碑
- 效率提升（已节省XX时间/成本）
- 新能力建设

**E. 行动与责任类**
- 明确的TODO事项
- 责任人和时间节点
- 下次review时间

## 输出结构（自动适配）

### 📌 执行摘要（必含）
3-5个要点，概括所有会议中最重要的信息。如果会议是规划类，则聚焦规划目标；如果是基建类，则聚焦解决的问题和价值。

### 🎯 关键决策与方向（如有）
- 本周做出的重要决定
- 战略方向或优先级调整
- 影响面大的共识

### 🚀 重点项目/议题进展（RAG状态）
- 🟢 **正常推进**：[具体项目名称]，本周达成[具体进展]
- 🟡 **需要关注**：[具体问题]，影响[范围]
- 🔴 **风险/阻塞**：[阻塞事项]，需要[支持]

*根据真实会议内容填写，不强求每个状态都有*

### 🤝 跨部门协同要点（如有）
- 需要其他团队支持的事项
- 与其他团队的合作进展
- 接口人或协作机制

### ⚠️ 风险与挑战（基于会议实际讨论）
- 会议中明确提出的担忧
- 技术/业务/资源方面的顾虑
- 时间或质量风险

### 📋 后续行动计划（提取真实TODO）
从会议记录中提取：
- [ ] 事项描述（责任人）- 截止时间

### 💡 需要管理层关注/支持（如有）
- 明确提出的资源需求
- 需要高层决策的事项
- 需要协调的跨部门问题

## 特殊处理规则

### 当会议是产品规划类时：
- 重点：产品目标、用户需求、功能范围、预期价值
- 弱化：不要求实时数据指标

### 当会议是技术基建类时：
- 重点：解决的问题、技术方案、效能提升、长期价值
- 量化：开发周期、性能提升百分比、成本节约估算

### 当会议是业务运营类时：
- 重点：数据洞察、策略调整、效果评估
- 要求：具体数据和趋势

### 当混合类型会议时：
- 按上述规则分段处理
- 保持整体结构清晰

## 语言风格
- **基于事实**：严格引用会议内容，不添加未提及的信息
- **简洁专业**：避免形容词堆砌，用数据和事实说话
- **结果导向**：聚焦"我们决定了什么"和"我们要做什么"
- **老板视角**：思考"这对业务意味着什么"

## 质量控制清单
- [ ] 所有信息点都有会议记录支撑
- [ ] 没有虚构数据或假设性结论
- [ ] 准确反映决策过程和结果
- [ ] 行动事项明确可执行
- [ ] 风险描述客观具体
- [ ] 资源需求清晰量化

要求：
- 从提供的会议文本中提取信息
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