# feishu-meeting-monitor

飞书会议监控系统 V2。基于 `lark-cli` 实现。

## 功能

- 自动搜索「文字记录：」开头的会议录音文档
- 读取文档内容
- 调用 DeepSeek AI 分析会议要点
- 生成结构化日报/周报
- 支持日报发送到飞书群

## 前提条件

1. **lark-cli 安装**：`npm install -g @larksuite/cli`
2. **飞书应用权限**（需管理员审批）：
   - `search:docs:read` — 搜索文档（用户身份）
   - `docx:document:readonly` — 读取文档（用户身份）
   - `offline_access` — 持续访问 token
   - `im:message:send_as_bot` — 发消息（Bot身份，已有）
3. **lark-cli 登录**：`lark-cli auth login --scope "search:docs:read docx:document:readonly offline_access"`
4. **DeepSeek API Key**

## 使用方法

```bash
# 配置
cp .env.example .env
# 编辑 .env 填入实际值

# 日报（当天）
python main.py --today

# 周报（上周）
python main.py --week

# 分析指定文档
python main.py --analyze <token>

# 生成并发送日报
python main.py --today --send
```

## 定时任务

```bash
# 每日早9点运行
0 9 * * 1-5 cd /path/to/feishu-meeting-monitor && python main.py --today --quiet
```

## 配置项

| 变量 | 说明 |
|-----|------|
| FEISHU_APP_ID | 飞书应用 App ID |
| FEISHU_APP_SECRET | 飞书应用 App Secret |
| DEEPSEEK_API_KEY | DeepSeek API Key |
| TARGET_CHAT_ID | 发消息的目标群 ID |
| SEARCH_PREFIX | 文档标题前缀（默认：文字记录：） |

## 输出格式

```
## 会议概览
## 关键决策
## 待办事项
## 讨论要点
## 风险与疑虑
```
