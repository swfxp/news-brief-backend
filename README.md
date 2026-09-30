# 每日中英双语新闻简报

从 BBC News 和 The Guardian 两个无需登录的英文新闻 RSS 抓取最近 24 小时的新闻，
调用 DeepSeek API 为每条新闻生成英文摘要和对应中文翻译，输出为 UTF-8 JSON。

## 安装依赖

本机 Python 通过 `py` 启动器调用（Python 3.13）。在项目目录下执行：

```bash
py -3.13 -m venv .venv
# Windows (Git Bash)
source .venv/Scripts/activate
py -3.13 -m pip install -r requirements.txt
```

> 若你直接使用系统 Python（`python` 命令可用），把上面的 `py -3.13` 换成 `python` 即可。

## 填写配置

1. 复制模板：`cp .env.example .env`（Windows 下可手动复制改名）。
2. 在 `.env` 中填入你的 DeepSeek API Key：

   ```
   DEEPSEEK_API_KEY=sk-xxxx
   ```

   也可以不建 `.env`，直接用环境变量 `DEEPSEEK_API_KEY` 提供密钥。
   `.env` 已加入 `.gitignore`，不会被提交。

## 运行

```bash
# 完整运行（抓取 + 调用模型生成摘要）
py -3.13 main.py

# 只抓取新闻、不调用模型（用于验证抓取与去重逻辑）
py -3.13 main.py --dry-run
```

输出文件为 `output/brief.json`（UTF-8，中文原样显示）。

可选参数：

| 参数 | 说明 |
| --- | --- |
| `--dry-run` | 只抓取新闻、保存原始字段，不调用 DeepSeek |
| `--feeds <list>` | 覆盖新闻源，格式 `名称=URL,名称2=URL2`（逗号分隔） |
| `--output <path>` | 覆盖输出文件路径（默认 `output/brief.json`） |

## 生成本地阅读页面

```bash
py -3.13 render_brief.py
```

读取 `output/brief.json`，生成 `output/brief.html`（纯 Python 标准库，不联网、不调用 AI）。
页面含“全部 / BBC / The Guardian”来源筛选，双击 `output/brief.html` 即可查看，无需启动服务器。

## 同一事件归组

```bash
py -3.13 group_events.py            # 抓取候选 + DeepSeek 归组
py -3.13 group_events.py --dry-run  # 只抓取候选，不调用模型
py -3.13 render_events.py           # 生成 events.html
```

流程：单独获取 BBC + The Guardian 最近 24 小时、每家最多 `MAX_CANDIDATES`（默认 30）条候选，
生成稳定 `article_id`，用一次 DeepSeek 调用仅依据标题与 RSS 摘要把「同一具体事件」归组
（同国家/人物/话题不算同一事件），并生成事件中文标题；程序校验返回的 id 必须存在、
同一文章不得进多个组，未分组文章自动补为单独组。校验失败时明确报告并退回逐条展示。

输出 `output/events.json` 与 `output/events.html`：

- 每个事件含 `event_id`、`title_zh`、`article_ids`、`source_count`（按不同媒体数，不按文章数）、
  `grouping_reason`。
- 事件卡片并列展示各篇原标题、原始 RSS 摘要、来源、发布时间、原文链接；
  含两个来源的事件优先展示（标注“便于核对，非重要性排名”）。
- 页面注明“自动归组，尚未独立核实”。
- 本阶段不做“立场”“事实已确认”等判断，不添加输入之外的背景；保留全部候选便于核对。

## 选取规则

- **每个来源独立**取「发布时间」落在最近 `NEWS_WINDOW_HOURS`（默认 24）小时窗口内的条目。
- 每个来源按发布时间**从新到旧**排序、按链接去重后，取前 `MAX_ARTICLES`（默认 5）条。
- 各来源结果合并后按发布时间倒序排列；**不做跨来源去重、聚类、立场标签或评分**，
  同一事件两家媒体的报道会**分别展示**，便于人工比较。
- 因此输出的是「各来源**最新的 N 条**」，**不是**热度/权重排名。

## 输出结构

```json
{
  "generated_at": "2026-09-30T12:34:56+00:00",
  "window_start": "2026-09-29T12:34:56+00:00",
  "window_end": "2026-09-30T12:34:56+00:00",
  "sources": [
    {
      "name": "BBC News",
      "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
      "status": "ok",
      "fetched": 27,
      "in_window": 25,
      "selected": 5,
      "error": null
    },
    {
      "name": "The Guardian",
      "url": "https://www.theguardian.com/world/rss",
      "status": "ok",
      "fetched": 45,
      "in_window": 40,
      "selected": 5,
      "error": null
    }
  ],
  "articles": [
    {
      "title": "新闻标题",
      "source": "BBC News",
      "url": "https://...",
      "published_at": "2026-09-30T10:00:00+00:00",
      "content_scope": "title_and_rss_summary",
      "rss_description": "RSS 原始摘要（已去除 HTML 标签）...",
      "summary_en": "English summary...",
      "summary_zh": "中文翻译..."
    }
  ]
}
```

`sources` 逐项记录各来源的 `status`（`ok`/`error`）与 `fetched`/`in_window`/`selected`
数量；`error` 为失败原因（成功时为 `null`）。单个来源失败不影响其它来源。

`content_scope` 取值：

- `title_and_rss_summary`：依据「标题 + RSS 提供的摘要」生成，**未读取全文**。
- `title_only`：该条目只有标题，无 RSS 摘要，摘要仅基于标题。

`rss_description` 是**实际传给模型**的 RSS 摘要文本（已去除 HTML 标签），
用于逐条核对模型是否添加了输入之外的事实；只有标题时为 `""`。

## 准确性说明

- 摘要只依据 RSS 实际提供的标题/描述生成，提示词明确要求模型**不得补充**
  记忆中的额外事实、人名、日期、数字或背景；英文摘要中的每个事实都必须在输入文本中有依据。
- 保留原文的归因与不确定性（“据某方称”“至少”“可能”等），不添加带立场的措辞；
  无法确认译名的专有名词保留英文原文；严格区分“宣布/启动/开工/投产”等动词。
- 只有标题时，`summary_en` 等于标题原文，`summary_zh` 只翻译标题，不扩写摘要。
- 本工具只读取 RSS，不抓取文章全文；`content_scope` 明确标注内容范围，
  `rss_description` 保留实际传给模型的原文，便于核对。
- 保留每条新闻的原始标题、来源、原文链接、发布时间。
- 抓取失败或窗口内无新闻时，程序会如实报错/报告，不会生成假新闻。

## 失败处理

- 单个来源不可达 / 非 200 / 解析失败：在 stderr 打印警告，`sources` 中该来源记为
  `error` 并带原因，**继续处理其它来源**；页面顶部会显示“部分来源获取失败”。
- 所有来源都失败：`articles` 为空，页面显示“未获取到任何新闻”，不会生成假新闻。
- 缺少 `DEEPSEEK_API_KEY` 且非 dry-run：打印错误并退出。
- 单条摘要生成失败：该条 `summary_en`/`summary_zh` 置为 `null`，
  在 stderr 打印警告，不影响其余条目。
