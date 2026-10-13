#!/usr/bin/env python3
"""每日简报一键入口：采集 → 归组 → 筛选 → 生成/复用事件卡 → HTML。

按北京时间建立独立输出目录 output/<YYYY-MM-DD_HHMM>/，保存：
  events.json       原始输入（抓取的候选文章 + 归组结果）
  daily_brief.json  筛选结果与事件卡（含中英标题、入选理由、材料指纹）
  daily_brief.html  阅读页面
  manifest.json     本次运行元数据（数据模式、各步状态、API 用量、耗时）

默认重新抓取最近 24 小时数据（BBC/Guardian 需走本地代理）；--offline 使用既有
events.json 并标记「历史数据」，不复用缓存卡片。步骤失败明确报告，不拿旧输出冒充成功。

用法:
    # 完整运行（抓取需代理，DeepSeek 直连不走代理）
    HTTPS_PROXY=http://127.0.0.1:7890 HTTP_PROXY=http://127.0.0.1:7890 \
      NO_PROXY=api.deepseek.com python3 run_daily.py

    python3 run_daily.py --offline [--events output/events.json]   # 用既有数据，标记历史
    python3 run_daily.py --dry-run                                  # 只采集与归组，不调用模型
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

from main import (
    BEIJING,
    beijing_now,
    load_dotenv,
    reset_usage,
    usage_summary,
)
from sources import resolve_sources
from group_events import (
    fallback_events,
    fetch_candidates,
    group_candidates,
    load_config,
)
from daily_brief import build_daily_brief
import render_daily_brief

RUN_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}$")


def to_beijing_str(iso):
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(str(iso))
    except (ValueError, TypeError):
        return str(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BEIJING).strftime("%Y-%m-%d %H:%M")


def find_latest_events(output_root):
    """找到最新一份 events.json：先看根目录，再看各运行目录（时间戳倒序）。"""
    root_events = os.path.join(output_root, "events.json")
    if os.path.exists(root_events):
        return root_events
    if os.path.isdir(output_root):
        for name in sorted(os.listdir(output_root), reverse=True):
            p = os.path.join(output_root, name, "events.json")
            if os.path.exists(p):
                return p
    return None


def load_cache(output_root, current_run_dir):
    """从最近一次运行目录的 daily_brief.json 读取双来源卡片复用缓存。

    返回 (prompt_version, {material_hash: brief})。按 material_hash 建索引，因为
    event_id 是每次运行的排序序号、跨运行不稳定；只有原始材料完全一致才复用。
    """
    if not os.path.isdir(output_root):
        return None, {}
    dirs = sorted(
        (d for d in os.listdir(output_root)
         if RUN_DIR_RE.match(d) and os.path.isdir(os.path.join(output_root, d))),
        reverse=True,
    )
    for d in dirs:
        run_dir = os.path.join(output_root, d)
        if os.path.abspath(run_dir) == os.path.abspath(current_run_dir):
            continue
        p = os.path.join(run_dir, "daily_brief.json")
        if not os.path.exists(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                dd = json.load(f)
        except (OSError, ValueError):
            continue
        cache = {}
        for ev in dd.get("events", []):
            card = ev.get("card") or {}
            mh = ev.get("material_hash")
            if card.get("status") == "ok" and ev.get("source_count", 0) >= 2 and mh:
                cache[mh] = card
        return dd.get("prompt_version"), cache
    return None, {}


def write_manifest(run_dir, beijing_ts, data_mode, steps, ok, error, elapsed, usage, window):
    manifest = {
        "run_dir": run_dir,
        "beijing_time": beijing_ts,
        "data_mode": data_mode,
        "ok": ok,
        "error": error,
        "elapsed_seconds": round(elapsed, 2),
        "api_usage": usage,
        "window": {"start": window[0], "end": window[1]} if window else None,
        "steps": steps,
    }
    with open(os.path.join(run_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(
        description="每日简报一键入口：采集 → 归组 → 筛选 → 生成/复用卡片 → HTML"
    )
    parser.add_argument("--offline", action="store_true",
                        help="不重新抓取，使用既有 events.json，输出标记为历史数据")
    parser.add_argument("--dry-run", action="store_true",
                        help="只采集与归组，不调用模型（用于验证抓取）")
    parser.add_argument("--events", default=None, help="offline 模式下使用的 events.json 路径")
    parser.add_argument("--feeds", help='覆盖新闻源，格式 "名称=URL,名称2=URL2"')
    parser.add_argument("--output-root", default="output", help="输出根目录（默认 output）")
    args = parser.parse_args(argv)

    load_dotenv()
    reset_usage()
    cfg = load_config()  # 来自 group_events：api_key/base_url/model/window_hours/max_candidates
    sources = resolve_sources(args.feeds)

    t0 = time.time()
    beijing_ts = beijing_now().strftime("%Y-%m-%d_%H%M")
    run_dir = os.path.join(args.output_root, beijing_ts)
    os.makedirs(run_dir, exist_ok=True)
    steps = []

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=cfg["window_hours"])
    window_end = now

    # ---- Step 1 + 2：采集 + 归组 ----
    if args.offline:
        events_path = args.events or find_latest_events(args.output_root)
        if not events_path or not os.path.exists(events_path):
            print("ERROR: offline 模式找不到 events.json（可用 --events 指定）。")
            return 1
        with open(events_path, encoding="utf-8") as f:
            events_data = json.load(f)
        data_mode = "historical"
        steps.append({"step": "采集+归组", "status": "ok",
                      "detail": f"offline 使用既有数据（历史数据）: {events_path}"})
    else:
        candidates, source_results = fetch_candidates(
            sources, window_start, window_end, cfg["max_candidates"]
        )
        if not candidates:
            print("ERROR: 未获取到任何候选文章（来源可能全部失败，或窗口内无新闻）。")
            for s in source_results:
                if s["status"] == "error":
                    print(f"  来源失败 [{s.get('name', s.get('url'))}]: {s['error']}")
            write_manifest(run_dir, beijing_ts, "fresh", steps, ok=False,
                           error="未获取到任何候选文章", elapsed=time.time() - t0,
                           usage=usage_summary(),
                           window=(window_start.isoformat(), window_end.isoformat()))
            return 1

        if args.dry_run:
            events, status, message = fallback_events(candidates), "dry_run", (
                "dry-run：未调用模型，全部候选各自成组。"
            )
        else:
            # 归组校验失败（如某篇文章被放进多个组）时重试一次，仍失败才退回逐条展示。
            events, status, message = None, None, None
            for attempt in (1, 2):
                try:
                    events, status, message = group_candidates(cfg, candidates)
                except Exception as exc:  # noqa: BLE001
                    sys.stderr.write(f"WARNING: 归组调用失败（第 {attempt} 次）: {exc}\n")
                    events, status, message = fallback_events(candidates), "fallback", (
                        f"归组调用失败：{exc}；已退回逐条展示。"
                    )
                    break
                if status == "ok":
                    break
                sys.stderr.write(f"WARNING: 归组校验失败（第 {attempt} 次）：{message}\n")

        two_source = sum(1 for e in events if e["source_count"] >= 2)
        events_data = {
            "generated_at": now.isoformat(),
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "sources": source_results,
            "articles": candidates,
            "events": events,
            "grouping": {
                "status": status,
                "message": message,
                "candidate_count": len(candidates),
                "event_count": len(events),
                "two_source_events": two_source,
            },
        }
        data_mode = "fresh"
        steps.append({"step": "采集+归组", "status": "ok",
                      "detail": f"候选 {len(candidates)} 篇 / 事件 {len(events)} 个（归组 {status}）"})

    events_path = os.path.join(run_dir, "events.json")
    with open(events_path, "w", encoding="utf-8") as f:
        json.dump(events_data, f, ensure_ascii=False, indent=2)

    if args.dry_run:
        elapsed = time.time() - t0
        print("dry-run 完成（仅采集与归组，未调用模型）。")
        print(f"原始输入已保存: {events_path}")
        print(f"运行目录: {run_dir}")
        return 0

    if not cfg["api_key"]:
        print("ERROR: 缺少 DEEPSEEK_API_KEY。请设置环境变量或写入 .env 文件（参考 .env.example）。")
        return 1

    # ---- 缓存（仅本次重新抓取时才允许复用）----
    if data_mode == "fresh":
        cache_pv, cache_mh = load_cache(args.output_root, run_dir)
    else:
        cache_pv, cache_mh = None, {}

    # ---- Step 3 + 4：筛选 + 生成/复用卡片 ----
    output, problems = build_daily_brief(
        cfg, events_data, cache_pv, cache_mh, data_mode=data_mode, source_label=events_path
    )
    steps.append({"step": "筛选+卡片", "status": output["selection"]["status"],
                  "detail": output["selection"]["message"]})

    daily_path = os.path.join(run_dir, "daily_brief.json")
    with open(daily_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # ---- Step 5：HTML ----
    render_data = dict(output)
    render_data["articles"] = events_data.get("articles", [])
    page = render_daily_brief.render(render_data)
    html_path = os.path.join(run_dir, "daily_brief.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(page)

    elapsed = time.time() - t0
    sel = output.get("selection", {})
    ok = sel.get("status") == "ok" and not problems
    error = None
    if not ok:
        error = sel.get("message") if sel.get("status") == "failed" else "; ".join(problems)
    write_manifest(run_dir, beijing_ts, data_mode, steps, ok=ok, error=error,
                   elapsed=elapsed, usage=usage_summary(),
                   window=(events_data.get("window_start"), events_data.get("window_end")))

    # ---- 报告 ----
    print()
    print("=" * 64)
    print(f"运行目录: {run_dir}")
    print(f"数据模式: {'本次重新抓取' if data_mode == 'fresh' else '历史数据（未重新抓取）'}")
    print(f"采集窗口: {to_beijing_str(events_data.get('window_start'))} ～ "
          f"{to_beijing_str(events_data.get('window_end'))}（北京时间）")
    src_ok = sum(1 for s in events_data.get("sources", []) if s["status"] == "ok")
    src_err = sum(1 for s in events_data.get("sources", []) if s["status"] == "error")
    print(f"来源: {src_ok} 成功 / {src_err} 失败")
    for s in events_data.get("sources", []):
        if s.get("status") == "ok":
            tr = "，已截断" if s.get("truncated") else ""
            nt = f"，无发布时间剔除 {s.get('no_time', 0)}" if s.get("no_time") else ""
            print(f"  [{s.get('name', s.get('url'))}] 抓取 {s.get('fetched', 0)} · "
                  f"窗口内 {s.get('in_window', 0)} · 入选 {s.get('selected', 0)}{tr}{nt}")
        else:
            print(f"  [{s.get('name') or s.get('url')}] 失败: {s.get('error')}")
    g = events_data.get("grouping", {})
    if g.get("status") == "fallback":
        print(f"归组: 失败（{g.get('message')}）—— 已退回逐条展示，本次无多来源事件。")
    else:
        print(f"归组: {g.get('status')} — {g.get('message')}")
    if sel.get("status") == "failed":
        print(f"筛选失败: {sel.get('message')}")
        print("本次未生成卡片，不冒充成功结果。")
    else:
        print(f"候选 {sel.get('candidate_count')} 个 · 入选 {sel.get('selected_count')} 个")
        for e in output["events"]:
            tag = "复用" if e["reused"] else "新生成"
            srcs = e.get("source_count", 0)
            print(f"  {e['title_zh']}  ·  {e['title_en']}  ({srcs} 来源 · {tag})")
    if problems:
        print("程序检查发现问题:")
        for p in problems:
            print(f"  - {p}")
    u = usage_summary()
    if u.get("calls"):
        print(f"API 用量: {u['calls']} 次调用 · prompt {u['prompt_tokens']} · "
              f"completion {u['completion_tokens']} · total {u['total_tokens']} tokens")
    else:
        print("API 用量: 响应未返回 usage 字段，未估算。")
    print(f"总耗时: {elapsed:.1f} 秒")
    print(f"阅读页面: {html_path}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
