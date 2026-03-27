# 飞书会议监控系统

自动搜索飞书中的会议纪要文档，调用 AI 分析，生成结构化报告。

## 功能特性

- 🔍 **自动搜索** - 搜索「文字记录：」开头的会议纪要文档
- 📖 **智能读取** - 自动读取文档正文内容
- 🤖 **AI 分析** - 使用 DeepSeek 分析会议要点
- 📊 **结构化输出** - 提取主题、决策、风险、待办、负责人
- 🔄 **自动续期** - 支持 refresh_token 自动刷新

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/Lmzzzzzz7/feishu-meeting-monitor.git
cd feishu-meeting-monitor
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入实际配置
```

### 4. 首次授权

需要获取用户 access_token 和 refresh_token：

1. 打开浏览器访问：
```
https://open.feishu.cn/open-apis/authen/v1/authorize?app_id=你的APP_ID&redirect_uri=https://open.feishu.cn/&scope=offline_access
```

2. 授权后记录 URL 中的 `code`

3. 换取 token：
```bash
curl -X POST "https://open.feishu.cn/open-apis/authen/v1/access_token" \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "authorization_code",
    "client_id": "你的APP_ID",
    "client_secret": "你的APP_SECRET",
    "code": "刚才拿到的code"
  }'
```

4. 将返回的 `access_token` 和 `refresh_token` 填入 `.env`

### 5. 运行

```bash
# 仅搜索和筛选
python main.py --search

# 仅分析
python main.py --analyze

# 完整流程
python main.py --all
```

## 配置说明

| 变量 | 必填 | 说明 |
|-----|-----|------|
| `FEISHU_APP_ID` | ✅ | 飞书应用 App ID |
| `FEISHU_APP_SECRET` | ✅ | 飞书应用 App Secret |
| `FEISHU_USER_ACCESS_TOKEN` | ✅ | 用户 access_token |
| `FEISHU_REFRESH_TOKEN` | ✅ | 用于自动刷新 |
| `DEEPSEEK_API_KEY` | ✅ | DeepSeek API Key |
| `SEARCH_PREFIX` | 可选 | 筛选标题前缀，默认「文字记录：」 |

## 输出示例

运行后输出类似：

```json
{
  "主题": "一站式Agent平台线上周会",
  "关键决策": [
    "工具调用决策：大模型自主决定，不额外控制调用顺序",
    "环境隔离决策：底层存储拆开，区分测试和生产环境"
  ],
  "风险问题": [
    "工具膨胀风险：MCP工具过多时可能调用混乱",
    "环境连接问题：生产环境无法连接测试沙箱"
  ],
  "待办事项": [
    {"任务": "知识库产品设计收尾", "负责人": "张雅欣"},
    {"任务": "沙箱产品层设计", "负责人": "尹思源"}
  ],
  "涉及项目": ["知识库", "沙箱", "MCP", "SDK"]
}
```

## 定时任务（可选）

配合 GitHub Actions 或 cron 实现每日自动运行。

## 目录结构

```
feishu-meeting-monitor/
├── main.py           # 主程序
├── config.py        # 配置加载
├── .env.example     # 配置模板
├── .gitignore       # Git 忽略规则
├── requirements.txt # 依赖
└── README.md        # 本文件
```

## License

MIT