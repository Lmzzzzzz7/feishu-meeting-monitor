# feishu-meeting-monitor

飞书会议监控系统。基于 `lark-cli` 实现，自动搜索「文字记录：」开头的会议录音文档，调用 AI（DeepSeek）分析生成结构化日报或周报。

## 功能

- 自动搜索「文字记录：」开头的会议录音文档
- 读取文档内容
- 调用 DeepSeek AI 分析会议要点
- 生成结构化日报（会议概览、决策、待办、风险）
- 支持周报（合并上周所有会议）
- 支持日报发送到飞书群

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
npm install -g @larksuite/cli
```

### 2. 配置 lark-cli 认证

飞书应用需要以下权限（需管理员审批）：
- `search:docs:read` — 搜索文档
- `docx:document:readonly` — 读取文档内容
- `offline_access` — 持续访问 token
- `im:message:send_as_bot` — 发送消息（Bot 身份）

```bash
lark-cli auth login --scope "search:docs:read docx:document:readonly offline_access"
```

### 3. 配置

复制 `.env.example` 为 `.env`，填入实际值。

### 4. 运行

```bash
# 生成当天日报
python main.py --today

# 生成周报
python main.py --week

# 分析指定文档
python main.py --analyze <doc-token>

# 生成并发送日报到群
python main.py --today --send --chat-id oc_xxx

# 定时运行（每日早9点）
0 9 * * 1-5 cd /path/to/feishu-meeting-monitor && python main.py --today --quiet
```

## AI 分析输出格式

```
## 会议概览
- 会议主题：...
- 会议时间：...
- 参与人：...

## 关键决策
- ...

## 待办事项
- [任务] （负责人）

## 讨论要点
- ...

## 风险与疑虑
- ...
```

周报在此基础上增加"本周会议概览""下周关注点"等模块。
