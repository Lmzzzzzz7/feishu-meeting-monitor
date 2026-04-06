#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

"""
飞书会议监控系统 V2 - 基于 lark-cli
搜索 → 读取 → AI分析 → 生成日报/周报 → 发群
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import get_config

# ========== 配置（从 .env 加载，见 config.py） ==========

CONFIG = get_config()

FEISHU_APP_ID = CONFIG.APP_ID
FEISHU_APP_SECRET = CONFIG.APP_SECRET
DEEPSEEK_API_KEY = CONFIG.DEEPSEEK_API_KEY
TARGET_CHAT_ID = CONFIG.TARGET_CHAT_ID
SEARCH_PREFIX = CONFIG.SEARCH_PREFIX
MODEL = CONFIG.DEEPSEEK_MODEL
MODEL_TEMP = CONFIG.deepseek_temp()

PROJECT_ROOT = Path(__file__).parent
LOGGER = logging.getLogger("feishu-meeting-monitor")


def setup_logging(quiet: bool = False) -> None:
    """Write logs to logs/ and optionally silence console output."""
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "feishu-meeting-monitor.log"

    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False

    # Reset handlers to avoid duplicate logs if main() is called twice.
    for h in list(LOGGER.handlers):
        LOGGER.removeHandler(h)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1_000_000,
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)
    LOGGER.addHandler(file_handler)

    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setLevel(logging.WARNING if quiet else logging.INFO)
    console_handler.setFormatter(fmt)
    LOGGER.addHandler(console_handler)


# ========== lark-cli 封装 ==========

def run_cli(cmd: list[str], timeout: int = 20) -> str:
    """运行 lark-cli 命令，返回 stdout。

    说明：这里不抛异常，统一由上层根据输出做 JSON 解析/判错。
    """
    try:
        result = subprocess.run(
            ["lark-cli"] + cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=PROJECT_ROOT,
        )
    except FileNotFoundError:
        LOGGER.error("lark-cli 未找到，请先安装：npm install -g @larksuite/cli")
        return ""
    except subprocess.TimeoutExpired:
        LOGGER.error("lark-cli 调用超时: %s", " ".join(cmd))
        return ""

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        if stderr:
            LOGGER.warning("lark-cli 非 0 返回(%s)：%s", result.returncode, stderr[:300])
        else:
            LOGGER.warning("lark-cli 非 0 返回(%s)：无 stderr", result.returncode)

    return result.stdout or ""


def search_docs(query: str = SEARCH_PREFIX, limit: int = 20) -> dict:
    """搜索文档。

    Returns:
        {"ok": bool, "docs": list[dict], "error": str}
    """
    output = run_cli(
        [
            "docs",
            "+search",
            "--query",
            query,
            "--page-size",
            str(limit),
            "--format",
            "json",
        ]
    )

    if not output.strip():
        return {"ok": False, "docs": [], "error": "lark-cli search 输出为空"}

    try:
        data = json.loads(output)
        results = data.get("data", {}).get("results", [])
        docs = [
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
        return {"ok": True, "docs": docs, "error": ""}
    except Exception as e:
        return {"ok": False, "docs": [], "error": f"搜索解析失败: {e}"}


def fetch_doc(token: str, limit: int = 8000) -> dict:
    """读取文档内容。

    Returns:
        {"ok": bool, "content": str, "error": str}
    """
    output = run_cli(
        [
            "docs",
            "+fetch",
            "--doc",
            token,
            "--limit",
            str(limit),
            "--format",
            "json",
        ]
    )

    if not output.strip():
        return {"ok": False, "content": "", "error": "lark-cli fetch 输出为空"}

    try:
        data = json.loads(output)
        text = data.get("data", {}).get("markdown", "")
        # 清理控制字符
        text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
        return {"ok": True, "content": text, "error": ""}
    except Exception as e:
        return {"ok": False, "content": "", "error": f"文档读取失败: {e}"}



# ========== DeepSeek AI 分析 ==========

def analyze_with_deepseek(content: str, prompt: str) -> str:
    """调用 DeepSeek 分析文本内容（带重试与错误提示）。

    失败时抛出 RuntimeError，交由上层统一处理与记录日志。
    """
    import requests

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": content[:12000]},
        ],
        "temperature": MODEL_TEMP,
    }

    last_err: str | None = None
    retry_waits = [0, 2, 5]

    for attempt, wait_s in enumerate(retry_waits, 1):
        if wait_s:
            time.sleep(wait_s)

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
        except requests.RequestException as e:
            last_err = f"DeepSeek 请求异常: {e}"
            LOGGER.warning("DeepSeek attempt %s/%s failed: %s", attempt, len(retry_waits), last_err)
            continue

        # Retryable status codes
        if resp.status_code in (429, 500, 502, 503, 504):
            last_err = f"DeepSeek HTTP {resp.status_code}: {resp.text[:300]}"
            LOGGER.warning("DeepSeek attempt %s/%s retryable: %s", attempt, len(retry_waits), last_err)
            continue

        if resp.status_code != 200:
            # 非可重试错误（多为鉴权/参数问题）
            msg = f"DeepSeek HTTP {resp.status_code}: {resp.text[:300]}"
            LOGGER.error(msg)
            raise RuntimeError(msg)

        try:
            result = resp.json()
        except Exception:
            msg = f"DeepSeek 响应非 JSON: {resp.text[:300]}"
            LOGGER.error(msg)
            raise RuntimeError(msg)

        text = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        if not text:
            msg = f"DeepSeek 返回空内容: {json.dumps(result, ensure_ascii=False)[:500]}"
            LOGGER.error(msg)
            raise RuntimeError(msg)

        return text

    raise RuntimeError(last_err or "DeepSeek 调用失败")


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

WEEKLY_PROMPT = """你是公司老板的决策助理。请基于输入的多篇会议纪要，生成「资源与优先级周报」，帮助老板在 2 分钟内完成拍板。

