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

## 中英对照事件卡

```bash
py -3.13 event_briefs.py            # 只处理双来源事件，逐事件调用 DeepSeek 生成事件卡
py -3.13 render_events.py           # 重新渲染 events.html（自动读取 event_briefs.json）
```

只处理 `events.json` 中 `source_count >= 2` 的事件（不重新抓取、不改动归组结果），
为每个事件生成一张中英对照卡片，写入 `output/event_briefs.json`，并展示到 `events.html`
（原始材料折叠保留）。每张卡含中英标题与四部分：

1. **事件概述**：1–2 句，保留归因与不确定性（“据…称”“涉嫌”等）。
2. **共同报道**：两份输入以实质相同意思都明确出现的最小事实（逐项求交集）。该标签只能是“共同报道”，不等于“已证实事实”，也不等于独立核实。
3. **各家补充**：分别列出各来源单独提供、或措辞/归因不同而无法合并的信息，保留原始措辞与归因。
4. **材料局限**：只保留影响理解的重要缺口（最多 2 条，没有实质局限不凑数），以及某篇标题与其摘要是否存在出入。

每条（概述除外）均带英文、中文与对应 `article_id`（点击可跳转到来源）。规则：

- 仅依据标题与 `rss_description`，不补充模型记忆中的背景。
- “未提及”不等于否认；报道时间不同不等于立场不同；RSS 长短不同不能直接解释成媒体偏见。
- 区分“本工具未读取全文”与“媒体未报道”：只拿到 RSS 时写“本工具未读取全文”，不臆断某媒体没有进一步细节。
- `event_briefs.py --only e3` 只重新生成指定事件（逗号分隔多个），其余卡片保持不变。
- 所有引用 id 由程序校验：引用不存在或其它事件的文章即判定该事件失败；共同报道若只落到单一来源会自动降级进“各家补充”。
- 失败时该事件保留原始材料展示并明确标记失败。

## 每日选读

一键运行（推荐）：

```bash
# 完整流程：采集 → 归组 → 筛选 → 生成/复用事件卡 → HTML
# （BBC/Guardian 需走本地代理，DeepSeek 直连不走代理）
HTTPS_PROXY=http://127.0.0.1:7890 HTTP_PROXY=http://127.0.0.1:7890 \
  NO_PROXY=api.deepseek.com python3 run_daily.py

# 只采集与归组、不调用模型（验证抓取）
python3 run_daily.py --dry-run

# 用既有 events.json、不重新抓取（输出明确标记「历史数据」）
python3 run_daily.py --offline [--events output/events.json]
```

`run_daily.py` 按北京时间建立独立输出目录 `output/<YYYY-MM-DD_HHMM>/`，保存
`events.json`（原始输入）、`daily_brief.json`、`daily_brief.html` 与 `manifest.json`
（数据模式、各步状态、API 用量、耗时），避免次日覆盖后无法核查。默认重新抓取最近
24 小时；任何步骤失败都会明确报告，不会拿旧输出冒充本次成功。

从 `events.json` 的**全部事件**（含单来源）中选出 5–8 件。这是「当前来源范围内的选读」，
不是全球热点排行榜。

筛选依据：公共影响、新进展、阅读价值、适度覆盖不同地区与主题。媒体数量不等于重要性，
单来源事件也可入选；不按耸动程度排序、不硬凑数量；不足 5 件就按实际数量并说明。
每件给出一句具体入选理由及支持它的 `article_id`。入选理由只依据原始材料，保留归因与
不确定性（「据…称」「涉嫌」等），不添加材料不支持的前瞻推断（如冲突升级、监管影响）。

生成：只为入选事件生成**中英标题**与卡片（含单来源事件；标题保留「涉嫌」「据某方称」等
限定）。双来源事件沿用四段式结构（概述 / 共同报道 / 各家补充 / 材料局限），仅在「原始材料
+ 提示词版本」均未变化、且该事件仍在本次采集窗口内时，按 `material_hash` 复用此前运行
的缓存卡片（跨运行时按材料指纹匹配，而非不稳定的 event_id）；单来源事件明确标记「单一
来源」，生成标题 / 概述 / 要点 / 材料局限，不生成「共同报道」、不虚构媒体对照。

页面显示生成时间、数据采集时间、采集窗口、来源范围、候选/入选数、来源获取失败情况、
入选理由与事件卡、原始材料及原文链接；使用旧文件时页面明确标「历史数据」，不冒充今日
简报。程序校验事件与引用 ID 存在、无重复入选、引用属于对应事件，并保存入选与未入选
事件 ID 供核对。

也可独立运行 `daily_brief.py`（只读 events.json、不重新抓取，默认标记历史数据、不复用缓存）。

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
