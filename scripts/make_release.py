#!/usr/bin/env python3
"""
BookwormPRO 发布打包脚本
生成干净的 ZIP 发布包，供分发给用户
"""

import shutil, zipfile, os, sys
from pathlib import Path

SRC = Path(__file__).parent.parent
RELEASE_DIR = SRC / 'release'
VERSION = '1.0.0'

# ── 排除列表 ──
EXCLUDE = {
    '.git', '.gitignore', '.gitattributes',
    '__pycache__', '*.pyc', '*.pyo',
    '.DS_Store', '.vscode', '.idea',
    'node_modules',
    'release',  # 不要把自己打包进去
}

def should_exclude(path):
    name = path.name
    for pattern in EXCLUDE:
        if '*' in pattern:
            if name.endswith(pattern[1:]):
                return True
        elif name == pattern:
            return True
    return False

def make_release():
    print(f"📦 BookwormPRO v{VERSION} 发布打包\n")
    
    # 清理
    if RELEASE_DIR.exists():
        shutil.rmtree(RELEASE_DIR)
    RELEASE_DIR.mkdir()
    
    # 复制文件
    zip_name = f'bookwormpro-sale-v{VERSION}.zip'
    zip_path = RELEASE_DIR / zip_name
    
    total = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in SRC.rglob('*'):
            if should_exclude(f) or f.is_dir():
                continue
            rel = f.relative_to(SRC)
            # 显示进度
            if total % 200 == 0 and total > 0:
                print(f"\r  打包中... {total} 个文件", end='', flush=True)
            zf.write(f, rel)
            total += 1
    
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"\r  ✅ 完成: {total} 个文件, {size_mb:.1f} MB\n")
    print(f"  发布包: {zip_path}")
    print(f"  文件名: {zip_name}")
    
    # 生成校验
    import hashlib
    sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()[:16]
    print(f"  SHA256: {sha}...")
    
    # 生成版本信息
    info = RELEASE_DIR / 'VERSION.txt'
    info.write_text(f"""BookwormPRO v{VERSION}
发布日期: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}
文件: {zip_name}
大小: {size_mb:.1f} MB
文件数: {total}
SHA256: {sha}
""")
    print(f"  版本信息: {info}")
    
    print(f"\n{'='*60}")
    print(f"  发布就绪！将 {zip_name} 上传到 GitHub Releases")
    print(f"{'='*60}")

if __name__ == '__main__':
    make_release()
