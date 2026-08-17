# 微信读书金句素材库（WeRead Golden Lines）

> 把你在微信读书里「读到的好句子」变成可复用的**口播/文案金句弹药库**。
> 自动采集书架书籍的**公开热门划线**与**你的个人划线** → 按书籍类型归档 → 写文案时按主题智能插入匹配的 ≥3 条金句，提升深度与质感。

出品 / 维护：**孔不惑AIko**　联系方式：`微信公众号：孔不惑AIko ｜ 抖音：孔不惑AIko ｜ 微信个人号：sydm628`（fork 后请替换为你的）

---

## ✨ 功能特性

- **一键采集**：对接微信读书，拉取书架全部电子书的公开热门划线（读者共识金句）+ 你的个人划线。
- **自动归类**：按书籍一级分类（个人成长 / 经济理财 / 心理 / 科技 / …）归档，自动打关键词标签。
- **智能插入**：写口播稿 / 公众号 / 短视频文案时，按「主题关键词 + 分类命中 + 热度」打分，筛选与语境匹配的金句，分布插入到钩子后 / 中段 / 结尾前，**保证 ≥3 条**。
- **稿件模板**：用 frontmatter 写明「主题 / 分类」，匹配精度再提一截。
- **增量同步**：反复运行只追加新书 / 新划线，不覆盖历史。
- **开源可分享**：配置与本地数据分离，开箱即用地给别人用。

## 🚀 快速开始

### 1. 准备运行环境（Python 3）
```bash
# 可选但推荐：中文分词，提升匹配精度（缺失时自动降级，不影响运行）
pip install jieba
```

### 2. 配置微信读书 Key
复制配置模板并填入你的 Key（`wrk-xxxx`，从微信读书获取）：
```bash
cp config.example.json config.json
# 编辑 config.json，把 api_key 换成你的
```
> 也可不改文件，直接用环境变量：`export WEREAD_API_KEY=wrk-你的key`（优先级更高）。
> ⚠️ `config.json` 含你的私有 Key，**已被 .gitignore 忽略，切勿提交到公开仓库**。

### 3. 采集金句到本地知识库
```bash
python scripts/collect.py
# 产出：<kb_dir>/golden_lines.json + 金句素材库.md + meta.json
```

### 4. 给稿件插金句
```bash
python scripts/insert.py --manuscript 你的稿.md --out 增强稿.md --min 3 --max 5
```
或直接用本仓库的 `templates/口播稿模板.md` 起稿（顶部写 `主题` / `分类` 更强匹配）。

## ⚙️ 配置项（config.json）

| 字段 | 说明 | 默认 |
|------|------|------|
| `api_key` | 微信读书 Key（或环境变量 `WRKB_API_KEY`） | 必填 |
| `gateway` | 接口网关地址 | 官方地址 |
| `skill_version` | 接口版本号 | 1.0.4 |
| `kb_dir` | 知识库目录（可指向 Obsidian 素材库等） | `./knowledge_base` |
| `min_insert` | 最少插入条数 | 3 |
| `author_contact` | 分享时署名/联系方式（开源署名用） | 选填 |

## 📁 目录结构

```
微信读书金句素材库/
├── SKILL.md                 # skill 定义（触发/工作流）
├── README.md                # 本文件
├── LICENSE                  # MIT
├── config.example.json      # 配置模板（复制为 config.json 后填写）
├── .gitignore
├── references/              # 接口/知识库/插入算法详解
│   ├── collect.md
│   ├── knowledge_base.md
│   ├── insert.md
│   └── recommended_books.md # 推荐补书单（填补主题缺口）
├── scripts/
│   ├── collect.py           # 采集
│   └── insert.py            # 插入
└── templates/
    └── 口播稿模板.md         # 带 frontmatter 的稿件模板
```

## 🧠 金句分类说明

分类直接来自书籍 `category` 的一级（如 `个人成长-励志成长` → `个人成长`）。
想让某类主题（如 AI）单独成库，可在 `insert.py` 的 `THEME_LEXICON` 增加触发词，
或在 `collect.py` 的 `split_category` 后加一层映射。

## 🤝 开源 / 分享

- 本 skill 采用 **MIT 许可证**，可自由 fork、修改、再分发。
- 分享时请保留 `LICENSE` 与署名；`config.json`（含你的 Key）与 `knowledge_base/`（你的私有数据）已被 `.gitignore` 排除，不会泄露。
- 欢迎提 PR 改进匹配算法、扩展有声书采集、支持更多笔记源。

---

出品：孔不惑AIko　·　`微信公众号：孔不惑AIko ｜ 抖音：孔不惑AIko ｜ 微信个人号：sydm628`
