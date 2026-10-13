#!/usr/bin/env python3
"""把 output/daily_brief.json 渲染成 output/daily_brief.html。

仅用 Python 标准库；不联网、不调用 AI、不启动服务器。
复用 render_events 的 HTML 转义、链接校验与事件卡渲染。

用法:
    python3 render_daily_brief.py [输入 daily_brief.json] [输出 daily_brief.html]
    默认: output/daily_brief.json -> output/daily_brief.html
"""

import json
import os
import sys

from render_events import (
    CSS,
    esc,
    render_article_cell,
    render_brief_card,
    render_id_tag,
    to_beijing,
)

DAILY_CSS = """
.reason {
  background: #f0f5f2;
  border: 1px solid #cfe0d3;
  border-radius: 8px;
  padding: 10px 14px;
  margin: 0 0 12px;
}
.reason-label {
  display: inline-block;
  font-size: .72rem;
  font-weight: 700;
  color: #2f6b46;
  letter-spacing: .04em;
  margin-bottom: 4px;
}
.reason-zh { margin: 0 0 2px; font-size: .92rem; }
.reason-en { margin: 0 0 4px; font-size: .88rem; color: #555; }
.single-source-card { border-left: 3px solid #b58900; }
.stats {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 14px;
  margin: 10px 0;
  font-size: .88rem;
}
.stats ul { margin: 6px 0 0; padding-left: 18px; }
.stats li { margin: 2px 0; }
.src-fail { color: var(--warn); }
.event-title-en {
  margin: 0 0 6px;
  color: var(--muted);
  font-size: .88rem;
  font-weight: 400;
}
.notice.historical {
  background: #f7e9e9;
  border-color: #e2b6b6;
  color: #8a2b2b;
}
"""


def _item(item, articles_by_id):
    ids = item.get("article_ids") or [item.get("article_id")]
    tags = "".join(render_id_tag(i, articles_by_id) for i in ids if i)
    return (
        '<div class="brief-item">'
        f'<p class="brief-en">{esc(item.get("en", ""))}</p>'
        f'<p class="brief-zh">{esc(item.get("zh", ""))}</p>'
        f'<div class="brief-tags">{tags}</div></div>'
    )


def render_single_card(card, articles_by_id):
    parts = []
    ov = card.get("overview") or {}
    parts.append(
        '<section class="brief-part"><h4 class="brief-label">事件概述</h4>'
        f'<p class="brief-en">{esc(ov.get("en", ""))}</p>'
        f'<p class="brief-zh">{esc(ov.get("zh", ""))}</p></section>'
    )
    points = card.get("points") or []
    ph = "".join(_item(p, articles_by_id) for p in points) if points else (
        '<p class="brief-empty">（无要点）</p>'
    )
    parts.append(
        '<section class="brief-part"><h4 class="brief-label">要点</h4>'
        f"{ph}</section>"
    )
    lims = card.get("limitations") or []
    lh = "".join(_item(l, articles_by_id) for l in lims) if lims else (
        '<p class="brief-empty">（未发现明显局限）</p>'
    )
    parts.append(
        '<section class="brief-part"><h4 class="brief-label">材料局限</h4>'
        f"{lh}</section>"
    )
    return f'<div class="brief-card single-source-card">{"".join(parts)}</div>'


def render_reason(ev, articles_by_id):
    r = ev.get("selection_reason") or {}
    tags = "".join(render_id_tag(i, articles_by_id) for i in r.get("article_ids", []))
    return (
        '<div class="reason">'
        '<span class="reason-label">入选理由</span>'
        f'<p class="reason-zh">{esc(r.get("zh", ""))}</p>'
        f'<p class="reason-en">{esc(r.get("en", ""))}</p>'
        f'<div class="brief-tags">{tags}</div></div>'
    )


