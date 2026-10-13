#!/usr/bin/env python3
"""集中管理新闻源。

默认来源（按需在此启用/停用、调整每家候选上限）：
  BBC News      英国
  The Guardian  英国
  TASS          俄罗斯国家通讯社（英文版）
  Al Jazeera    卡塔尔 / 中东

也可用 --feeds 参数或 RSS_FEEDS 环境变量整体覆盖（覆盖后忽略本文件列表）。

各家内容版权归各媒体所有；这些均为免费公开 RSS，无需登录或密钥，仅用于
个人阅读/学习，不得再分发，具体以各媒体官网使用条款为准。
"""

import os

DEFAULT_MAX_CANDIDATES = 30

DEFAULT_SOURCES = [
    {
        "name": "BBC News",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "enabled": True,
        "max_candidates": 30,
    },
    {
        "name": "The Guardian",
        "url": "https://www.theguardian.com/world/rss",
        "enabled": True,
        "max_candidates": 30,
    },
    {
        "name": "TASS",
        "url": "https://tass.com/rss/v2.xml",
        "enabled": True,
        "max_candidates": 30,
    },
    {
        "name": "Al Jazeera",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "enabled": True,
        "max_candidates": 30,
    },
]


def resolve_sources(cli_feeds=None):
    """返回启用来源列表：[{name, url, max_candidates}, ...]。

    - 提供 --feeds 或 RSS_FEEDS（格式 "名称=URL,名称2=URL2"）时整体覆盖；
    - 否则使用 DEFAULT_SOURCES 中 enabled 的来源。
    """
    raw = cli_feeds or os.environ.get("RSS_FEEDS", "").strip()
    if raw:
        sources = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if "=" in part:
                name, url = part.split("=", 1)
                sources.append(
                    {"name": name.strip(), "url": url.strip(),
                     "max_candidates": DEFAULT_MAX_CANDIDATES}
                )
            else:
                sources.append(
                    {"name": "", "url": part, "max_candidates": DEFAULT_MAX_CANDIDATES}
                )
        return sources
    return [
        {"name": s["name"], "url": s["url"],
         "max_candidates": s.get("max_candidates", DEFAULT_MAX_CANDIDATES)}
        for s in DEFAULT_SOURCES
        if s.get("enabled", True)
    ]