重要约束：
- 只基于输入，不虚构；不确定就写「会议未明确」
- 聚焦：资源投入、人力排期、优先级取舍
- 尽量短：<= 900 中文字、<= 35 行
- 不要复述讨论过程，不要技术细节

输出（固定格式）：

## 🔴 需要老板拍板（Top 3）
（按紧急程度排序；如果没有，请写：本周无需要拍板事项。）
- [决策1] 决策点：一句话说明要拍什么板
  - 推荐：A/B/推荐项（写清推荐原因一句话）
  - 资源/优先级：需要什么资源，或把哪个项目从 P? 调整到 P?
  - 影响：对交付/目标/成本/风险的影响（一句话）
  - 最晚时间：若会议未明确，写「本周内」
  - 来源：会议标题 + 日期 + 链接（若有）

## 📌 资源与优先级建议（P0/P1/P2，最多 5 项）
- 项目/议题：XXX | 优先级：P?（理由一句话）
  - 本周变化：状态变化一句话（例如：从讨论→已定方案 / 从推进→阻塞）
  - 资源诉求：缺口/需要老板支持什么（一句话）
  - 下一步：Owner + DDL（若会议未明确可省略）

## ⚠️ 风险雷达（最多 3 条）
- 风险：XXX | 概率：高/中/低 | 影响：高/中/低 | 建议动作：一句话

