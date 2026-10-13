#!/usr/bin/env python3
"""把 output/events.json 渲染成 output/events.html。

仅用 Python 标准库；不联网、不调用 AI、不启动服务器。
生成后双击 output/events.html 即可查看（离线可用）。

用法:
    py -3.13 render_events.py [输入json] [输出html]
    默认: output/events.json -> output/events.html
"""

import html
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

BEIJING = timezone(timedelta(hours=8))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(BASE_DIR, "output", "events.json")
DEFAULT_OUTPUT = os.path.join(BASE_DIR, "output", "events.html")

CSS = """
:root {
  --bg: #f7f7f5;
  --card-bg: #ffffff;
  --text: #1c1c1c;
  --muted: #6b6b6b;
  --accent: #2b5c8a;
  --border: #e4e4e0;
  --warn: #8a5a2b;
  --warn-bg: #fdf3e7;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei",
    "PingFang SC", "Noto Sans CJK SC", "Helvetica Neue", Arial, sans-serif;
  font-size: 16px;
  line-height: 1.7;
  -webkit-font-smoothing: antialiased;
}
.container { max-width: 860px; margin: 0 auto; padding: 24px 16px 64px; }
header { margin-bottom: 20px; }
h1 { font-size: 1.55rem; line-height: 1.3; margin: 0 0 6px; }
.subtitle { color: var(--muted); font-size: .88rem; margin: 0; }
.notice {
  background: var(--warn-bg);
  border: 1px solid #e8c89a;
  color: var(--warn);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: .88rem;
  margin: 12px 0;
}
.order-note { color: var(--muted); font-size: .82rem; margin: 0 0 16px; }
.event-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px 20px;
  margin-bottom: 20px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, .03);
}
.event-card.multi { border-left: 4px solid var(--accent); }
.event-head { display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: center; margin-bottom: 6px; }
.event-title { font-size: 1.15rem; line-height: 1.4; margin: 0; }
.event-badge {
  display: inline-block;
  font-size: .7rem;
  font-weight: 600;
  color: #fff;
  background: var(--accent);
  border-radius: 999px;
  padding: 2px 10px;
  white-space: nowrap;
}
.event-badge.single { background: #9a9a94; }
.group-reason { font-size: .82rem; color: var(--muted); margin: 0 0 12px; }
.articles-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}
.article-cell {
  background: #fafaf7;
  border-left: 3px solid var(--border);
  border-radius: 0 6px 6px 0;
  padding: 10px 12px;
}
.cell-title { font-size: .95rem; line-height: 1.45; margin: 0 0 6px; }
.cell-meta { font-size: .8rem; color: var(--muted); margin-bottom: 6px; }
.cell-meta a { color: var(--accent); text-decoration: none; }
.cell-meta a:hover { text-decoration: underline; }
.cell-desc { font-size: .85rem; color: #555; margin: 0; white-space: pre-wrap; word-break: break-word; }
.empty { color: var(--muted); text-align: center; padding: 40px 0; }
footer { color: var(--muted); font-size: .8rem; margin-top: 8px; text-align: center; }
.brief-card {
  background: #fbfbfa;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 16px;
  margin: 12px 0;
}
.brief-part { margin-bottom: 14px; }
.brief-part:last-child { margin-bottom: 0; }
.brief-label {
  font-size: .78rem;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: .04em;
  margin: 0 0 6px;
}
.brief-note { font-weight: 400; color: var(--muted); letter-spacing: 0; }
.brief-item {
  margin-bottom: 10px;
  padding-left: 10px;
  border-left: 2px solid var(--border);
}
.brief-item:last-child { margin-bottom: 0; }
.brief-en { margin: 0 0 2px; font-size: .92rem; }
.brief-zh { margin: 0 0 4px; font-size: .92rem; color: #444; }
.brief-source { margin-bottom: 8px; }
.brief-source:last-child { margin-bottom: 0; }
.brief-source-name { margin: 0 0 4px; font-size: .82rem; font-weight: 600; color: var(--muted); }
.brief-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.id-tag {
  font-size: .72rem;
  color: var(--accent);
  background: #eef3f8;
  border-radius: 4px;
  padding: 1px 6px;
  text-decoration: none;
  white-space: nowrap;
}
.id-tag:hover { text-decoration: underline; }
.brief-empty { color: var(--muted); font-size: .85rem; margin: 0; }
.notice.brief-failed { margin: 12px 0; }
details.original {
  margin-top: 12px;
  border-top: 1px dashed var(--border);
  padding-top: 10px;
}
details.original summary {
  cursor: pointer;
  font-size: .82rem;
  color: var(--accent);
  font-weight: 600;
}
@media (max-width: 480px) {
  h1 { font-size: 1.35rem; }
  .event-title { font-size: 1.05rem; }
  .event-card { padding: 14px 15px; }
  .container { padding: 18px 12px 48px; }
}
"""


