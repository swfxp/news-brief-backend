#!/usr/bin/env python3
"""生成「虚构演示数据」的本地演示页面（无需 API Key、不联网、不调用 AI）。

本目录（demo/）下由本脚本生成的全部数据均为虚构：人物、机构、地点、事件、
媒体名称（“示例媒体 A / B”）与链接（example.com）都是编造的，仅用于展示工具的
输出样式，不代表任何真实新闻或真实媒体立场。

用法（在项目根目录执行）：
    python3 demo/make_demo.py

生成产物（均在 demo/ 下）：
    events.json / event_briefs.json / events.html      多源对照页
    daily_brief.json / daily_brief.html                每日选读页

依赖：仅 Python 标准库 + 本仓库的 render_events.py / render_daily_brief.py
（二者也只使用标准库，不联网、不调用 AI）。
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import render_daily_brief
import render_events

DEMO_DIR = os.path.dirname(os.path.abspath(__file__))

DEMO_BANNER = (
    '<div style="background:#5b1f1f;color:#fff;border-radius:8px;padding:12px 16px;'
    'margin:0 0 16px;font-size:.95rem;font-weight:600;">'
    "⚠ 虚构演示数据 · 非真实新闻（仅展示工具输出样式）</div>"
)

GENERATED_AT = "2026-01-01T00:00:00+00:00"
WINDOW_START = "2025-12-31T00:00:00+00:00"
WINDOW_END = "2026-01-01T00:00:00+00:00"

# ---- 虚构文章（article_id 以 demo 前缀标识，链接均为 example.com）----
ARTICLES = [
    {
        "article_id": "demo000000001",
        "title": "Atlantis port fuel depot blast injures six workers",
        "source": "示例媒体 A",
        "url": "https://example.com/demo/a1",
        "published_at": "2025-12-31T09:00:00+00:00",
        "rss_description": "A fuel tank exploded at the port of Atlantis early Monday, "
        "injuring six workers, officials said. The cause is under investigation.",
    },
    {
        "article_id": "demo000000002",
        "title": "Six hurt in blast at Atlantis port storage depot",
        "source": "示例媒体 B",
        "url": "https://example.com/demo/a2",
        "published_at": "2025-12-31T09:30:00+00:00",
        "rss_description": "Six people were injured in an explosion at a storage depot near "
        "Atlantis port, emergency services said. No deaths were reported.",
    },
    {
        "article_id": "demo000000003",
        "title": "Atlantis parliament passes new data privacy law",
        "source": "示例媒体 A",
        "url": "https://example.com/demo/a3",
        "published_at": "2025-12-31T10:00:00+00:00",
        "rss_description": "Atlantis lawmakers approved a new data privacy law on Monday, "
        "which officials said would give residents more control over personal data.",
    },
    {
        "article_id": "demo000000004",
        "title": "Power cut hits northern Atlantis",
        "source": "示例媒体 B",
        "url": "https://example.com/demo/a4",
        "published_at": "2025-12-31T11:00:00+00:00",
        "rss_description": "",
    },
]

# ---- 归组结果（events.json 的 events）----
EVENTS = [
    {
        "event_id": "e1",
        "title_zh": "亚特兰蒂斯港储油罐爆炸致 6 人受伤",
        "article_ids": ["demo000000001", "demo000000002"],
        "source_count": 2,
        "grouping_reason": "两篇都报道同一起亚特兰蒂斯港储油设施爆炸、6 人受伤。",
    },
    {
        "event_id": "e2",
        "title_zh": "亚特兰蒂斯议会通过新数据隐私法",
        "article_ids": ["demo000000003"],
        "source_count": 1,
        "grouping_reason": "",
    },
    {
        "event_id": "e3",
        "title_zh": "亚特兰蒂斯北部发生停电",
        "article_ids": ["demo000000004"],
        "source_count": 1,
        "grouping_reason": "",
    },
]

# ---- 双来源事件卡（四段式：概述 / 共同报道 / 各家补充 / 材料局限）----
DUAL_BRIEF = {
    "status": "ok",
    "title": {
        "en": "Atlantis port fuel depot blast injures six",
        "zh": "亚特兰蒂斯港储油罐爆炸致 6 人受伤",
    },
    "overview": {
        "en": "Six people were injured in an explosion at a fuel depot near Atlantis port, officials said.",
        "zh": "据官员称，亚特兰蒂斯港附近一座储油设施发生爆炸，6 人受伤。",
    },
    "common": [
        {
            "en": "Six people were injured in an explosion at a fuel/storage depot near Atlantis port.",
            "zh": "亚特兰蒂斯港附近一座储油设施发生爆炸，6 人受伤。",
            "article_ids": ["demo000000001", "demo000000002"],
        }
    ],
    "per_source": [
        {
            "source": "示例媒体 A",
            "items": [
                {
                    "en": "The cause is under investigation, officials said.",
                    "zh": "官员称事故原因正在调查中。",
                    "article_id": "demo000000001",
                }
            ],
        },
        {
            "source": "示例媒体 B",
            "items": [
                {
                    "en": "No deaths were reported, emergency services said.",
                    "zh": "应急部门称无死亡报告。",
                    "article_id": "demo000000002",
                }
            ],
        },
    ],
    "limitations": [
        {
            "en": "This tool read only the titles and RSS summaries, not the full articles.",
            "zh": "本工具仅读取标题与 RSS 摘要，未读取全文。",
            "article_ids": ["demo000000001", "demo000000002"],
        }
    ],
}

# ---- 单来源事件卡（完整：概述 / 要点 / 材料局限）----
SINGLE_BRIEF_E2 = {
    "status": "ok",
    "single_source": True,
    "source": "示例媒体 A",
    "title": {
        "en": "Atlantis parliament passes new data privacy law",
        "zh": "亚特兰蒂斯议会通过新数据隐私法",
    },
    "overview": {
        "en": "Atlantis lawmakers approved a new data privacy law, which officials said would "
        "give residents more control over personal data.",
        "zh": "亚特兰蒂斯议会通过一项新数据隐私法，官员称该法将赋予居民更多个人数据控制权。",
    },
    "points": [
        {
            "en": "The law was passed on Monday.",
            "zh": "该法于周一通过。",
            "article_id": "demo000000003",
        }
    ],
    "limitations": [
        {
            "en": "Only one source; this tool read only the title and RSS summary, not the full article.",
            "zh": "单一来源；本工具仅读取标题与 RSS 摘要，未读取全文。",
            "article_ids": ["demo000000003"],
        }
    ],
}

# ---- 单来源 + 材料不足（仅有标题、无 RSS 摘要）----
SINGLE_BRIEF_E3 = {
    "status": "ok",
    "single_source": True,
    "source": "示例媒体 B",
    "title": {
        "en": "Power cut hits northern Atlantis",
        "zh": "亚特兰蒂斯北部发生停电",
    },
    "overview": {
        "en": "This entry has only a headline and no RSS summary, so further details are unavailable.",
        "zh": "该条目仅有标题、无 RSS 摘要，详情不可知。",
    },
    "points": [
        {
            "en": "A power cut affected northern Atlantis.",
            "zh": "亚特兰蒂斯北部发生停电。",
            "article_id": "demo000000004",
        }
    ],
    "limitations": [
        {
            "en": "This entry has only a title and no RSS summary.",
            "zh": "该条目仅有标题，无 RSS 摘要。",
            "article_ids": ["demo000000004"],
        }
    ],
}

SOURCES = [
    {"name": "示例媒体 A", "url": "https://example.com/demo/feed-a", "status": "ok",
     "fetched": 3, "in_window": 3, "selected": 3, "error": None},
    {"name": "示例媒体 B", "url": "https://example.com/demo/feed-b", "status": "ok",
     "fetched": 2, "in_window": 2, "selected": 2, "error": None},
]


def _selection_reason(ev, en, zh):
    return {"en": en, "zh": zh, "article_ids": list(ev["article_ids"])}


def build_events_data():
    return {
        "generated_at": GENERATED_AT,
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        "sources": SOURCES,
        "articles": ARTICLES,
        "events": EVENTS,
        "grouping": {
            "status": "ok",
            "message": "归组完成：1 个多篇组，其余 2 篇单独成组。",
            "candidate_count": len(ARTICLES),
            "event_count": len(EVENTS),
            "two_source_events": 1,
        },
    }


def build_briefs_data():
    return {
        "generated_at": GENERATED_AT,
        "source_events_file": "demo/events.json",
        "dual_source_only": True,
        "prompt_version": "demo",
        "events": [
            {
                "event_id": "e1",
                "title_zh": EVENTS[0]["title_zh"],
                "article_ids": EVENTS[0]["article_ids"],
                "source_count": 2,
                "material_hash": "demo-e1",
                "brief": DUAL_BRIEF,
            }
        ],
    }


def build_daily_data():
    events = [
        {
            "event_id": "e1",
            "title_en": DUAL_BRIEF["title"]["en"],
            "title_zh": DUAL_BRIEF["title"]["zh"],
            "article_ids": ["demo000000001", "demo000000002"],
            "source_count": 2,
            "reused": False,
            "material_hash": "demo-e1",
            "selection_reason": _selection_reason(
                EVENTS[0],
                "Two outlets both report the same port blast with six injured.",
                "两家媒体都报道了同一起港区爆炸、6 人受伤。",
            ),
            "card": DUAL_BRIEF,
        },
        {
            "event_id": "e2",
            "title_en": SINGLE_BRIEF_E2["title"]["en"],
            "title_zh": SINGLE_BRIEF_E2["title"]["zh"],
            "article_ids": ["demo000000003"],
            "source_count": 1,
            "reused": False,
            "material_hash": "demo-e2",
            "selection_reason": _selection_reason(
                EVENTS[1],
                "A concrete new development (a law passed), single source.",
                "有具体新进展（通过一项新法），单一来源。",
            ),
            "card": SINGLE_BRIEF_E2,
        },
        {
            "event_id": "e3",
            "title_en": SINGLE_BRIEF_E3["title"]["en"],
            "title_zh": SINGLE_BRIEF_E3["title"]["zh"],
            "article_ids": ["demo000000004"],
            "source_count": 1,
            "reused": False,
            "material_hash": "demo-e3",
            "selection_reason": _selection_reason(
                EVENTS[2],
                "Selected despite limited material (title only).",
                "材料不足（仅有标题）仍入选，以展示局限说明。",
            ),
            "card": SINGLE_BRIEF_E3,
        },
    ]
    return {
        "generated_at": GENERATED_AT,
        "fetched_at": GENERATED_AT,
        "source_events_file": "demo/events.json",
        "data_mode": "fresh",
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        "sources": SOURCES,
        "prompt_version": "demo",
        "scope_note": "当前来源范围内的选读，非全球热点排行榜",
        "selection": {
            "status": "ok",
            "candidate_count": 3,
            "selected_count": 3,
            "selected_event_ids": ["e1", "e2", "e3"],
            "unselected_event_ids": [],
            "message": "筛选完成：从 3 个事件中选出 3 件。",
        },
        "events": events,
    }


def _inject_banner(page):
    return page.replace('<div class="container">', f'<div class="container">\n    {DEMO_BANNER}', 1)


def _write(name, obj):
    path = os.path.join(DEMO_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path


def main():
    events_data = build_events_data()
    briefs_data = build_briefs_data()
    daily_data = build_daily_data()

    p1 = _write("events.json", events_data)
    p2 = _write("event_briefs.json", briefs_data)
    p3 = _write("daily_brief.json", daily_data)

    # 渲染多源对照页（events.html）
    events_page = _inject_banner(render_events.render(events_data, briefs_data))
    events_html = os.path.join(DEMO_DIR, "events.html")
    with open(events_html, "w", encoding="utf-8") as f:
        f.write(events_page)

    # 渲染每日选读页（daily_brief.html）；需把原始文章并入供渲染引用标签
    daily_render_data = dict(daily_data)
    daily_render_data["articles"] = ARTICLES
    daily_page = _inject_banner(render_daily_brief.render(daily_render_data))
    daily_html = os.path.join(DEMO_DIR, "daily_brief.html")
    with open(daily_html, "w", encoding="utf-8") as f:
        f.write(daily_page)

    print("演示数据已生成（全部为虚构，非真实新闻）：")
    print(f"  {p1}")
    print(f"  {p2}")
    print(f"  {p3}")
    print(f"  {events_html}")
    print(f"  {daily_html}")
    print("打开 demo/events.html 或 demo/daily_brief.html 即可离线查看。")


if __name__ == "__main__":
    main()