def render_selected_event(ev, articles_by_id):
    articles = [articles_by_id[a] for a in ev["article_ids"] if a in articles_by_id]
    if not articles:
        return ""
    card = ev.get("card") or {}
    single = bool(card.get("single_source"))
    badge = "单一来源" if single else f"{ev.get('source_count', 0)} 家媒体"
    badge_cls = "event-badge single" if single else "event-badge"
    title_zh = esc(ev.get("title_zh") or (articles[0]["title"] if articles else ""))
    title_en = esc(ev.get("title_en") or "")
    title_en_html = f'<p class="event-title-en">{title_en}</p>' if title_en else ""
    reason = render_reason(ev, articles_by_id)
    cells = "\n".join(render_article_cell(a) for a in articles)

    if card.get("status") == "ok":
        body = render_single_card(card, articles_by_id) if single else render_brief_card(
            None, {"brief": card}, articles_by_id
        )
        original = (
            f'<details class="original"><summary>原始材料（{len(articles)} 篇）</summary>'
            f'<div class="articles-grid">{cells}</div></details>'
        )
    else:
        err = card.get("error") or "未知错误"
        body = f'<div class="notice brief-failed">⚠ 事件卡生成失败（{esc(err)}），仅展示原始材料。</div>'
        original = (
            f'<details class="original" open><summary>原始材料（{len(articles)} 篇）</summary>'
            f'<div class="articles-grid">{cells}</div></details>'
        )

    return f'''<article class="event-card multi">
  <div class="event-head">
    <h2 class="event-title">{title_zh}</h2>
    <span class="{badge_cls}">{esc(badge)}</span>
  </div>
  {title_en_html}
  {reason}
  {body}
  {original}
</article>'''


def render(data):
    articles_by_id = {a["article_id"]: a for a in data.get("articles", [])} if data.get("articles") else {}
    # daily_brief.json 不含 articles 全量，需要从 events.json 取原始文章；由调用方传入
    gen_time = to_beijing(data.get("generated_at", "")) or ""
    win_start = to_beijing(data.get("window_start", "")) or "—"
    win_end = to_beijing(data.get("window_end", "")) or "—"
    mode = data.get("data_mode", "")
    fetched = to_beijing(data.get("fetched_at", "")) or ""

    heading = "每日选读（历史数据）" if mode == "historical" else "每日选读"
    hist = (
        '<div class="notice historical">⚠ 历史数据：本页基于既有文件生成，未重新抓取，'
        "不代表今日采集，不构成今日简报。</div>"
        if mode == "historical"
        else ""
    )
    sub = f"生成于 {gen_time}（北京时间）"
    if fetched:
        sub += f" · 数据采集于 {fetched}（北京时间）"
    sub += " · 仅依据标题与 RSS 摘要，未读取全文"

    sel = data.get("selection", {})
    events = data.get("events", [])

    if events:
        cards = "\n".join(render_selected_event(e, articles_by_id) for e in events)
    elif sel.get("status") == "failed":
        cards = f'<div class="notice">⚠ 筛选失败：{esc(sel.get("message", ""))}。本次未生成卡片。</div>'
    else:
        cards = '<p class="empty">没有入选事件。</p>'

    src_failures = [s for s in data.get("sources", []) if s.get("status") == "error"]
    fail_html = ""
    if src_failures:
        items = "".join(
            f'<li class="src-fail">{esc(s.get("name", s.get("url", "?")))}：{esc(s.get("error", ""))}</li>'
            for s in src_failures
        )
        fail_html = f"<li>来源获取失败：<ul>{items}</ul></li>"

    stats = (
        '<div class="stats">'
        f'<div>候选事件 {sel.get("candidate_count", 0)} 个 · 入选 {sel.get("selected_count", 0)} 个'
        f' · 采集窗口 {win_start} ～ {win_end}（北京时间）</div>'
        f"{fail_html}</div>"
    )

    scope = f'<div class="notice">{esc(data.get("scope_note", ""))}</div>'

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{heading}</title>
  <style>{CSS}{DAILY_CSS}</style>
</head>
<body>
  <div class="container">
    <header>
      <h1>{heading}</h1>
      <p class="subtitle">{sub}</p>
      {hist}
      {scope}
      {stats}
    </header>
    {cards}
    <footer>本页由本地脚本生成，不调用 AI，不联网。“共同报道”不等于独立核实；“未提及”不等于否认。</footer>
  </div>
</body>
</html>
'''


def main(argv=None):
    argv = sys.argv if argv is None else argv
    input_path = argv[1] if len(argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "output", "daily_brief.json"
    )
    output_path = argv[2] if len(argv) > 2 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "output", "daily_brief.html"
    )

    if not os.path.exists(input_path):
        sys.stderr.write(f"ERROR: 找不到输入文件 {input_path}\n")
        return 1

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 原始文章在 events.json 里，不在 daily_brief.json 里；这里补入以便渲染原始材料
    data["articles"] = []
    src_events = os.path.join(os.path.dirname(input_path), "events.json")
    if os.path.exists(src_events):
        with open(src_events, "r", encoding="utf-8") as f:
            evdata = json.load(f)
        data["articles"] = evdata.get("articles", [])

    page = render(data)

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(page)

    print(f"已生成: {output_path}（入选 {len(data.get('events', []))} 件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
