# knowledge_base.md — 本地知识库结构

知识库默认落在 `config.json` 的 `kb_dir`（默认指向 Obsidian `02-创作素材库/微信读书金句库`，可直接进你的素材库体系）。可自行改指向任意本地目录。

## 目录产出

```
kb_dir/
├── golden_lines.json   # 机器可读全量金句（insert.py 读取此文件）
├── 金句素材库.md        # 人读索引，按「金句分类」分组陈列
└── meta.json           # 元信息：同步时间 / 书本数 / 条数 / 来源占比
```

## golden_lines.json 条目结构

```json
{
  "id": "a1b2c3d4e5f6",
  "text": "所以，相信相信的力量。",
  "book": "相信",
  "author": "蔡磊",
  "bookId": "3300054149",
  "topCategory": "个人成长",
  "subCategory": "励志成长",
  "category": "个人成长-励志成长",
  "source": "popular",
  "popularity": 9104,
  "chapter": "第 54 章《第九章 倒下之前的N件事》",
  "range": "13945-13980",
  "tags": ["相信", "力量", "努力", "希望"],
  "addedAt": "2026-08-17"
}
```

字段说明：
- `topCategory`：**金句分类**（书籍一级分类），是素材库的主要归档维度。
- `source`：`popular`=公域热门划线；`personal`=你自己的划线。
- `popularity`：公域划线人数，衡量「共鸣强度」，插入打分时的微加权因子。
- `tags`：自动关键词，供插入时主题匹配。

## 金句分类（taxonomy）

分类直接来自书籍 `category` 的一级，例如：
`个人成长` / `经济理财` / `心理` / `哲学宗教` / `文学` ……
首次采集后，`金句素材库.md` 会按这些分类自动分组，方便你按题材挑金句。

## 维护

- 增量同步：重跑 `collect.py` 即可，只追加新书/新划线。
- 个人划线：当你在微信读书里真划了线，重跑后会并入 `personal` 来源。
