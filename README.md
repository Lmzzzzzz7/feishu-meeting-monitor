# feishu-meeting-monitor

飞书会议周报生成器 - 管理层决策版

## 项目概述

基于飞书「文字记录：」会议录音文档，自动搜索、读取、分析，调用 DeepSeek AI 生成结构化周报。

**核心特点**：
- 自动识别上周会议（周一到周日）
- 多会议整合，追踪决策脉络
- 四步法重构（硬信息提取→价值量化→风险三要素→行动SMART化）
- 输出结构适配管理层决策需求

---

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    feishu-meeting-monitor                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌────────────┐ │
│  │  lark-cli   │ -> │  fetch_doc  │ -> │ DeepSeek   │ │
│  │  (搜索文档)  │    │  (读取内容)  │    │  (AI分析)   │ │
│  └─────────────┘    └─────────────┘    └────────────┘ │
│        ↓                                        ↓       │
│  ┌────────────────────────────────────────────────────┐ │
│  │              输出结构（多会议整合版）                │ │
│  │  - 执行摘要    - 跨会议决策脉络                      │ │
│  │  - 项目进展    - 风险预警                            │ │
│  │  - 管理层决策需求                                     │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 功能特性

| 功能 | 说明 |
|------|------|
| 自动搜索 | 搜索「文字记录：」开头的会议文档 |
| 日期过滤 | 自动识别上周（周一到周日）范围 |
| 多会议整合 | 识别跨会议关联，追踪决策演变 |
| 四步法重构 | 硬信息提取 → 价值量化 → 风险三要素 → 行动SMART |
| 定时运行 | 支持cron定时生成日报/周报 |
| 群发送 | 支持发送到飞书群 |

---

## 安装配置

### 1. 安装依赖

```bash
# 克隆项目
git clone https://github.com/Lmzzzzzz7/feishu-meeting-monitor.git
cd feishu-meeting-monitor

# Python依赖
pip install -r requirements.txt

# lark-cli
npm install -g @larksuite/cli
```

### 2. 飞书应用权限

在飞书开放平台创建应用，需要以下权限：

| 权限 | 用途 |
|------|------|
| `search:docs:read` | 搜索文档 |
| `docx:document:readonly` | 读取文档内容 |
| `offline_access` | 持续访问 token |
| `im:message:send_as_bot` | 发送消息（Bot身份） |

### 3. lark-cli 认证

```bash
lark-cli auth login --scope "search:docs:read docx:document:readonly offline_access"
```

### 4. 环境配置

```bash
# 复制配置示例
cp .env.example .env

# 编辑 .env 填入实际值
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
DEEPSEEK_API_KEY=sk-xxx
TARGET_CHAT_ID=  # 使用 --send 时必填（老板群 chat_id）
SEARCH_PREFIX=文字记录：
```

---

## 使用方法

### 命令行

```bash
# 上线前自检（推荐先跑一次）
python main.py --health-check

# 生成上周周报（老板每周收）
python main.py --week

# 生成并发送上周周报到老板群
python main.py --week --send

# 上线前演练：跑完整流程但不发群
python main.py --week --dry-run

# 分析指定文档
python main.py --analyze <doc-token>

# 静默模式（减少输出）
python main.py --week --quiet
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `--today` | 生成当天日报（可不用） |
| `--week` | 生成上周周报（老板每周收） |
| `--analyze <token>` | 分析指定文档 |
| `--send` | 生成后发送到飞书群（需配置 `TARGET_CHAT_ID`） |
| `--quiet` | 静默模式 |
| `--dry-run` | 运行但不发送消息（上线前验证） |
| `--health-check` | 检查配置/权限/依赖是否可用 |

---

## AI 提示词说明

### 周报提示词结构（老板决策版：资源与优先级）

```
# 四步法重构
1. 跨会议信息关联 - 识别同一议题在多个会议中的讨论脉络
2. 硬信息提取 - 将模糊表述转化为具体量化
3. 价值量化翻译 - 技术语言 → 业务价值
4. 风险三要素计算 - 概率、影响、预案