def esc(text):
    return html.escape("" if text is None else str(text))


def safe_url(url):
    u = (url or "").strip()
    p = urlparse(u)
    if p.scheme in ("http", "https") and p.netloc:
        return u
    return None


def to_beijing(iso):
    try:
        dt = datetime.fromisoformat(str(iso))
    except (ValueError, TypeError):
        return str(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BEIJING).strftime("%Y-%m-%d %H:%M")


def event_heading(ev, articles):
    if ev.get("title_zh"):
        return esc(ev["title_zh"])
    if len(articles) == 1:
        return esc(articles[0]["title"])
    return "（未生成中文标题）"


def render_article_cell(a):
    title = esc(a.get("title", ""))
    source = esc(a.get("source", ""))
    published = to_beijing(a.get("published_at", "")) or "时间未知"
    desc = esc(a.get("rss_description")) or "（无 RSS 摘要）"

    url = safe_url(a.get("url"))
    if url:
        link = f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">原文链接 →</a>'
    else:
        link = '<span>原文链接不可用</span>'

    return f'''
    <div class="article-cell">
      <h3 class="cell-title">{title}</h3>
      <div class="cell-meta">{source} · {published}（北京时间） · {link}</div>
      <p class="cell-desc">{desc}</p>
    </div>'''


def render_id_tag(aid, articles_by_id):
    """把一个 article_id 渲染成可跳转到来源的小标签。"""
    a = articles_by_id.get(aid)
    if not a:
        return ""
    url = safe_url(a.get("url"))
    label = esc(a.get("source") or aid)
    if url:
        return (
            f'<a class="id-tag" href="{esc(url)}" target="_blank" rel="noopener noreferrer" '
            f'title="{esc(aid)}">{label} ↗</a>'
        )
    return f'<span class="id-tag" title="{esc(aid)}">{label}</span>'


def _brief_item_html(item, articles_by_id):
    ids = item.get("article_ids") or [item.get("article_id")]
    tags = "".join(render_id_tag(i, articles_by_id) for i in ids if i)
    return (
        '<div class="brief-item">'
        f'<p class="brief-en">{esc(item.get("en", ""))}</p>'
        f'<p class="brief-zh">{esc(item.get("zh", ""))}</p>'
        f'<div class="brief-tags">{tags}</div>'
        "</div>"
    )


def render_brief_card(ev, brief, articles_by_id):
    b = brief["brief"]
    parts = []

    ov = b.get("overview") or {}
    parts.append(
        '<section class="brief-part">'
        '<h4 class="brief-label">事件概述</h4>'
        f'<p class="brief-en">{esc(ov.get("en", ""))}</p>'
        f'<p class="brief-zh">{esc(ov.get("zh", ""))}</p>'
        "</section>"
    )

    common = b.get("common") or []
    if common:
        common_html = "".join(_brief_item_html(i, articles_by_id) for i in common)
    else:
        common_html = '<p class="brief-empty">（两份输入未发现可明确共同支持的信息）</p>'
    parts.append(
        '<section class="brief-part">'
        '<h4 class="brief-label">共同报道 <span class="brief-note">（非独立核实）</span></h4>'
        f"{common_html}</section>"
    )

    per_source = b.get("per_source") or []
    ps_html = ""
    for src in per_source:
        items_html = "".join(_brief_item_html(i, articles_by_id) for i in src.get("items", []))
        ps_html += (
            '<div class="brief-source">'
            f'<h5 class="brief-source-name">{esc(src.get("source", ""))}</h5>'
            f"{items_html}</div>"
        )
    if not per_source:
        ps_html = '<p class="brief-empty">（无单一来源的额外补充）</p>'
    parts.append(
        '<section class="brief-part">'
        '<h4 class="brief-label">各家补充</h4>'
        f"{ps_html}</section>"
    )

    lims = b.get("limitations") or []
    if lims:
        lim_html = "".join(_brief_item_html(i, articles_by_id) for i in lims)
    else:
        lim_html = '<p class="brief-empty">（未发现明显局限）</p>'
    parts.append(
        '<section class="brief-part">'
        '<h4 class="brief-label">材料局限</h4>'
        f"{lim_html}</section>"
    )

    return f'<div class="brief-card">{"".join(parts)}</div>'


def render_brief_failed(ev, brief):
    err = (brief.get("brief") or {}).get("error") or "未知错误"
    return (
        '<div class="notice brief-failed">'
        f'⚠ 事件卡生成失败（{esc(err)}），以下仅展示原始材料。</div>'
    )


