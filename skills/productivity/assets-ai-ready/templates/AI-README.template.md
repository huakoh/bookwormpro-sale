# AI-README — <asset_library_path>

> **如果你是 AI 助手，这是你的操作手册。**
> 版本：YYYY-MM-DD | N 文件 | X GB

---

## 核心检索路径

```
用户问 → 推荐命中? → 直接返回路径
        ↓ 否
        FTS5 搜索 .search.db
        ↓
        读对应 .assets.json 看描述
        ↓
        必要时 Read 具体文件
```

## 快捷入口（recommended_picks）

| 用户怎么说 | 直接返回 |
|------------|----------|
<!-- INSERT RECOMMENDED PICKS -->

完整清单见 `.manifest.json` → `recommended_picks`。

## FTS5 全文搜索

```python
import sqlite3
db = sqlite3.connect('<root>/.search.db')
# 关键词搜索（空格 = AND）
db.execute("SELECT path FROM fts WHERE fts MATCH 'brochure vaccine'").fetchall()
# 带上下文摘要
db.execute("SELECT path, snippet(fts,1,'**','**','...',40) FROM fts WHERE fts MATCH ?", (query,)).fetchall()
```

数据库字段: `path, title, summary, tags, filename, body`（FTS5 unicode61 分词）

## .assets.json 结构

每个叶子目录有 `.assets.json`，包含：
- `purpose` — 目录用途
- `search_hints.common_queries` — 用户常用问法
- `assets[].description` — 每张图的详细描述
- `assets[].tags` — 英文标签
- `assets[].source_file` — 源文件引用
- `assets[].license` — `internal-only` 全员内部使用

## 目录地图

```
<!-- INSERT DIRECTORY MAP -->
```

## 项目归属

| 项目 | project 字段 | 说明 |
|------|-------------|------|
<!-- INSERT PROJECT TABLE -->

## 文件命名规范

```
<project>_{category}_{subject}_{variant?}_{size?}.{ext}
```

全小写、下划线分字段、短横线分词、无空格无中文。

## 约束

- **不要全库扫图** — 优先读 `.assets.json` 的文字描述
- **源文件不可直接交付** — `_sources/psd|psb|tif` 需原工具导出
- **web/ 子目录** — 同文件的压缩版，适合 Web
- **OCR 文本** — 图片和 PDF 的 OCR 结果已缓存到 `_cache/text/`

## 维护脚本

| 脚本 | 用途 |
|------|------|
| `_scripts/enrich_manifest.py` | 扫描文件重建 .manifest.json |
| `_scripts/build_search_index.py` | 重建 .search.db FTS5 索引 |
| `_scripts/refresh-manifest.py` | 增量刷新 file_count |
| `_scripts/validate-naming.ps1` | 命名合规检查 |
| `_scripts/inject_ai_meta.py` | 注入 ai_guidance/projects_map/recommended_picks |

## 关联资产库

| 库 | 路径 | 内容 |
|----|------|------|
| <!-- INSERT CROSS-LIBRARY LINKS -->

> 当用户需要的资料不在本库时，查关联库的 MANIFEST 或 AI-README。
