#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信读书金句素材库 · 插入脚本 (insert.py)
功能：
  读取口播/文案稿件 + 本地金句知识库，按「主题 / 关键词 / 书籍分类」匹配度打分，
  筛选与文案主题语境匹配的金句，分布插入到稿件合适位置（钩子后 / 中段 / 结尾前），
  输出增强稿 + 插入报告。默认保证插入 >= min_insert(3) 条。
依赖：标准库 + 可选 jieba（中文分词，缺失时二元组降级）
"""
import os, sys, json, re, argparse, math

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)

try:
    import jieba
    import jieba.analyse
    jieba.setLogLevel(20)
    _HAS_JIEBA = True
except Exception:
    _HAS_JIEBA = False

# 主题词 -> 金句分类 的映射词典，弥补「稿件里没直接写分类名」导致的主题漏判
THEME_LEXICON = {
    "经济理财": ["财富", "杠杆", "复利", "赚钱", "收入", "投资", "资产", "财务", "生意",
              "股权", "被动收入", "理财", "自由", "钱", "资本"],
    "心理": ["习惯", "行为", "动机", "情绪", "心理", "焦虑", "自律", "欲望", "幸福",
            "拖延", "专注"],
    "个人成长": ["成长", "学习", "目标", "效率", "精进", "认知", "提升", "复盘"],
    "哲学宗教": ["谋略", "纵横", "人性", "智慧", "格局", "权谋", "处世", "心法"],
    "沟通表达": ["沟通", "表达", "说服", "逻辑", "金字塔", "汇报", "演讲", "写作"],
}


def load_kb(kb_arg):
    # kb_arg: 目录 或 golden_lines.json 路径
    if os.path.isdir(kb_arg):
        p = os.path.join(kb_arg, "golden_lines.json")
    else:
        p = kb_arg
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def tokenize(text):
    text = text or ""
    if _HAS_JIEBA:
        toks = [t for t in jieba.lcut(text) if len(t) >= 2 and not re.fullmatch(r"[\s\W]+", t)]
        return toks
    # 降级：CJK 二元组 + 英文词
    toks = []
    for m in re.finditer(r"[\u4e00-\u9fff]{2,}", text):
        s = m.group(0)
        for i in range(len(s) - 1):
            toks.append(s[i:i+2])
    for m in re.finditer(r"[A-Za-z]{3,}", text):
        toks.append(m.group(0).lower())
    return toks


def score_entry(entry, ms_tokens, ms_text_lower, ms_categories):
    """返回 (score, matched_keywords, category_match)"""
    score = 0.0
    matched = set()
    etext = (entry.get("text") or "").lower()
    etags = " ".join(entry.get("tags") or []).lower()
    ebook = (entry.get("book") or "").lower()
    ecat = (entry.get("category") or "").lower()
    # 关键词重叠（短语越长权重越高）
    for kw in ms_tokens:
        if len(kw) < 2:
            continue
        if kw in etext or kw in etags or kw in ebook or kw in ecat:
            w = len(kw)
            score += w
            matched.add(kw)
    # 分类/主题匹配（强信号）
    cat_match = False
    for c in ms_categories:
        if c and (c in (entry.get("topCategory") or "") or c in ecat or c in etext):
            score += 6
            cat_match = True
            matched.add("分类:" + c)
    # 热度微加权（公域共鸣）
    pop = entry.get("popularity") or 0
    if pop:
        score += math.log10(pop + 1) * 0.4
    return score, matched, cat_match


def parse_frontmatter(text):
    """解析稿件顶部 --- 包裹的 YAML 风格 frontmatter，返回 (meta_dict, body_text)。
    meta 含 主题 / 分类（可选）。无 frontmatter 时返回 ({}, text)。"""
    meta = {}
    body = text
    m = re.match(r"^\s*---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if m:
        fm = m.group(1)
        body = text[m.end():]
        for line in fm.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    return meta, body


def detect_categories(ms_text, all_topcats):
    """从稿件文本里猜测涉及的书籍分类，作为主题信号。
    同时用分类名直接命中 + 主题词典触发，提升召回。"""
    found = []
    for c in all_topcats:
        if c and c in ms_text:
            found.append(c)
    # 主题词典触发（仅当该分类确实存在于知识库中）
    for cat, triggers in THEME_LEXICON.items():
        if cat in all_topcats and cat not in found:
            if any(t in ms_text for t in triggers):
                found.append(cat)
    return found


def manuscript_keywords(ms_text):
    """提取稿件显著关键词（TF-IDF），过滤泛词，提升主题匹配精度。
    无 jieba 时降级为 CJK 2-4 字片段 + 英文词。"""
    if _HAS_JIEBA:
        kws = jieba.analyse.extract_tags(ms_text, topK=15, withWeight=False)
        return [k for k in kws if len(k) >= 2]
    return tokenize(ms_text)


def pick_entries(entries, ms_tokens, ms_text, ms_categories, min_n, max_n):
    scored = []
    for e in entries:
        s, m, cm = score_entry(e, ms_tokens, ms_text.lower(), ms_categories)
        scored.append((s, m, cm, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    relevant = [x for x in scored if x[0] > 0]
    # 多样性：每本书最多取 2 条
    chosen = []
    per_book = {}
    for x in relevant:
        e = x[3]
        bid = e.get("bookId")
        if per_book.get(bid, 0) >= 2:
            continue
        chosen.append(x)
        per_book[bid] = per_book.get(bid, 0) + 1
        if len(chosen) >= max_n:
            break
    # 保底：不足 min_n 则放宽（弱匹配），按热度/分类就近补
    if len(chosen) < min_n:
        used_ids = {x[3]["id"] for x in chosen}
        for x in scored:
            if len(chosen) >= min_n:
                break
            e = x[3]
            if e["id"] in used_ids:
                continue
            bid = e.get("bookId")
            if per_book.get(bid, 0) >= 2 and len(chosen) >= min_n:
                continue
            if per_book.get(bid, 0) >= 3:
                continue
            chosen.append(x)
            used_ids.add(e["id"])
            per_book[bid] = per_book.get(bid, 0) + 1
    # 重新按分数排序，标记置信度
    chosen.sort(key=lambda x: x[0], reverse=True)
    result = []
    for s, m, cm, e in chosen:
        if s > 0:
            conf = "高" if (cm and s >= 8) else ("中" if s >= 4 else "低")
        else:
            conf = "保底(弱匹配)"
        result.append({"entry": e, "score": round(s, 1), "matched": list(m), "conf": conf})
    return result


def split_paragraphs(text):
    # 以空行分段；若无空行则按单换行
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) <= 1:
        blocks = [b.strip() for b in text.splitlines() if b.strip()]
    return blocks


def insert_positions(n_paras):
    """返回要插入金句段的索引位置（在对应段之后插入）"""
    if n_paras <= 1:
        return [0]
    if n_paras == 2:
        return [0, 1]  # 第一段后、结尾前
    if n_paras == 3:
        return [0, 1, 2]
    # >=4：钩子后、中段、结尾前，外加均匀分布
    pos = set()
    pos.add(max(0, int(n_paras * 0.25)))
    pos.add(max(0, int(n_paras * 0.5)))
    pos.add(n_paras - 1)  # 结尾前
    return sorted(pos)


def build_enhanced(paragraphs, picks, min_n):
    # 取前 min(max_n, len(picks)) 个，按插入位置分配
    n = min(len(picks), max(min_n, 3))
    n = min(n, len(picks))
    positions = insert_positions(len(paragraphs))
    # 选择 n 个插入点（尽量均匀，至少 n 个）
    chosen_pos = positions[:]
    # 若插入点少于需要，补充中间段
    idx = 1
    while len(chosen_pos) < n and idx < len(paragraphs):
        if idx not in chosen_pos:
            chosen_pos.append(idx)
        idx += 1
    chosen_pos = sorted(set(chosen_pos))[:n]

    out = []
    insertions = []
    for pi, para in enumerate(paragraphs):
        out.append(para)
        if pi in chosen_pos and picks:
            pick = picks.pop(0)
            e = pick["entry"]
            block = (f"> 💡 「{e['text']}」\n> —— 《{e['book']}》{e['author']} "
                     f"[{e['topCategory']}·{'热门' if e['source']=='popular' else '个人'}]")
            out.append(block)
            insertions.append((pi, pick))
    return "\n\n".join(out), insertions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manuscript", required=True, help="口播稿路径(.md/.txt) 或 - 表示从 stdin")
    ap.add_argument("--kb", default=os.path.join(SKILL_DIR, "..", "微信读书金句素材库"),
                    help="知识库目录或 golden_lines.json 路径")
    ap.add_argument("--out", default=None, help="增强稿输出路径，默认在原文件名后加 _with_golden")
    ap.add_argument("--min", type=int, default=3, help="最少插入条数(默认3)")
    ap.add_argument("--max", type=int, default=5, help="最多插入条数(默认5)")
    args = ap.parse_args()

    if args.manuscript == "-":
        raw = sys.stdin.read()
    else:
        with open(args.manuscript, encoding="utf-8") as f:
            raw = f.read()

    meta, ms_body = parse_frontmatter(raw)

    entries = load_kb(args.kb)
    all_topcats = {e.get("topCategory") for e in entries}
    ms_tokens = manuscript_keywords(ms_body)
    # 主题词作为强信号补充（frontmatter 中的「主题」）
    if meta.get("主题"):
        ms_tokens = ms_tokens + manuscript_keywords(meta["主题"])
    ms_categories = detect_categories(ms_body, all_topcats)
    # 分类强制锁定（若存在该分类，置顶优先）
    if meta.get("分类") and meta["分类"] in all_topcats:
        if meta["分类"] not in ms_categories:
            ms_categories.insert(0, meta["分类"])

    picks = pick_entries(entries, ms_tokens, ms_body, ms_categories, args.min, args.max)

    paragraphs = split_paragraphs(ms_body)
    enhanced, insertions = build_enhanced(paragraphs, picks, args.min)

    out_path = args.out
    if not out_path and args.manuscript != "-":
        base, ext = os.path.splitext(args.manuscript)
        out_path = base + "_with_golden" + (ext or ".md")
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(enhanced)

    # 报告
    print("=== 金句插入报告 ===")
    print(f"知识库金句总数: {len(entries)} | 稿件段落数: {len(paragraphs)}")
    fm_info = []
    if meta.get("主题"):
        fm_info.append(f"主题={meta['主题']}")
    if meta.get("分类"):
        fm_info.append(f"强制分类={meta['分类']}")
    if fm_info:
        print("Frontmatter: " + " | ".join(fm_info))
    print(f"检测到主题分类: {ms_categories if ms_categories else '(未直接命中分类，已按关键词匹配)'}")
    print(f"实际插入: {len(insertions)} 条（要求 >= {args.min}）")
    print("-" * 50)
    for i, (pos, pk) in enumerate(insertions, 1):
        e = pk["entry"]
        print(f"[{i}] 第 {pos+1} 段后 | 置信:{pk['conf']} | 分:{pk['score']}")
        print(f"     「{e['text']}」")
        print(f"     —— 《{e['book']}》{e['author']} [{e['topCategory']}]")
        if pk["matched"]:
            print(f"     命中: {', '.join(pk['matched'][:6])}")
    print("-" * 50)
    print(f"增强稿已写入: {out_path}")


if __name__ == "__main__":
    main()
