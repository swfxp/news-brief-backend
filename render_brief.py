#!/usr/bin/env python3
"""把 output/brief.json 渲染成 output/brief.html。

仅用 Python 标准库；不联网、不调用 AI、不启动服务器。
生成后双击 output/brief.html 即可在浏览器查看（含来源筛选，可离线使用）。

用法:
    py -3.13 render_brief.py [输入json] [输出html]
    默认: output/brief.json -> output/brief.html
"""

import html
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

BEIJING = timezone(timedelta(hours=8))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(BASE_DIR, "output", "brief.json")
DEFAULT_OUTPUT = os.path.join(BASE_DIR, "output", "brief.html")

# 来源筛选按钮的短标签
SHORT_LABELS = {"BBC News": "BBC", "The Guardian": "The Guardian"}

CSS = """
:root {
  --bg: #f7f7f5;
  --card-bg: #ffffff;
  --text: #1c1c1c;
  --muted: #6b6b6b;
  --accent: #2b5c8a;
  --zh-accent: #a0612c;
  --border: #e4e4e0;
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
.container { max-width: 720px; margin: 0 auto; padding: 24px 16px 64px; }
header { margin-bottom: 20px; }
h1 { font-size: 1.55rem; line-height: 1.3; margin: 0 0 6px; }
.subtitle { color: var(--muted); font-size: .88rem; margin: 0; }
.warn-banner {
  background: #fdf3e7;
  border: 1px solid #e8c89a;
  color: #8a5a2b;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: .88rem;
  margin: 12px 0;
}
.source-status { font-size: .82rem; color: var(--muted); margin: 10px 0 4px; }
.status-item { display: inline-block; margin-right: 16px; }
.status-item.ok::before { content: "✓ "; color: #2e8b57; font-weight: 700; }
.status-item.err::before { content: "✗ "; color: #c0392b; font-weight: 700; }
.filters { display: flex; flex-wrap: wrap; gap: 8px; margin: 14px 0 18px; }
.filter-btn {
  font: inherit;
  font-size: .88rem;
  color: var(--text);
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 5px 16px;
  cursor: pointer;
}
.filter-btn:hover { border-color: var(--accent); color: var(--accent); }
.filter-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; }
.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, .03);
}
.scope-note {
  display: inline-block;
  font-size: .72rem;
  color: var(--muted);
  background: #efefe9;
  border-radius: 999px;
  padding: 2px 10px;
  margin-bottom: 10px;
}
.title { font-size: 1.15rem; line-height: 1.45; margin: 0 0 8px; }
.meta {
  font-size: .85rem;
  color: var(--muted);
  margin-bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  align-items: center;
}
.meta a { color: var(--accent); text-decoration: none; }
.meta a:hover { text-decoration: underline; }
.unavailable { color: #999; }
.lang-block { margin: 12px 0; }
.lang-label {
  display: inline-block;
  font-size: .66rem;
  font-weight: 600;
  letter-spacing: .06em;
  color: #fff;
  background: var(--accent);
  border-radius: 4px;
  padding: 1px 7px;
  margin-right: 8px;
}
.lang-zh .lang-label { background: var(--zh-accent); }
.lang-block p { margin: 4px 0 0; }
details {
  margin-top: 12px;
  border-top: 1px dashed var(--border);
  padding-top: 10px;
}
summary {
  cursor: pointer;
  font-size: .85rem;
  color: var(--accent);
  user-select: none;
}
summary:hover { text-decoration: underline; }
.rss-desc {
  font-size: .85rem;
  color: #555;
  background: #fafaf7;
  border-left: 3px solid var(--border);
  padding: 8px 12px;
  margin-top: 8px;
  border-radius: 0 6px 6px 0;
  white-space: pre-wrap;
  word-break: break-word;
}
.empty { color: var(--muted); text-align: center; padding: 40px 0; }
footer {
  color: var(--muted);
  font-size: .8rem;
  margin-top: 8px;
  text-align: center;
}
@media (max-width: 480px) {
  h1 { font-size: 1.35rem; }
  .title { font-size: 1.05rem; }
  .card { padding: 14px 15px; }
  .container { padding: 18px 12px 48px; }
}
"""


def esc(text):
    """HTML 转义，防止新闻文本中的特殊字符破坏页面结构。"""
    return html.escape("" if text is None else str(text))


def safe_url(url):
    """只允许 http/https 链接，其余返回 None（不渲染成可点击链接）。"""
    u = (url or "").strip()
    p = urlparse(u)
    if p.scheme in ("http", "https") and p.netloc:
        return u
    return None


def to_beijing(iso):
    """把 ISO8601 时间转成北京时间（UTC+8）的字符串。"""
    try:
        dt = datetime.fromisoformat(str(iso))
    except (ValueError, TypeError):
        return str(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BEIJING).strftime("%Y-%m-%d %H:%M")


def short_label(name):
    return SHORT_LABELS.get(name, name)


