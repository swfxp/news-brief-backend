#!/usr/bin/env python3
"""每日中英双语新闻简报生成器（双来源）。

用法:
    python main.py            # 获取 BBC + The Guardian，调用 DeepSeek 生成摘要
    python main.py --dry-run  # 只获取新闻，不调用模型

输出: output/brief.json（UTF-8，中文原样显示）
"""

import argparse
import html
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import feedparser
import requests

from sources import resolve_sources

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"

USER_AGENT = "news-brief/1.0"

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")

BEIJING = timezone(timedelta(hours=8))


def beijing_now():
    """当前北京时间（aware datetime）。"""
    return datetime.now(BEIJING)


# DeepSeek API 用量统计（跨步骤累计，run_daily 结束时汇总）。
_API_USAGE = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def record_usage(usage):
    """累计一次 API 调用的 token 用量。usage 为响应中的 usage 字段（可能缺失）。"""
    if not isinstance(usage, dict):
        return
    _API_USAGE["calls"] += 1
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        v = usage.get(k)
        if isinstance(v, (int, float)):
            _API_USAGE[k] += int(v)


def usage_summary():
    """返回累计 API 用量（副本）。"""
    return dict(_API_USAGE)


def reset_usage():
    for k in _API_USAGE:
        _API_USAGE[k] = 0


