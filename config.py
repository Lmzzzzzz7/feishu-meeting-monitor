#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

"""飞书会议监控 V2 配置 - 使用 lark-cli"""

import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent
load_dotenv(PROJECT_ROOT / ".env")


class Config:
    APP_ID = os.getenv("FEISHU_APP_ID", "")
    APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID", "")
    SEARCH_PREFIX = os.getenv("SEARCH_PREFIX", "文字记录：")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # 注意：不要在类定义阶段直接 float(...)，避免环境变量不合法导致导入即崩溃
    DEEPSEEK_TEMP_RAW = os.getenv("DEEPSEEK_TEMP", "0.3")

    FEISHU_API_BASE = "https://open.feishu.cn/open-apis"

    @classmethod
    def deepseek_temp(cls) -> float:
        try:
            return float(cls.DEEPSEEK_TEMP_RAW)
        except Exception:
            return 0.3

    @classmethod
    def validate(cls, require_chat_id: bool = False):
        """验证关键配置。

        Returns:
            (ok: bool, errors: list[str])
        """
        errors: list[str] = []

        if not cls.APP_ID:
            errors.append("缺少 FEISHU_APP_ID")
        if not cls.APP_SECRET:
            errors.append("缺少 FEISHU_APP_SECRET")
        if not cls.DEEPSEEK_API_KEY:
            errors.append("缺少 DEEPSEEK_API_KEY")
        if require_chat_id and not cls.TARGET_CHAT_ID:
            errors.append("缺少 TARGET_CHAT_ID（使用 --send 时必填）")

        # 校验温度参数合法性
        try:
            float(cls.DEEPSEEK_TEMP_RAW)
        except Exception:
            errors.append(f"DEEPSEEK_TEMP 非法: {cls.DEEPSEEK_TEMP_RAW!r}")

        return (len(errors) == 0, errors)


def get_config():
    return Config


if __name__ == "__main__":
    config = get_config()
    ok, errors = config.validate()
    if ok:
        print(f"✅ 配置验证通过 (APP_ID: {config.APP_ID[:10]}...)")
    else:
        print("❌ 配置验证失败")
        for e in errors:
            print(f" - {e}")
