# 多来源双语新闻简报工具

从 BBC News、The Guardian、TASS、Al Jazeera 四个公开 RSS 抓取最近一段时间的新闻，
调用 DeepSeek API 完成「同一事件归组 → 选读筛选 → 生成中英对照事件卡」，
输出可离线查看的 HTML 页面。

> **定位**：个人学习 / 实验性项目。用来练习「RSS 抓取、调用大模型、结果校验、
> 静态页面渲染」的完整链路，**不是**稳定的生产工具，也不保证输出准确可用。

---

## 已实现功能

- **抓取**：默认四个来源（BBC News、The Guardian、TASS、Al Jazeera，集中配置见
  [sources.py](sources.py)，可用环境变量或参数换成其它源），按发布时间过滤最近
  `NEWS_WINDOW_HOURS`（默认 24）小时内的条目，按链接去重；缺少可靠发布时间的条目不进入窗口。
- **逐条摘要**（`main.py`）：为每条新闻生成英文摘要与中文翻译（`brief.json`）。
- **同一事件归组**（`group_events.py`）：用一次模型调用把报道「同一具体事件」的文章归组，
  程序校验 id 合法、同一文章不进多组；归组失败时明确报告并退回逐条展示。
- **中英对照事件卡**（`event_briefs.py`）：对双来源事件生成四段式卡片
  （事件概述 / 共同报道 / 各家补充 / 材料局限）。
- **每日选读**（`daily_brief.py` + `run_daily.py`）：从全部事件（含单来源）中选出 5–8 件，
  生成中英标题与事件卡；单来源事件生成「概述 / 要点 / 材料局限」卡片。
- **数据时效**：记录实际采集时间与窗口；使用旧文件时页面明确标记「历史数据」；
  双来源卡片仅在「提示词版本 + 原始材料」均未变化且仍在本次窗口内时按材料指纹复用。
- **独立输出目录**：每次运行按北京时间建立 `output/<YYYY-MM-DD_HHMM>/`，
  保存原始输入、JSON 与 HTML，避免次日覆盖。
- **离线阅读页**：三个渲染脚本只用 Python 标准库，不联网、不调用 AI，双击 HTML 即可查看。
- **API 用量统计**：完整运行结束时汇总调用次数与 token 用量（仅当响应返回 usage 字段时）。

---

## 处理流程

```
RSS 抓取（四个来源，默认最近 24h，每家最多 30 条）
        │
        ▼
同一事件归组（一次模型调用，程序校验；输入过大时自动分批并跨批合并）
        │
        ▼
选读筛选（一次模型调用，选出 5–8 件，给入选理由）
        │
        ▼
为入选事件生成 / 复用中英事件卡（逐事件调用，双来源与单来源分别处理）
        │
        ▼
渲染 HTML（纯本地，不联网、不调用 AI）
```

一键入口 `run_daily.py` 按上述顺序执行：**采集 → 归组 → 筛选 → 生成/复用卡片 → HTML**。

---

## 来源

默认四个来源，集中在 [sources.py](sources.py) 管理（可在此启用/停用、调整每家候选上限）：

| 来源 | 地区 / 类型 | RSS |
| --- | --- | --- |
| BBC News | 英国公共广播 | `https://feeds.bbci.co.uk/news/world/rss.xml` |
| The Guardian | 英国报纸 | `https://www.theguardian.com/world/rss` |
| TASS | 俄罗斯国家通讯社（英文版） | `https://tass.com/rss/v2.xml` |
| Al Jazeera | 卡塔尔 / 中东 | `https://www.aljazeera.com/xml/rss/all.xml` |

- 均为免费公开 RSS，无需登录或密钥；内容版权归各媒体，仅用于个人阅读/学习，
  不得再分发，具体以各媒体官网使用条款为准。
- 每家采集最近 24 小时、默认最多 30 条候选（`MAX_CANDIDATES`，或 `sources.py` 中
  各来源的 `max_candidates`）。
- 可用 `RSS_FEEDS` 环境变量或 `--feeds` 参数整体覆盖默认列表。
- 通讯社稿件可能被多家媒体转载；仅当输入明确给出转载归属时才记录，不自行猜测，
  且多家转载不等于独立证实。

---

## 安装与配置

需要 Python 3（已在 3.12 上验证），依赖仅两个库：

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python3 -m pip install -r requirements.txt
```

复制 `.env.example` 为 `.env`，填入你的 DeepSeek API Key：

```
DEEPSEEK_API_KEY=sk-xxxx
```

也可以用环境变量 `DEEPSEEK_API_KEY` 提供，不建 `.env`。`.env` 已被 `.gitignore` 忽略，
不会进入版本库。

可选配置（均有默认值，一般无需修改）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名 |
| `RSS_FEEDS` | 空（用默认双源） | 覆盖新闻源，格式 `名称=URL,名称2=URL2` |
| `NEWS_WINDOW_HOURS` | `24` | 时间窗口（小时） |
| `MAX_CANDIDATES` | `30` | 归组时每个来源的候选上限 |

---

## 运行

**一键完整流程（推荐）**

```bash
# 这些境外 RSS（BBC、Guardian、TASS、Al Jazeera）在中国大陆通常需要代理才能访问；
# DeepSeek API 直连、不走代理。请按你的网络情况调整代理地址。
HTTPS_PROXY=http://127.0.0.1:7890 HTTP_PROXY=http://127.0.0.1:7890 \
  NO_PROXY=api.deepseek.com python3 run_daily.py