def _fix_stdio_encoding():
    """让 stdout/stderr 输出 UTF-8，避免 Windows 控制台中文乱码。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


def load_dotenv(path=None):
    """加载项目目录的 .env 文件（不覆盖已存在的环境变量）。"""
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value


def load_config():
    return {
        "api_key": os.environ.get("DEEPSEEK_API_KEY", "").strip(),
        "base_url": os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        "model": os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL).strip(),
        "window_hours": int(os.environ.get("NEWS_WINDOW_HOURS", "24")),
        "max_articles": int(os.environ.get("MAX_ARTICLES", "5")),
    }


def clean_html(text):
    """去掉 HTML 标签与实体、尾部样板，压平成纯文本。"""
    if not text:
        return ""
    text = TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = WS_RE.sub(" ", text).strip()
    # 去掉 RSS 常见尾部样板（如 The Guardian 的 "Continue reading..."）
    text = re.sub(r"\s*Continue reading\.\.\.\s*$", "", text, flags=re.IGNORECASE)
    return text.strip()


def parse_published(entry):
    """解析条目发布时间，返回 UTC-aware datetime，失败返回 None。"""
    for key in ("published", "updated"):
        raw = entry.get(key)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except (TypeError, ValueError, IndexError):
                pass
    for key in ("published_parsed", "updated_parsed"):
        p = entry.get(key)
        if p:
            try:
                return datetime(*p[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    return None


def fetch_feed(url):
    """抓取单个 RSS，返回 (feed_title, entries)。entries 为 dict 列表。"""
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
    except requests.RequestException as exc:
        raise RuntimeError(f"无法访问 RSS 源 {url}: {exc}") from exc

    if resp.status_code != 200:
        raise RuntimeError(f"RSS 源返回 HTTP {resp.status_code}: {resp.text[:200]}")

    feed = feedparser.parse(resp.content)
    if not feed.entries:
        detail = getattr(feed, "bozo_exception", None)
        raise RuntimeError(f"RSS 解析失败或没有条目: {detail}")

    feed_title = feed.feed.get("title") or urlparse(url).netloc

    entries = []
    for entry in feed.entries:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue
        link = link.split("#", 1)[0]  # 去掉 fragment，便于去重
        entries.append(
            {
                "title": title,
                "url": link,
                "published_at": parse_published(entry),
                "description": clean_html(entry.get("summary") or entry.get("description") or ""),
            }
        )
    return feed_title, entries


def dedupe_by_url(entries):
    seen = set()
    out = []
    for e in entries:
        if e["url"] in seen:
            continue
        seen.add(e["url"])
        out.append(e)
    return out


def extract_json(text):
    """从模型输出中稳健地提取 JSON 对象。"""
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:]) if len(lines) > 1 else ""
        text = text.rstrip("`").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def summarize(api_key, base_url, model, title, description):
    """调用 DeepSeek，返回 (summary_en, summary_zh)。"""
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    system = (
        "你是一名新闻摘要员。严格遵守以下规则：\n"
        "1. 只根据用户提供的 TITLE 和 DESCRIPTION 总结，不得补充输入中不存在的事实、"
        "人名、日期、数字或背景；不得使用模型自身知识。\n"
        "2. 保留原文的归因与不确定性表述（如“据某方称”“至少”“可能”“据称”等），"
        "不得擅自去掉或改写成确定语气。\n"
        "3. 不添加带立场、价值判断或情绪化的措辞，保持中性客观。\n"
        "4. 无法确认中文译名的专有名词（人名、地名、机构名等）保留英文原文，"
        "不得自行创造或猜测中文译名。\n"
        "5. 严格区分动词含义：不要把“宣布 / 启动 / 开工 / 投产 / 计划 / 完成”等混为一谈，"
        "忠实对应原文。\n"
        "6. 中文翻译必须忠实对应英文摘要：英文摘要中的每个事实都必须在输入文本中有依据；"
        "中文不得添加英文中没有的信息。"
    )
    desc_text = description if description else "(未提供)"
    user = (
        "根据下面提供的新闻内容生成摘要，只能使用提供的内容：\n\n"
        f"TITLE: {title}\n"
        f"DESCRIPTION: {desc_text}\n\n"
        "要求：\n"
        "- 如果 DESCRIPTION 为“(未提供)”（只有标题）：summary_en 直接等于标题原文，"
        "不要改写或扩写成摘要；summary_zh 为标题的忠实中文翻译。\n"
        "- 如果提供了 DESCRIPTION：summary_en 为 1–2 句的英文摘要（严格基于标题+描述），"
        "summary_zh 为其忠实中文翻译。\n"
        "- 保留归因与不确定性表述；专有名词无法确认译名时保留原文。\n\n"
        "只输出一个 JSON 对象，恰好两个键：\n"
        '{"summary_en": "...", "summary_zh": "..."}'
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "stream": False,
        "response_format": {"type": "json_object"},
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
    except requests.RequestException as exc:
        raise RuntimeError(f"调用 DeepSeek API 网络失败: {exc}") from exc

    if resp.status_code != 200:
        raise RuntimeError(f"DeepSeek API 返回 HTTP {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    parsed = extract_json(content)
    summary_en = (parsed.get("summary_en") or "").strip()
    summary_zh = (parsed.get("summary_zh") or "").strip()
    if not summary_en or not summary_zh:
        raise RuntimeError("DeepSeek 返回了空的摘要")
    return summary_en, summary_zh


def main(argv=None):
    _fix_stdio_encoding()

    parser = argparse.ArgumentParser(description="每日中英双语新闻简报生成器（双来源）")
    parser.add_argument("--dry-run", action="store_true", help="只获取新闻，不调用 DeepSeek API")
    parser.add_argument("--feeds", help='覆盖新闻源，格式 "名称=URL,名称2=URL2"')
    parser.add_argument("--output", default="output/brief.json", help="输出文件路径")
    args = parser.parse_args(argv)

    load_dotenv()
    cfg = load_config()
    sources = resolve_sources(args.feeds)

    if not args.dry_run and not cfg["api_key"]:
        sys.stderr.write(
            "ERROR: 缺少 DEEPSEEK_API_KEY。请设置环境变量或写入 .env 文件"
            "（参考 .env.example）。或使用 --dry-run 只抓取新闻。\n"
        )
        return 1

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=cfg["window_hours"])
    window_end = now

    source_results = []
    all_selected = []

    for s in sources:
        name, url = s["name"], s["url"]
        try:
            feed_title, entries = fetch_feed(url)
        except RuntimeError as exc:
            sys.stderr.write(f"WARNING: 来源获取失败 [{name or url}]: {exc}\n")
            source_results.append(
                {
                    "name": name or url,
                    "url": url,
                    "status": "error",
                    "fetched": 0,
                    "in_window": 0,
                    "selected": 0,
                    "error": str(exc),
                }
            )
            continue

        source_name = name or feed_title

        # 每个来源独立：过滤时间窗口 -> 去重 -> 取最新 N 条
        in_window = [
            e
            for e in entries
            if e["published_at"] and window_start <= e["published_at"] <= window_end
        ]
        in_window.sort(key=lambda e: e["published_at"], reverse=True)
        selected = dedupe_by_url(in_window)[: cfg["max_articles"]]

        source_results.append(
            {
                "name": source_name,
                "url": url,
                "status": "ok",
                "fetched": len(entries),
                "in_window": len(in_window),
                "selected": len(selected),
                "error": None,
            }
        )

        for e in selected:
            e["source"] = source_name
            all_selected.append(e)

    # 合并后按发布时间倒序（不同来源各自展示，不做跨源去重/聚类）
    all_selected.sort(key=lambda e: e["published_at"], reverse=True)

    articles = []
    for e in all_selected:
        scope = "title_only" if not e["description"] else "title_and_rss_summary"
        article = {
            "title": e["title"],
            "source": e["source"],
            "url": e["url"],
            "published_at": e["published_at"].isoformat(),
            "content_scope": scope,
            "rss_description": e["description"],
        }
        if args.dry_run:
            article["summary_en"] = None
            article["summary_zh"] = None
        else:
            try:
                en, zh = summarize(
                    cfg["api_key"], cfg["base_url"], cfg["model"], e["title"], e["description"]
                )
                article["summary_en"] = en
                article["summary_zh"] = zh
            except Exception as exc:  # noqa: BLE001 单条失败不影响整体
                sys.stderr.write(f"WARNING: 摘要生成失败 [{e['title'][:50]}]: {exc}\n")
                article["summary_en"] = None
                article["summary_zh"] = None
        articles.append(article)

    output = {
        "generated_at": now.isoformat(),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "sources": source_results,
        "articles": articles,
    }

    out_path = args.output
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    ok_count = sum(1 for s in source_results if s["status"] == "ok")
    err_count = sum(1 for s in source_results if s["status"] == "error")
    print(f"来源: {ok_count} 成功, {err_count} 失败; 合并选取 {len(articles)} 条。")
    for s in source_results:
        if s["status"] == "ok":
            print(
                f"  [{s['name']}] 成功: 抓取 {s['fetched']} 条, "
                f"窗口内 {s['in_window']} 条, 选取 {s['selected']} 条"
            )
        else:
            print(f"  [{s['name']}] 失败: {s['error']}")
    print(f"输出: {out_path}")
    if not articles:
        print("所有来源均未产出窗口内的新闻。")
    elif args.dry_run:
        print("dry-run 模式：未调用模型，summary_en/summary_zh 为 null。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