def render_event(ev, articles_by_id, brief=None):
    articles = [articles_by_id[a] for a in ev["article_ids"] if a in articles_by_id]
    if not articles:
        return ""
    multi = ev.get("source_count", 0) >= 2
    cls = "event-card multi" if multi else "event-card"
    badge = f'{ev.get("source_count", 0)} 家媒体'
    badge_cls = "event-badge" if multi else "event-badge single"
    reason = ev.get("grouping_reason") or ""
    reason_html = f'<p class="group-reason">归组理由：{esc(reason)}</p>' if reason else ""
    cells = "\n".join(render_article_cell(a) for a in articles)

    if brief:
        status = (brief.get("brief") or {}).get("status")
        if status == "ok":
            brief_html = render_brief_card(ev, brief, articles_by_id)
            original = (
                f'<details class="original"><summary>原始材料（{len(articles)} 篇）</summary>'
                f'<div class="articles-grid">{cells}</div></details>'
            )
        else:
            brief_html = render_brief_failed(ev, brief)
            original = (
                f'<details class="original" open><summary>原始材料（{len(articles)} 篇）</summary>'
                f'<div class="articles-grid">{cells}</div></details>'
            )
    else:
        brief_html = ""
        original = f'<div class="articles-grid">{cells}</div>'

    return f'''
<article class="{cls}">
  <div class="event-head">
    <h2 class="event-title">{event_heading(ev, articles)}</h2>
    <span class="{badge_cls}">{esc(badge)}</span>
  </div>
  {reason_html}
  {brief_html}
  {original}
</article>'''


def sort_events(events, articles_by_id):
    def latest(ev):
        ts = [articles_by_id[a]["published_at"] for a in ev["article_ids"] if a in articles_by_id]
        return max(ts) if ts else ""
    # 先按最新发布时间倒序，再按「双来源优先」稳定排序（两段稳定排序，双来源在前、组内最新在前）
    events = sorted(events, key=latest, reverse=True)
    return sorted(events, key=lambda e: 0 if e.get("source_count", 0) >= 2 else 1)


def render(data, briefs=None):
    articles_by_id = {a["article_id"]: a for a in data.get("articles", [])}
    events = data.get("events", [])
    grouping = data.get("grouping", {})
    gen_time = to_beijing(data.get("generated_at", "")) or ""

    brief_by_event = {}
    if briefs:
        brief_by_event = {b.get("event_id"): b for b in briefs.get("events", [])}

    events = sort_events(events, articles_by_id)
    two_source = sum(1 for e in events if e.get("source_count", 0) >= 2)
    brief_ok = sum(
        1 for b in brief_by_event.values() if (b.get("brief") or {}).get("status") == "ok"
    )

    if events:
        cards = "\n".join(
            render_event(e, articles_by_id, brief_by_event.get(e["event_id"])) for e in events
        )
    else:
        cards = '<p class="empty">暂无候选新闻。</p>'

    status = grouping.get("status", "")
    if status == "fallback":
        notice = f'<div class="notice">⚠ 自动归组失败（{esc(grouping.get("message", ""))}），已退回逐条展示。</div>'
    else:
        notice = '<div class="notice">自动归组，尚未独立核实。</div>'

    order_note = f'<p class="order-note">含两个来源的事件优先展示（便于核对，非重要性排名）。多来源事件 {two_source} 个。</p>'

    brief_note = ""
    if briefs:
        brief_note = (
            '<p class="order-note">事件卡仅依据标题与 RSS 摘要；“共同报道”指两家来源都写了，'
            f'不等于独立核实；“未提及”不等于否认。已生成事件卡 {brief_ok} 个。</p>'
        )

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>同一事件 · 多源对照</title>
  <style>{CSS}</style>
</head>
<body>
  <div class="container">
    <header>
      <h1>同一事件 · 多源对照</h1>
      <p class="subtitle">生成于 {gen_time}（北京时间） · 候选 {len(data.get("articles", []))} 篇 · 事件 {len(events)} 个</p>
      {notice}
      {order_note}
      {brief_note}
    </header>
    {cards}
    <footer>本页由本地脚本生成，不调用 AI，不联网。归组仅依据标题与 RSS 摘要，未读取全文。</footer>
  </div>
</body>
</html>
'''


def load_briefs(input_path):
    """读取与 events.json 同目录的 event_briefs.json；不存在则返回 None。"""
    p = os.path.join(os.path.dirname(input_path), "event_briefs.json")
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def main(argv=None):
    argv = sys.argv if argv is None else argv
    input_path = argv[1] if len(argv) > 1 else DEFAULT_INPUT
    output_path = argv[2] if len(argv) > 2 else DEFAULT_OUTPUT

    if not os.path.exists(input_path):
        sys.stderr.write(f"ERROR: 找不到输入文件 {input_path}\n")
        return 1

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    briefs = load_briefs(input_path)
    page = render(data, briefs)

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(page)

    print(f"已生成: {output_path}（事件 {len(data.get('events', []))} 个）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
