# feishu-meeting-monitor

飞书会议纪要监控系统。自动搜索会议纪要文档，调用 AI 分析，生成结构化报告。

## 功能

- 自动搜索「文字记录：」开头的会议纪要文档
- 读取文档内容
- 调用 AI（DeepSeek）分析会议要点
- 生成结构化报告（主题、决策、风险、待办、负责人）
- 支持 refresh_token 自动刷新

## 使用方法

### 1. 配置

在项目根目录创建 `.env` 文件：

```bash
# 飞书应用凭证
FEISHU_APP_ID=cli_xxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxx

# 用户 OAuth（首次需要手动获取，后续可自动刷新）
# 参考下方"获取 Token"步骤
FEISHU_USER_ACCESS_TOKEN=
FEISHU_REFRESH_TOKEN=

# DeepSeek API
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
```

### 2. 获取 Token（首次）

1. 打开浏览器访问：
```
https://open.feishu.cn/open-apis/authen/v1/authorize?app_id=你的APP_ID&redirect_uri=https://open.feishu.cn/&scope=offline_access
```

2. 授权后，浏览器会跳转到类似：
```
https://open.feishu.cn/?code=xxxxx&state=xxx
```

3. 用 code 换取 token：
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

4. 把返回的 `access_token` 和 `refresh_token` 填入 `.env`

### 3. 运行

```bash
python main.py --search    # 搜索并筛选文档
python main.py --analyze  # 分析文档并生成报告
python main.py --all      # 完整流程：搜索+分析+报告
```

### 4. 定时任务（可选）

配合 cron 实现每日自动运行。

## 配置项

| 变量 | 必填 | 说明 |
|-----|-----|------|
| FEISHU_APP_ID | ✅ | 飞书应用 App ID |
| FEISHU_APP_SECRET | ✅ | 飞书应用 App Secret |
| FEISHU_USER_ACCESS_TOKEN | ✅ | 用户 access_token |
| FEISHU_REFRESH_TOKEN | ✅ | 用于自动刷新 |
| DEEPSEEK_API_KEY | ✅ | DeepSeek API Key |

## 输出示例

```json
{
  "主题": "一站式Agent平台线上周会",
  "关键决策": [
    "工具调用决策：大模型自主决定",
    "环境隔离决策：区分测试和生产环境"
  ],
  "风险问题": [
    "工具膨胀风险",
    "环境连接问题"
  ],
  "待办事项": [
    {"任务": "知识库产品设计收尾", "负责人": "张雅欣"},
    {"任务": "沙箱产品层设计", "负责人": "尹思源"}
  ],
  "涉及项目": ["知识库", "沙箱", "MCP", "SDK"]
}
```

## 文件结构

```
feishu-meeting-monitor/
├── SKILL.md           # 本文件
├── main.py            # 主程序
├── config.py          # 配置加载
├── .env.example       # 配置示例
├── requirements.txt   # 依赖
└── README.md         # 详细说明
```