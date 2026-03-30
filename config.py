#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
    DEEPSEEK_TEMP = float(os.getenv("DEEPSEEK_TEMP", "0.3"))
    FEISHU_API_BASE = "https://open.feishu.cn/open-apis"

    @classmethod
    def validate(cls):
        if not cls.APP_ID:
            print("⚠️ 缺少 FEISHU_APP_ID")
            return False
        if not cls.APP_SECRET:
            print("⚠️ 缺少 FEISHU_APP_SECRET")
            return False
        if not cls.DEEPSEEK_API_KEY:
            print("⚠️ 缺少 DEEPSEEK_API_KEY")
            return False
        return True


def get_config():
    return Config


if __name__ == "__main__":
    config = get_config()
    if config.validate():
        print(f"✅ 配置验证通过 (APP_ID: {config.APP_ID[:10]}...)")
    else:
        print("❌ 配置验证失败")