# 输出结构
- 执行摘要：核心变化追踪
- 跨会议决策脉络：议题→会议→演进
- 重点项目进展：状态、进度、阻塞、下周目标
- 风险预警：首次提及时间线、当前状态
- 管理层决策需求：立即决策/需要知晓/需要支持
```

### 提示词自定义

修改 `main.py` 中的 `WEEKLY_PROMPT` 变量即可调整输出格式。

---

## 输出示例

### 执行摘要
```
## 📌 执行摘要
**核心变化追踪：**
- 议题1：从"初步讨论"→"立项决策"（3次会议推进）
- 议题2：从"方案设计"→"资源Blocked"（需管理层介入）
**整合要点**：多场会议聚焦的共同挑战或趋势
```

### 决策清单
```
## 🎯 决策清单
**已确定：**
- ✅ 明确结论1
- ✅ 明确结论2

**待决策：**
- ❓ 待确认事项1（影响范围）
- ❓ 待确认事项2（资源需求）
```

### 项目进展
```
## 🚀 重点项目进展
**项目名称 - 状态标识**
- 本周会议覆盖：X场（日期1、日期2）
- 进度：X%（综合多场会议进展）
- 本周演进：会议1明确A，会议2确定B，会议3发现C问题
- 当前阻塞：具体问题（提及该问题的会议及时间）
- 下周目标：基于最后一次会议讨论
```

---

## 定时任务

### 每日早9点运行日报

```bash
# crontab -e
0 9 * * 1-5 cd /path/to/feishu-meeting-monitor && python main.py --today --quiet
```

### 每周一早上生成周报

```bash
# crontab -e
# 建议先执行一次健康检查
# python main.py --health-check

0 8 * * 1 cd /path/to/feishu-meeting-monitor && python main.py --week --send --quiet
```

---

## 故障排除

### lark-cli 未找到

```bash
# 检查安装
which lark-cli

# 重新安装
npm install -g @larksuite/cli
```

### 认证过期

```bash
# 重新认证
lark-cli auth login --scope "search:docs:read docx:document:readonly offline_access"
```

### 没有找到会议文档

1. 确认文档标题以「文字记录：」开头
2. 检查 `SEARCH_PREFIX` 配置
3. 确认日期范围正确

### 日志与排错

- 日志文件：`logs/feishu-meeting-monitor.log`（自动轮转，保留 7 份）
- 常见退出码：
  - `0`：成功（包括“上周无会议”）
  - `2`：配置/健康检查失败
  - `3`：飞书搜索/拉取失败
  - `4`：DeepSeek 分析失败
  - `5`：发送失败

### API 错误

- 检查 `DEEPSEEK_API_KEY` 是否正确
- 确认 API 余额充足
- 查看 DeepSeek 官方状态

---

## 文件结构

```
feishu-meeting-monitor/
├── main.py           # 主程序入口
├── README.md         # 本文档
├── SKILL.md          # OpenClaw skill定义
├── config.py         # 配置文件
├── requirements.txt # Python依赖
├── .env.example      # 环境变量示例
└── .env              # 环境变量（实际配置）
```

---

## 技术栈

- **Python 3.8+**
- **lark-cli** - 飞书CLI工具
- **DeepSeek API** - AI分析
- **requests** - HTTP请求

---

## 注意事项

1. **会议文档命名**：必须以「文字记录：」开头才能被搜索到
2. **日期范围**：周报自动识别上周（当前日期往前推一个完整周）
3. **Token限制**：单次请求内容限制12000字符
4. **发送权限**：需要 Bot 身份和群 ID 才能发送消息

---

## 更新日志

### 2026-04-01
- 升级为多会议整合版提示词
- 修正周报时间范围计算（正确识别上周周一到周日）
- 添加决策脉络追踪功能

### 2026-03-26
- 初始版本
- 支持日报和周报生成

---

## License

MIT