def render_article(a):
    title = esc(a.get("title", ""))
    source = esc(a.get("source", ""))
    published = to_beijing(a.get("published_at", "")) or "时间未知"
    summary_en = esc(a.get("summary_en")) or "（未生成）"
    summary_zh = esc(a.get("summary_zh")) or "（未生成）"
    rss_desc = a.get("rss_description") or ""

    url = safe_url(a.get("url"))
    if url:
        link = f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">原文链接 →</a>'
    else:
        link = '<span class="unavailable">原文链接不可用</span>'

    rss_body = esc(rss_desc) if rss_desc else "（此条仅有标题，无 RSS 摘要）"

    return f'''
<article class="card" data-source="{source}">
  <div class="scope-note">仅依据标题与 RSS 摘要，未读取全文</div>
  <h2 class="title">{title}</h2>
  <div class="meta">
    <span class="source">{source}</span>
    <span class="time">{published}（北京时间）</span>
    {link}
  </div>
  <div class="lang-block">
    <span class="lang-label lang-en">EN</span>
    <p>{summary_en}</p>
  </div>
  <div class="lang-block lang-zh">
    <span class="lang-label lang-zh">中文</span>
    <p>{summary_zh}</p>
  </div>
  <details class="rss-details">
    <summary>核对原始摘要</summary>
    <div class="rss-desc">{rss_body}</div>
  </details>
</article>
'''


def render_source_status(sources):
    items = []
    for s in sources:
        name = esc(s.get("name") or s.get("url") or "未知来源")
        if s.get("status") == "ok":
            text = f"{name}：成功（抓取 {s.get('fetched', 0)} 条，窗口内 {s.get('in_window', 0)} 条，选 {s.get('selected', 0)}）"
            items.append(f'<span class="status-item ok">{esc(text)}</span>')
        else:
            err = esc(s.get("error") or "获取失败")
            items.append(f'<span class="status-item err">{name}：失败（{err}）</span>')
    return '<div class="source-status">' + "\n".join(items) + "</div>"


def render_filters(source_names):
    buttons = ['<button class="filter-btn active" data-filter="all">全部</button>']
    for name in source_names:
        label = short_label(name)
        buttons.append(
            f'<button class="filter-btn" data-filter="{esc(name)}">{esc(label)}</button>'
        )
    return '<div class="filters">' + "\n".join(buttons) + "</div>"


FILTER_JS = """
<script>
(function () {
  var btns = document.querySelectorAll('.filter-btn');
  var cards = document.querySelectorAll('.card');
  btns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      btns.forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      var f = btn.getAttribute('data-filter');
      cards.forEach(function (card) {
        var show = (f === 'all' || card.getAttribute('data-source') === f);
        card.style.display = show ? '' : 'none';
      });
    });
  });
})();
</script>
"""


def render(data):
    articles = data.get("articles", [])
    sources = data.get("sources", [])
    gen_time = to_beijing(data.get("generated_at", "")) or ""
    count = len(articles)

    # 来源名称（用于筛选按钮）：优先取 sources，回退到 articles 去重
    source_names = []
    for s in sources:
        n = s.get("name")
        if n and n not in source_names:
            source_names.append(n)
    if not source_names:
        for a in articles:
            n = a.get("source")
            if n and n not in source_names:
                source_names.append(n)

    status_html = render_source_status(sources) if sources else ""
    filters_html = render_filters(source_names) if len(source_names) > 1 else ""

    failed = [s for s in sources if s.get("status") != "ok"]
    warn_html = ""
    if failed:
        names = "、".join(esc(s.get("name") or s.get("url") or "") for s in failed)
        warn_html = f'<div class="warn-banner">⚠ 部分来源获取失败（{names}），以下仅包含成功来源的新闻。</div>'
    elif not sources and not articles:
        warn_html = '<div class="warn-banner">⚠ 未获取到任何新闻。</div>'

    if articles:
        cards = "\n".join(render_article(a) for a in articles)
    else:
        cards = '<p class="empty">暂无新闻。</p>'

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>最新新闻 · 双语速读</title>
  <style>{CSS}</style>
</head>
<body>
  <div class="container">
    <header>
      <h1>最新新闻 · 双语速读</h1>
      <p class="subtitle">生成于 {gen_time}（北京时间） · 共 {count} 条 · 仅依据标题与 RSS 摘要，未读取全文</p>
      {status_html}
      {warn_html}
      {filters_html}
    </header>
    {cards}
    <footer>本页由本地脚本生成，不调用 AI，不联网。不同来源的报道分别展示，便于人工比较。</footer>
  </div>
  {FILTER_JS}
</body>
</html>
'''


def main(argv=None):
    argv = sys.argv if argv is None else argv
    input_path = argv[1] if len(argv) > 1 else DEFAULT_INPUT
    output_path = argv[2] if len(argv) > 2 else DEFAULT_OUTPUT

    if not os.path.exists(input_path):
        sys.stderr.write(f"ERROR: 找不到输入文件 {input_path}\n")
        return 1

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    page = render(data)

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(page)

    print(f"已生成: {output_path}（共 {len(data.get('articles', []))} 条）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