```

其它模式：

```bash
python3 run_daily.py --dry-run   # 只采集与归组，不调用模型（验证抓取）
python3 run_daily.py --offline   # 用既有 events.json，不重新抓取，标记「历史数据」
```

**独立步骤**（可按需单独运行）

```bash
python3 main.py              # 抓取 + 逐条中英摘要 -> output/brief.json
python3 group_events.py      # 抓取候选 + 归组 -> output/events.json
python3 event_briefs.py      # 双来源事件四段式卡片 -> output/event_briefs.json
python3 daily_brief.py       # 只读 events.json，筛选 + 卡片 -> output/daily_brief.json
```

## 查看页面

```bash
python3 render_brief.py        # brief.json        -> brief.html        双语速读
python3 render_events.py       # events.json       -> events.html       多源对照
python3 render_daily_brief.py  # daily_brief.json  -> daily_brief.html  每日选读
```

用浏览器打开生成的 HTML 即可（渲染脚本离线可用，不联网、不调用 AI）。
完整运行（`run_daily.py`）会自动在本次运行目录生成 `daily_brief.html`。

---

## 离线演示（虚构数据）

无需 API Key、不联网即可预览工具的输出样式：

```bash
python3 demo/make_demo.py
```

会在 `demo/` 下生成 `events.html`（多源对照）与 `daily_brief.html`（每日选读）。

> 该目录下的数据**全部为虚构**（人物、机构、地点、媒体名「示例媒体 A/B」、链接
> example.com 均为编造），页面上有醒目的「虚构演示数据 · 非真实新闻」横幅，仅用于
> 展示输出样式。演示覆盖双来源、单来源、以及「仅有标题、无 RSS 摘要」的材料不足情况。

---

## API 费用与网络访问

- 本项目调用 **DeepSeek API**，属于**按量付费**服务，需要你自行注册并获取 Key；
  运行会产生费用，且不承诺免费或长期可用，具体以官方定价为准。
- 一次完整运行大致调用：1 次归组 + 1 次筛选 + 每个入选事件 1 次卡片生成，
  调用次数与 token 用量会在运行结束时汇总打印（仅当响应返回 usage 字段时）。
- 默认新闻源 BBC News / The Guardian 位于境外，需要可访问其 RSS 的网络环境
  （中国大陆通常需要代理）；DeepSeek API 默认直连。
- 离线演示（`demo/make_demo.py`）与三个渲染脚本**不联网、不调用 API**。

---

## 已知局限

- **来源覆盖有限**：默认仅四个英文来源（英国两源 + 俄罗斯通讯社 + 中东媒体），
  选读结果是「当前来源范围内的选读」，不是全球热点排行榜；媒体数量不等于重要性。
- **通讯社转载不等于独立证实**：多家媒体可能转载同一通讯社稿件，本工具仅在输入明确
  给出转载归属时记录，不自行判断转载关系。
- **RSS 不等于全文**：只读取标题与 RSS 摘要，未抓取文章正文；`content_scope`
  会标注「未读取全文」。
- **模型可能出错**：归组、筛选、翻译与总结都可能误判、误译或遗漏，程序做了 id 校验、
  归组去重与失败降级，但无法消除模型错误。
- **多来源报道不等于独立核实**：两张卡里的「共同报道」只表示两家都写了相近内容，
  不是「已证实事实」，也不是独立事实核查；「未提及」不等于否认。
- **本地自用工具**：没有在线服务、没有 APK/移动端、没有论坛或讨论区，也不提供
  部署为一站式服务的支持。

---

## 开发方式说明

本项目在开发过程中使用了 AI 编码工具辅助生成代码与文档；需求设计、流程定义、
运行测试与结果核对由维护者完成并负责。提示词与校验规则随实验持续调整，仅供参考。

---

## 许可证与第三方内容

- 本项目代码以 [MIT License](LICENSE) 授权（版权所有者姓名见 LICENSE 首行占位符，
  由维护者填写）。
- 该许可证**仅覆盖本项目有权授权的代码与文档**，不授予任何第三方新闻内容的版权，
  也不授予 BBC、The Guardian、DeepSeek 或其它名称的商标使用权。
- 直接依赖：[requests](https://github.com/psf/requests)（Apache-2.0）、
  [feedparser](https://github.com/kurtmckee/feedparser)（BSD）。二者均为宽松许可证；
  如需在发行物中捆绑分发，请按各自许可证要求保留其版权与许可声明。
- 本项目不含第三方新闻全文；演示数据为虚构，不包含真实新闻内容。

---

## 后续计划（暂未实现）

以下仅为可能方向，**尚未实现**，不代表当前已有：

- 抓取文章全文（当前仅标题 + RSS 摘要）。
- 定时自动运行（如 cron / 计划任务）。
- 更多新闻来源与更多语言。
- 提供可部署的 Web 服务或在线页面。
- 更系统的单元测试与模型输出质量评估。

## 贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md)。请勿在 Issue、评论或日志中粘贴 API Key 或
`.env` 内容。
