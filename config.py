#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书会议监控系统 - 配置加载
从环境变量或 .env 文件加载配置
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# 加载 .env 文件
load_dotenv(PROJECT_ROOT / ".env")


class Config:
    """飞书会议监控配置"""

    # 飞书应用凭证
    APP_ID = os.getenv("FEISHU_APP_ID", "")
    APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")

    # 用户 Token
    USER_ACCESS_TOKEN = os.getenv("FEISHU_USER_ACCESS_TOKEN", "")
    REFRESH_TOKEN = os.getenv("FEISHU_REFRESH_TOKEN", "")

    # DeepSeek API
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

    # 搜索配置
    SEARCH_QUERY = os.getenv("SEARCH_QUERY", "a")  # 搜索关键词
    SEARCH_PREFIX = os.getenv("SEARCH_PREFIX", "文字记录：")  # 标题筛选前缀

    # API 地址
    FEISHU_API_BASE = "https://open.feishu.cn/open-apis"
    DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"

    @classmethod
    def validate(cls):
        """验证配置是否完整"""
        required = [
            ("FEISHU_APP_ID", cls.APP_ID),
            ("FEISHU_APP_SECRET", cls.APP_SECRET),
            ("DEEPSEEK_API_KEY", cls.DEEPSEEK_API_KEY),
        ]

        missing = [name for name, value in required if not value]
        if missing:
            print(f"⚠️ 缺少配置: {', '.join(missing)}")
            print("请在 .env 文件中配置，或设置环境变量")
            return False

        # 检查用户 token（至少有一个）
        if not cls.USER_ACCESS_TOKEN and not cls.REFRESH_TOKEN:
            print("⚠️ 需要配置 FEISHU_USER_ACCESS_TOKEN 或 FEISHU_REFRESH_TOKEN")
            print("参考 SKILL.md 中的「获取 Token」步骤")
            return False

        return True

    @classmethod
    def save_token(cls, access_token: str, refresh_token: str = None):
        """保存 token 到 .env 文件"""
        env_file = PROJECT_ROOT / ".env"

        # 读取现有配置
        lines = []
        if env_file.exists():
            with open(env_file, "r") as f:
                lines = f.readlines()

        # 更新或添加 token
        new_lines = []
        found_access = False
        found_refresh = False

        for line in lines:
            if line.startswith("FEISHU_USER_ACCESS_TOKEN="):
                new_lines.append(f'FEISHU_USER_ACCESS_TOKEN="{access_token}"\n')
                found_access = True
            elif line.startswith("FEISHU_REFRESH_TOKEN="):
                if refresh_token:
                    new_lines.append(f'FEISHU_REFRESH_TOKEN="{refresh_token}"\n')
                else:
                    new_lines.append(line)
                found_refresh = True
            else:
                new_lines.append(line)

        # 如果没有找到，追加
        if not found_access:
            new_lines.append(f'FEISHU_USER_ACCESS_TOKEN="{access_token}"\n')
        if not found_refresh and refresh_token:
            new_lines.append(f'FEISHU_REFRESH_TOKEN="{refresh_token}"\n')

        # 写入文件
        with open(env_file, "w") as f:
            f.writelines(new_lines)

        print(f"✅ Token 已保存到 {env_file}")


def get_config():
    """获取配置实例"""
    return Config


if __name__ == "__main__":
    config = get_config()
    if config.validate():
        print("✅ 配置验证通过")
        print(f"  APP_ID: {config.APP_ID[:10]}...")
        print(f"  ACCESS_TOKEN: {'已配置' if config.USER_ACCESS_TOKEN else '未配置'}")
        print(f"  REFRESH_TOKEN: {'已配置' if config.REFRESH_TOKEN else '未配置'}")
    else:
        print("❌ 配置验证失败")