要求：
- 不要输出长段落
- 不要把同一信息重复写在多个部分
- 中文输出
"""


# ========== 组装内容 / 截断提示 ==========

def build_combined_content(docs: list[dict]) -> tuple[str, list[str], dict]:
    """读取并拼接多篇会议内容。

    Returns:
        combined_content, warnings, stats
    """
    combined = ""
    warnings: list[str] = []
    stats = {
        "docs_total": len(docs),
        "docs_fetched": 0,
        "docs_truncated": 0,
        "total_chars": 0,
        "combined_truncated": False,
    }

    for i, doc in enumerate(docs, 1):
        title = (doc.get("title") or "").strip()
        token = doc.get("token")

        LOGGER.info("[%s/%s] fetch doc: %s", i, len(docs), title[:60])

        fr = fetch_doc(token)
        if not fr.get("ok"):
            LOGGER.warning("fetch failed token=%s title=%s err=%s", token, title[:60], fr.get("error"))
            continue

        content = fr.get("content", "")
        if not content:
            LOGGER.warning("fetch empty token=%s title=%s", token, title[:60])
            continue

        stats["docs_fetched"] += 1
        stats["total_chars"] += len(content)

        clipped = content
        if len(content) > 6000:
            stats["docs_truncated"] += 1
            clipped = content[:6000]
            warnings.append(f"单篇会议内容过长已截断：{title[:40]}")

        dt_str = ""
        if doc.get("create_time"):
            try:
                dt_str = datetime.fromtimestamp(doc["create_time"]).strftime("%Y-%m-%d")
            except Exception:
                dt_str = ""
        if not dt_str:
            dt_str = (doc.get("create_time_iso") or "").strip()

        url = (doc.get("url") or "").strip()

        header_lines = [
            f"--- 会议{i} ---",
            f"标题: {title}" if title else "",
            f"时间: {dt_str}" if dt_str else "",
            f"链接: {url}" if url else "",
            "内容:",
        ]
        header = "\n".join([x for x in header_lines if x])

        combined += f"\n\n{header}\n{clipped}"
        time.sleep(1)

    # DeepSeek 单次输入上限
    if len(combined) > 12000:
        stats["combined_truncated"] = True
        warnings.append("本周会议总内容超过模型上限已截断，结果可能不完整")

    return combined, warnings, stats


# ========== 主流程 ==========

def get_docs_by_date(days: int = 0, weekday_only: bool = True) -> dict:
    """获取指定日期范围的文档。

    Returns:
        {"ok": bool, "docs": list[dict], "error": str}
    """
    sr = search_docs(limit=50)
    if not sr.get("ok"):
        return {"ok": False, "docs": [], "error": sr.get("error", "搜索失败")}

    docs = sr.get("docs", [])

    filtered: list[dict] = []
    now = datetime.now()

    for doc in docs:
        if not doc.get("token"):
            continue
        if SEARCH_PREFIX and not doc.get("title", "").startswith(SEARCH_PREFIX):
            continue

        if days == 0:
            # 当天
            doc_date = datetime.fromtimestamp(doc["create_time"]) if doc.get("create_time") else None
            if doc_date and doc_date.date() == now.date():
                filtered.append(doc)
        else:
            # 最近 N 天
            doc_date = datetime.fromtimestamp(doc["create_time"]) if doc.get("create_time") else None
            if doc_date:
                days_ago = (now - doc_date).days
                in_range = days_ago <= days
                is_weekday = doc_date.weekday() < 5 if weekday_only else True
                if in_range and is_weekday:
                    filtered.append(doc)

    # 稳定排序：按创建时间升序（便于周报时间线）
    filtered.sort(key=lambda d: d.get("create_time", 0))

    return {"ok": True, "docs": filtered, "error": ""}


def send_to_chat(message: str, *, chat_id: str | None = None) -> tuple[bool, str]:
    """发送消息到飞书群。

    Args:
        message: 文本消息
        chat_id: 可选，覆盖默认 TARGET_CHAT_ID

    Returns:
        (ok, error_message)
    """
    target = (chat_id or TARGET_CHAT_ID or "").strip()
    if not target:
        return False, "未配置 TARGET_CHAT_ID"

    output = run_cli(
        [
            "im",
            "+messages-send",
            "--chat-id",
            target,
            "--text",
            message,
            "--as",
            "bot",
            "--format",
            "json",
        ],
        timeout=15,
    )

    if not output.strip():
        return False, "lark-cli send 输出为空"

    try:
        data = json.loads(output)
    except Exception:
        return False, f"发送结果解析失败: {output[:200]}"

    if data.get("ok"):
        return True, ""

    err = data.get("error", {}) or {}
    msg = err.get("message") or output[:200]
    return False, f"发送失败: {msg}"

def health_check(send: bool = False) -> tuple[bool, list[str]]:
    """最小健康检查：配置 + lark-cli + DeepSeek。"""
    notes: list[str] = []

    ok, errors = CONFIG.validate(require_chat_id=send)
    if not ok:
        return False, errors

    # lark-cli
    out = run_cli(["--version"], timeout=10)
    if not out.strip():
        return False, ["lark-cli 不可用：请检查是否安装/是否在 PATH 中"]
    notes.append(f"lark-cli: {out.strip().splitlines()[0][:80]}")

    # Feishu search
    sr = search_docs(limit=1)
    if not sr.get("ok"):
        return False, [f"Feishu 搜索失败: {sr.get('error')}"]
    notes.append("Feishu 搜索：OK")

    # DeepSeek minimal call
    try:
        _ = analyze_with_deepseek("ping", "请只回复 OK")
    except Exception as e:
        return False, [f"DeepSeek 调用失败: {e}"]
    notes.append("DeepSeek：OK")

    return True, notes


def main():
    parser = argparse.ArgumentParser(description="飞书会议监控系统 V2")
    parser.add_argument("--today", action="store_true", help="分析当天会议，生成日报")
    parser.add_argument("--week", action="store_true", help="分析上周所有会议，生成周报")
    parser.add_argument("--analyze", metavar="TOKEN", help="分析指定文档 token")
    parser.add_argument("--send", action="store_true", help="生成后发送到飞书群")
    parser.add_argument("--quiet", action="store_true", help="静默模式，减少输出")
    parser.add_argument("--dry-run", action="store_true", help="运行但不发送消息（用于上线前验证）")
    parser.add_argument("--health-check", action="store_true", help="检查配置/权限/依赖是否可用")
    args = parser.parse_args()

    setup_logging(quiet=args.quiet)
    LOGGER.info("run start args=%s", vars(args))

    ok, errors = CONFIG.validate(require_chat_id=(args.send and not args.dry_run))
    if not ok:
        for e in errors:
            LOGGER.error(e)
        print("❌ 配置校验失败：" + "；".join(errors))
        sys.exit(2)

    if args.health_check:
        hc_ok, hc_notes = health_check(send=(args.send and not args.dry_run))
        if hc_ok:
            msg = "✅ health-check 通过\n" + "\n".join(f"- {n}" for n in hc_notes)
            print(msg)
            LOGGER.info(msg)
            if args.send and not args.dry_run:
                ok_send, err = send_to_chat(msg)
                if not ok_send:
                    LOGGER.error("health-check send failed: %s", err)
            sys.exit(0)
        else:
            msg = "❌ health-check 失败\n" + "\n".join(f"- {n}" for n in hc_notes)
            print(msg)
            LOGGER.error(msg)
            sys.exit(2)

    log = (lambda x: print(x)) if not args.quiet else (lambda _x: None)

    # 分析指定文档
    if args.analyze:
        log(f"\n[1] 读取文档: {args.analyze}")
        fr = fetch_doc(args.analyze)
        if not fr.get("ok"):
            msg = f"❌ 文档读取失败：{fr.get('error')}"
            print(msg)
            LOGGER.error(msg)
            sys.exit(3)

        content = fr.get("content", "")
        if not content:
            msg = "❌ 文档内容为空"
            print(msg)
            LOGGER.error(msg)
            sys.exit(3)

        log(f"    已读取 {len(content)} 字符")
        log("\n[2] AI 分析中...")
        try:
            result = analyze_with_deepseek(content, DAILY_PROMPT)
        except Exception as e:
            LOGGER.exception("DeepSeek analyze failed")
            print(f"❌ AI 分析失败：{e}")
            sys.exit(4)

        print(f"\n{result}")

        if args.send:
            if args.dry_run:
                LOGGER.info("dry-run: skip sending")
            else:
                ok_send, err = send_to_chat(result)
                if not ok_send:
                    LOGGER.error(err)
                    sys.exit(5)
        return

    # 日报（当天）
    if args.today:
        log("\n📋 生成日报...")
        dr = get_docs_by_date(days=0)
        if not dr.get("ok"):
            msg = f"❌ 搜索失败：{dr.get('error')}"
            print(msg)
            LOGGER.error(msg)
            sys.exit(3)

        docs = dr.get("docs", [])
        log(f"    找到 {len(docs)} 篇当天文档")

        if not docs:
            msg = "⚠️ 当天没有会议记录（任务正常完成）"
            print(msg)
            LOGGER.info(msg)
            if args.send and not args.dry_run:
                ok_send, err = send_to_chat(msg)
                if not ok_send:
                    LOGGER.error(err)
                    sys.exit(5)
            return

        all_content, warnings, stats = build_combined_content(docs)
        LOGGER.info("daily stats=%s", stats)

        if not all_content.strip():
            msg = "❌ 已找到会议文档，但全部读取为空/失败"
            print(msg)
            LOGGER.error(msg)
            sys.exit(3)

        log("\n[2] AI 分析中...")
        try:
            result = analyze_with_deepseek(all_content, DAILY_PROMPT)
        except Exception as e:
            LOGGER.exception("DeepSeek analyze failed")
            print(f"❌ AI 分析失败：{e}")
            sys.exit(4)

        if warnings:
            result = "【系统提示】" + "；".join(warnings) + "\n\n" + result

        log("\n[3] 输出结果")
        print(f"\n{'='*60}\n{result}\n{'='*60}")

        if args.send:
            if args.dry_run:
                LOGGER.info("dry-run: skip sending")
            else:
                ok_send, err = send_to_chat(result)
                if not ok_send:
                    LOGGER.error(err)
                    sys.exit(5)
        return

    # 周报（上周）
    if args.week:
        log("\n📊 生成周报...")
        today = datetime.now()

        # 上周范围：上周一到周日
        days_since_monday = today.weekday()
        last_monday = today - timedelta(days=days_since_monday + 7)
        last_sunday = last_monday + timedelta(days=6)

        dr = get_docs_by_date(days=days_since_monday + 7)
        if not dr.get("ok"):
            msg = f"❌ 搜索失败：{dr.get('error')}"
            print(msg)
            LOGGER.error(msg)
            sys.exit(3)

        docs = dr.get("docs", [])
        docs = [
            d
            for d in docs
            if last_monday.date() <= datetime.fromtimestamp(d["create_time"]).date() <= last_sunday.date()
        ]

        log(f"    上周范围：{last_monday.strftime('%m/%d')} - {last_sunday.strftime('%m/%d')}")
        log(f"    找到 {len(docs)} 篇上周文档")

        if not docs:
            msg = "⚠️ 上周没有会议记录（任务正常完成）"
            print(msg)
            LOGGER.info(msg)
            if args.send and not args.dry_run:
                ok_send, err = send_to_chat(msg)
                if not ok_send:
                    LOGGER.error(err)
                    sys.exit(5)
            return

        all_content, warnings, stats = build_combined_content(docs)
        LOGGER.info("weekly stats=%s", stats)

        if not all_content.strip():
            msg = "❌ 已找到会议文档，但全部读取为空/失败"
            print(msg)
            LOGGER.error(msg)
            sys.exit(3)

        log("\n[2] AI 分析中...")
        try:
            result = analyze_with_deepseek(all_content, WEEKLY_PROMPT)
        except Exception as e:
            LOGGER.exception("DeepSeek analyze failed")
            print(f"❌ AI 分析失败：{e}")
            sys.exit(4)

        if warnings:
            result = "【系统提示】" + "；".join(warnings) + "\n\n" + result

        log("\n[3] 输出结果")
        print(f"\n{'='*60}\n{result}\n{'='*60}")

        if args.send:
            if args.dry_run:
                LOGGER.info("dry-run: skip sending")
            else:
                ok_send, err = send_to_chat(result)
                if not ok_send:
                    LOGGER.error(err)
                    sys.exit(5)
        return

    # 无参数，显示帮助
    parser.print_help()


if __name__ == "__main__":
    main()