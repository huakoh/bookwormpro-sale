---

name: asset-library-organization

category: 系统工具

description: >

  Professional organization of asset libraries and archives for AI retrieval.

  Use when user asks to organize files, archive folders, build searchable asset

  libraries, create AI-readable manifests, or set up FTS5+OCR indexes.

  Covers _Archive monthly bucket system and ~/assets visual media library.

trigger_keywords: [archive, organize, assets, 整理, 归档, 资产库, FTS5, OCR]

---




# Asset Library Organization





## Prerequisites


- Windows: use `python` not `python3` (python3 exit 49)


- `patch` fails on CJK .md → use `write_file` or `sed -i`


- System sqlite3 may lack FTS5 → use Python sqlite3 module





## Archive Pattern (~/Desktop/_Archive)





### Structure


```


_Archive/


  README.md              # rules + SOP + cross-refs


  YYYY-MM/


    MANIFEST.md           # monthly index


    ClaudeSecure/ Docs/ HTMLs/ Images/ Misc/ PDFs/ Reports/ Scripts/


```





### SOP (per month)


1. `mkdir -p YYYY-MM/{Docs,HTMLs,Images,Misc,PDFs,Reports,Scripts,ClaudeSecure}`


2. Sort desktop files by type into categories


3. Project files stay together (don't split across type dirs)


4. `find . -type d -empty -delete`


5. Generate MANIFEST.md with file list + sizes + dates


6. Git commit: `cd ~/Desktop/_Archive && git add -A && git commit -m "..." && git push`





### Naming: `{topic}_{version}.{ext}` or `YYYY-MM-DD_{topic}.{ext}`


### Sensitive: GPG encrypt configs (`gpg -c file`, delete plaintext)


### .gitignore: *.png *.jpg *.pdf *.docx *.xlsx *.zip *.gpg *.exe





## Assets Library Pattern (~/assets)





### Core files


- `.manifest.json` — root manifest (schema v2, files array + ai_guidance + projects_map + recommended_picks)


- `.search.db` — SQLite FTS5 index


- `AI-README.md` — AI retrieval guide


- `*/.assets.json` — per-directory manifest with descriptions





### Search


```python


import sqlite3


db = sqlite3.connect('~/assets/.search.db')


db.execute("SELECT path FROM fts WHERE fts MATCH 'keyword'").fetchall()


```





### OCR


```bash


pip install rapidocr-onnxruntime


python _scripts/build_search_index.py --force-ocr


```





### PDF compress (no Ghostscript needed)


```bash


pip install pikepdf


python _scripts/compress-pdfs.py


```





### Maintenance scripts in `_scripts/`:


- `enrich_manifest.py` — rebuild .manifest.json


- `build_search_index.py` — rebuild .search.db FTS5


- `refresh-manifest.py` — incremental file_count update


- `compress-pdfs.py` — pikepdf web copies


- `search-assets.py` — unified search (assets + archive)


- `inject_ai_meta.py` — add ai_guidance to manifest





### WebP conversion for images


```python


from PIL import Image


img = Image.open(src)


img.save(dst, 'webp', quality=85)  # typically 60-92% reduction


```


