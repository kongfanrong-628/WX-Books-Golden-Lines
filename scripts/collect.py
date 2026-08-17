#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信读书金句素材库 · 采集脚本 (collect.py)
功能：
  1. 对接微信读书 gateway，拉取用户书架全部电子书
  2. 对每本书抓取「公开热门划线」(bestbookmarks) 与「个人划线」(bookmarklist)
  3. 按书籍类型(一级分类)归纳，自动生成关键词标签
  4. 去重后写入本地知识库 (JSON + Markdown 索引)
依赖：标准库 + 可选 jieba（用于标签/分词，缺失时自动降级）
"""
import os, sys, json, hashlib, datetime, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")

try:
    import jieba.analyse
    _HAS_JIEBA = True
except Exception:
    _HAS_JIEBA = False


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    # 环境变量优先
    env_key = os.environ.get("WRKB_API_KEY")
    if env_key:
        cfg["api_key"] = env_key
    return cfg


def api_call(cfg, api_name, **params):
    body = {"api_name": api_name, "skill_version": cfg.get("skill_version", "1.0.4")}
    body.update(params)
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        cfg["gateway"], data=data,
        headers={"Authorization": "Bearer " + cfg["api_key"],
                 "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def chapter_map(chapters):
    return {c.get("chapterUid"): c.get("title", "") for c in (chapters or [])}


def split_category(cat):
    if not cat:
        return ("未分类", "")
    parts = cat.split("-", 1)
    return (parts[0].strip(), parts[1].strip() if len(parts) > 1 else "")


def make_tags(text):
    text = (text or "").strip()
    if not text:
        return []
    if _HAS_JIEBA:
        try:
            tags = jieba.analyse.extract_tags(text, topK=6, withWeight=False)
            return [t for t in tags if len(t) >= 2]
        except Exception:
            pass
    # 降级：CJK 二元组 + 英文词
    import re
    tags = set()
    for m in re.finditer(r"[\u4e00-\u9fff]{2,4}", text):
        tags.add(m.group(0))
    for m in re.finditer(r"[A-Za-z]{3,}", text):
        tags.add(m.group(0).lower())
    return list(tags)[:6]


def uid(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def get_shelf_books(cfg):
    data = api_call(cfg, "/shelf/sync")
    books = []
    for b in data.get("books", []):
        cat = b.get("category", "")
        top, sub = split_category(cat)
        books.append({
            "bookId": b.get("bookId"),
            "title": b.get("title", ""),
            "author": b.get("author", ""),
            "category": cat, "topCategory": top, "subCategory": sub,
        })
    albums = data.get("albums", [])
    if albums:
        print(f"  [提示] 书架含 {len(albums)} 个有声书/专辑，本次仅采集电子书金句（如需有声书稿可后续扩展）。")
    return books


def collect_book(cfg, book):
    bid = book["bookId"]
    entries = []
    # 1) 公开热门划线
    try:
        bb = api_call(cfg, "/book/bestbookmarks", bookId=bid, chapterUid=0)
        cmap = chapter_map(bb.get("chapters", []))
        for it in bb.get("items", []):
            txt = (it.get("markText") or "").strip()
            if not txt:
                continue
            cu = it.get("chapterUid")
            entries.append({
                "id": uid(txt),
                "text": txt,
                "book": book["title"], "author": book["author"], "bookId": bid,
                "topCategory": book["topCategory"], "subCategory": book["subCategory"],
                "category": book["category"],
                "source": "popular",
                "popularity": it.get("totalCount", 0),
                "chapter": cmap.get(cu, f"第{cu}章"),
                "range": it.get("range", ""),
                "tags": make_tags(txt),
                "addedAt": datetime.date.today().isoformat(),
            })
    except Exception as e:
        print(f"  [warn] {book['title']} 热门划线失败: {e}")
    # 2) 个人划线
    try:
        bl = api_call(cfg, "/book/bookmarklist", bookId=bid)
        cmap = chapter_map(bl.get("chapters", []))
        for it in bl.get("updated", []):
            txt = (it.get("markText") or "").strip()
            if not txt:
                continue
            cu = it.get("chapterUid")
            entries.append({
                "id": uid(txt),
                "text": txt,
                "book": book["title"], "author": book["author"], "bookId": bid,
                "topCategory": book["topCategory"], "subCategory": book["subCategory"],
                "category": book["category"],
                "source": "personal",
                "popularity": None,
                "chapter": cmap.get(cu, f"第{cu}章"),
                "range": it.get("range", ""),
                "tags": make_tags(txt),
                "addedAt": datetime.date.today().isoformat(),
            })
    except Exception as e:
        print(f"  [warn] {book['title']} 个人划线失败: {e}")
    return entries


def load_existing(kb_dir):
    path = os.path.join(kb_dir, "golden_lines.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_kb(kb_dir, entries, author_contact=None):
    os.makedirs(kb_dir, exist_ok=True)
    # 去重合并
    existing = load_existing(kb_dir)
    seen = {e["id"] for e in existing}
    added = 0
    for e in entries:
        if e["id"] not in seen:
            existing.append(e)
            seen.add(e["id"])
            added += 1
    # 保存 JSON
    with open(os.path.join(kb_dir, "golden_lines.json"), "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    # 保存 Markdown 索引
    write_md_index(kb_dir, existing, author_contact)
    # 元信息
    meta = {
        "lastSync": datetime.datetime.now().isoformat(timespec="seconds"),
        "bookCount": len({e["bookId"] for e in existing}),
        "lineCount": len(existing),
        "popularCount": sum(1 for e in existing if e["source"] == "popular"),
        "personalCount": sum(1 for e in existing if e["source"] == "personal"),
    }
    with open(os.path.join(kb_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return added, meta


def write_md_index(kb_dir, entries, author_contact=None):
    groups = {}
    for e in entries:
        groups.setdefault(e["topCategory"], []).append(e)
    lines = ["# 微信读书金句素材库", ""]
    lines.append(f"> 共 {len(entries)} 条金句 · 覆盖 {len(groups)} 个分类 · 由 collect.py 自动归类生成")
    if author_contact and not author_contact.startswith("在此填写"):
        lines.append(f"> 出品 / 整理：{author_contact}")
    lines.append("")
    lines.append("> 用法：写口播稿时用 insert.py 按主题智能插入；或直接在下方按分类挑金句。")
    lines.append("")
    for cat in sorted(groups.keys()):
        items = groups[cat]
        lines.append(f"## 📚 {cat}（{len(items)} 条）")
        lines.append("")
        # 按热度/个人排序
        items_sorted = sorted(items, key=lambda x: (x["popularity"] or 0), reverse=True)
        for it in items_sorted:
            src = f"🔥{it['popularity']}人" if it["source"] == "popular" else "✍️个人"
            lines.append(f"- {it['text']}  \n  └─ 《{it['book']}》{it['author']} · {src} · {it['chapter']}")
        lines.append("")
    with open(os.path.join(kb_dir, "金句素材库.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    cfg = load_config()
    api_key = cfg.get("api_key", "")
    if not api_key or api_key.startswith("在此填入"):
        print("✗ 未配置微信读书 Key。请复制 config.example.json 为 config.json 并填入 api_key，")
        print("  或设置环境变量 WRKB_API_KEY=wrk-你的key 后重试。")
        sys.exit(1)
    kb_dir = cfg["kb_dir"]
    print("=== 微信读书金句素材库 · 采集开始 ===")
    print(f"知识库目录: {kb_dir}")
    books = get_shelf_books(cfg)
    print(f"书架电子书: {len(books)} 本")
    all_entries = []
    for i, b in enumerate(books, 1):
        print(f"  [{i}/{len(books)}] 采集《{b['title']}》[{b['topCategory']}] ...", end=" ")
        es = collect_book(cfg, b)
        print(f"{len(es)} 条")
        all_entries.extend(es)
    added, meta = save_kb(kb_dir, all_entries, cfg.get("author_contact"))
    print("=== 采集完成 ===")
    print(f"本次新增: {added} 条 | 知识库总计: {meta['lineCount']} 条 "
          f"(热门 {meta['popularCount']} / 个人 {meta['personalCount']}) | 覆盖 {meta['bookCount']} 本书")


if __name__ == "__main__":
    main()
