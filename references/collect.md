# collect.md — 采集接口与参数

微信读书金句素材库通过 **Agent API Gateway** 对接微信读书，与 `weread-skills` 同源。

## 统一入口

```
POST https://i.weread.qq.com/api/agent/gateway
Authorization: Bearer $WEREAD_API_KEY
Content-Type: application/json
```

每次请求 body 必须带 `skill_version`（见 `config.json`）。若回包出现 `upgrade_info`，按提示升级 `weread-skills` 后重跑。

## 采集流程用到的接口

### 1. `/shelf/sync` — 书架
- 参数：无（身份由 key 绑定）
- 回包关键字段：`books[].bookId / title / author / category / readUpdateTime`
- **数量口径**：电子书 = `books[]`；有声书/专辑在 `albums[]`（本 skill 默认只采集电子书金句，有声书如需可扩展）。
- `category` 形如 `个人成长-励志成长`，用 `-` 切分得到一级分类（`topCategory`=个人成长）作为**金句分类**。

### 2. `/book/bestbookmarks` — 公开热门划线（公域共鸣点）
- 参数：`bookId`（必填）、`chapterUid`（默认 0=全书）
- 回包：`items[]`（markText 原文、totalCount 划线人数、chapterUid、range）；`chapters[]` 映射到章节标题。
- 服务端固定返回前 20 条，按热度排序，**不支持分页**。
- 注意：这是**别人划得最多的段落**，不是你的笔记。

### 3. `/book/bookmarklist` — 个人划线
- 参数：`bookId`
- 回包：`updated[]`（markText、chapterUid、range、createTime）；自动过滤书签(type=0)，只返回划线(type=1)。
- 你当前若尚未划线，返回为空，脚本照常处理（不报错）。

## 字段映射与归类

每条金句 entry：
- `id` = `md5(markText)[:12]`（去重主键，跨次采集幂等）
- `topCategory` / `subCategory` = 书籍 `category` 按 `-` 拆分
- `source` = `popular`（热门）| `personal`（个人）
- `popularity` = 热门划线人数（个人划线为 null）
- `tags` = 关键词标签（jieba.extract_tags，缺失时降级为 CJK 2-4 字片段）
- `chapter` / `range` = 处码（定位用，因 bestbookmarks 不返 deepLink，无法一键跳转）

## 去重与合并

`collect.py` 读取已有 `golden_lines.json`，按 `id` 合并，**只追加新增**，可反复运行（如读完新书后增量同步）。
