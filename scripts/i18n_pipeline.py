#!/usr/bin/env python3
"""
BookwormPRO 自动化 i18n 管道
=============================
Phase 1: 扫描 → Phase 2: 注入导入 → Phase 3: 冲突处理 → Phase 4: 提取 → Phase 5: 生成.po → Phase 6: 编译

用法: python scripts/i18n_pipeline.py [--dry-run] [--phase 1-6] [--target-dir bwm_cli/]
"""

import os
import re
import sys
import ast
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ─── 配置 ───────────────────────────────────────────────
PROJECT_ROOT = Path(r"C:\Users\leesu\BookwormPRO")
PO_PATH = PROJECT_ROOT / "locale" / "zh_CN" / "LC_MESSAGES" / "bookwormpro.po"
MO_PATH = PROJECT_ROOT / "locale" / "zh_CN" / "LC_MESSAGES" / "bookwormpro.mo"
COMPILE_SCRIPT = PROJECT_ROOT / "scripts" / "compile_i18n.py"

# 要扫描的目录
TARGET_DIRS = [
    PROJECT_ROOT / "bwm_cli",
    PROJECT_ROOT / "gateway",
    PROJECT_ROOT / "agent",
]

# 根目录下的独立 .py 文件
ROOT_FILES = [
    PROJECT_ROOT / "cli.py",
    PROJECT_ROOT / "run_agent.py",
    PROJECT_ROOT / "model_tools.py",
    PROJECT_ROOT / "batch_runner.py",
]

# 排除的文件
EXCLUDE_PATTERNS = [
    r"__init__\.py$",
    r"i18n\.py$",
    r"test_.*\.py$",
    r".*_test\.py$",
    r"setup\.py$",  # package setup, not BookwormPRO setup
]

# 输出函数模式（参数为面向用户的字符串）
OUTPUT_PATTERNS = [
    # 直接输出
    (r'\bprint\(', 'print'),
    (r'\bconsole\.print\(', 'console.print'),
    (r'\b_cprint\(', '_cprint'),
    (r'\b_console_print\(', '_console_print'),
    (r'\b_safe_print\(', '_safe_print'),
    (r'\b_vprint\(', '_vprint'),
    # 彩色输出
    (r'\bcolor\(', 'color'),
    # BookwormPRO 特定辅助函数
    (r'\bcheck_ok\(', 'check_ok'),
    (r'\bcheck_warn\(', 'check_warn'),
    (r'\bcheck_fail\(', 'check_fail'),
    (r'\bcheck_info\(', 'check_info'),
    (r'\b_notify\(', '_notify'),
    (r'\b_notify_error\(', '_notify_error'),
    # Rich
    (r'\brprint\(', 'rprint'),
]

# 这些辅助函数会自动对首个参数调用 _()，所以它们的静态字符串参数会被翻译
AUTO_TRANSLATE_FUNCTIONS = {
    'check_ok', 'check_warn', 'check_fail', 'check_info',
    '_notify', '_notify_error', '_cprint', '_console_print',
    '_safe_print', '_vprint',
}

# ─── 工具函数 ───────────────────────────────────────────

def find_py_files():
    """查找所有需要处理的 .py 文件"""
    files = list(ROOT_FILES)
    for d in TARGET_DIRS:
        if d.exists():
            files.extend(d.rglob("*.py"))
    
    # 过滤排除项
    def excluded(p):
        p_str = str(p)
        for pat in EXCLUDE_PATTERNS:
            if re.search(pat, p_str):
                return True
        return False
    
    files = [f for f in files if f.exists() and not excluded(f)]
    return sorted(set(files))


def read_file_safe(path):
    """安全读取文件，处理编码和 CRLF"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        with open(path, 'r', encoding='latin-1') as f:
            return f.read()


def write_file_safe(path, content):
    """安全写入文件，保持原始行尾"""
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)


# ─── Phase 1: 扫描 ──────────────────────────────────────

def scan_file(filepath):
    """扫描文件，返回分析结果"""
    content = read_file_safe(filepath)
    lines = content.split('\n')
    
    result = {
        'path': str(filepath),
        'relative': str(filepath.relative_to(PROJECT_ROOT)),
        'lines': len(lines),
        'has_i18n_import': False,
        'has_underscore_conflict': False,
        'conflict_lines': [],
        'output_calls': 0,
        'fstring_output_calls': 0,
        'static_output_calls': 0,
        'static_strings': [],
        'functions_found': defaultdict(int),
    }
    
    # 检查 i18n 导入
    if re.search(r'from bwm_cli\.i18n import _', content):
        result['has_i18n_import'] = True
    
    # 检查 _ 变量冲突（作为抛弃变量使用）
    conflict_pattern = re.compile(r'^\s*(?:for\s+_[\s,]+|_\s*,\s*\w+\s*=|_\s*=\s*)', re.MULTILINE)
    for i, line in enumerate(lines, 1):
        if conflict_pattern.search(line):
            # 排除函数定义 (def _...)
            if re.match(r'\s*def\s+_', line):
                continue
            # 排除 import _ 语句
            if 'import _' in line or 'import _,' in line:
                continue
            result['has_underscore_conflict'] = True
            result['conflict_lines'].append((i, line.strip()))
    
    # 统计输出调用
    for pattern, func_name in OUTPUT_PATTERNS:
        matches = re.finditer(pattern, content)
        for m in matches:
            result['functions_found'][func_name] += 1
            result['output_calls'] += 1
            
            # 检查是否是 f-string
            # 找到匹配后的字符串参数
            post_match = content[m.end():m.end()+200]
            if re.match(r'\s*f["\']', post_match):
                result['fstring_output_calls'] += 1
            elif re.match(r'\s*["\']', post_match):
                result['static_output_calls'] += 1
                # 提取静态字符串
                str_match = re.match(r'\s*["\']([^"\']*)["\']', post_match)
                if str_match:
                    s = str_match.group(1)
                    if len(s) > 2 and not s.startswith('['):  # 排除太短的和 Rich 标签
                        result['static_strings'].append(s)
    
    return result


def phase1_scan(dry_run=False):
    """Phase 1: 全量扫描"""
    print("=" * 60)
    print("Phase 1: 全量扫描")
    print("=" * 60)
    
    files = find_py_files()
    print(f"找到 {len(files)} 个文件待扫描\n")
    
    results = []
    needs_i18n = []
    has_conflict = []
    total_output = 0
    total_fstring = 0
    total_static = 0
    
    for f in files:
        r = scan_file(f)
        results.append(r)
        
        if not r['has_i18n_import'] and r['output_calls'] > 0:
            needs_i18n.append(r)
        if r['has_underscore_conflict']:
            has_conflict.append(r)
        
        total_output += r['output_calls']
        total_fstring += r['fstring_output_calls']
        total_static += r['static_output_calls']
    
    # 按输出调用数排序
    needs_i18n.sort(key=lambda x: x['output_calls'], reverse=True)
    
    # 打印报告
    print(f"{'文件':<45} {'行':>5} {'输出':>5} {'f-str':>5} {'静态':>5} {'i18n':>4} {'冲突':>4}")
    print("-" * 75)
    
    for r in results:
        if r['output_calls'] > 0:
            marker = ''
            if r['has_underscore_conflict']:
                marker += ' ⚠'
            print(f"{r['relative']:<45} {r['lines']:>5} {r['output_calls']:>5} "
                  f"{r['fstring_output_calls']:>5} {r['static_output_calls']:>5} "
                  f"{'✓' if r['has_i18n_import'] else '✗':>4}{marker}")
    
    print(f"\n总计: {total_output} 个输出调用 ({total_fstring} f-string, {total_static} 静态)")
    print(f"需添加导入: {len(needs_i18n)} 个文件")
    print(f"有 _ 冲突: {len(has_conflict)} 个文件")
    
    # 保存扫描结果
    if not dry_run:
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_files': len(files),
            'total_output_calls': total_output,
            'total_fstring': total_fstring,
            'total_static': total_static,
            'needs_import': [r['relative'] for r in needs_i18n],
            'has_conflict': [{'file': r['relative'], 'lines': r['conflict_lines']} for r in has_conflict],
            'top_files': [{'file': r['relative'], 'calls': r['output_calls']} for r in needs_i18n[:20]],
        }
        report_path = PROJECT_ROOT / "i18n_scan_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n扫描报告已保存: {report_path}")
    
    return results, needs_i18n, has_conflict


# ─── Phase 2: 注入导入 ──────────────────────────────────

def phase2_inject_imports(needs_i18n, has_conflict, dry_run=False):
    """Phase 2: 添加 i18n 导入"""
    print("\n" + "=" * 60)
    print("Phase 2: 注入 i18n 导入")
    print("=" * 60)
    
    conflict_files = {c['relative'] for c in has_conflict}
    
    injected = []
    skipped_conflict = []
    skipped_no_output = []
    errors = []
    
    for r in needs_i18n[:30]:  # 限制前30个高优先级文件
        if r['relative'] in conflict_files:
            skipped_conflict.append(r['relative'])
            continue
        
        filepath = Path(r['path'])
        content = read_file_safe(filepath)
        
        # 找到合适的注入点（最后一个标准库/本地导入之后）
        import_lines = []
        for i, line in enumerate(content.split('\n')):
            if re.match(r'^(from|import)\s', line) and 'bwm_cli.i18n' not in line:
                import_lines.append((i, line))
        
        if not import_lines:
            skipped_no_output.append(r['relative'])
            continue
        
        # 在最后一个 import 之后插入
        last_import_line = import_lines[-1][0]
        lines = content.split('\n')
        
        new_lines = lines[:last_import_line + 1]
        new_lines.append('from bwm_cli.i18n import _')
        new_lines.extend(lines[last_import_line + 1:])
        
        new_content = '\n'.join(new_lines)
        
        if dry_run:
            print(f"  [DRY-RUN] 将注入: {r['relative']}")
        else:
            write_file_safe(filepath, new_content)
            print(f"  ✓ 已注入: {r['relative']}")
        
        injected.append(r['relative'])
    
    print(f"\n注入完成: {len(injected)} 个文件")
    if skipped_conflict:
        print(f"因 _ 冲突跳过: {len(skipped_conflict)} 个文件")
        for f in skipped_conflict[:5]:
            print(f"  - {f}")
    
    return injected


# ─── Phase 3: 处理 _ 冲突 ──────────────────────────────

def phase3_resolve_conflicts(has_conflict, dry_run=False):
    """Phase 3: 重命名 _ 抛弃变量为 _unused"""
    print("\n" + "=" * 60)
    print("Phase 3: 处理 _ 变量冲突")
    print("=" * 60)
    
    resolved = []
    
    for c in has_conflict[:15]:  # 限制数量
        filepath = PROJECT_ROOT / c['relative']
        if not filepath.exists():
            continue
        
        content = read_file_safe(filepath)
        original = content
        
        # 重命名模式
        # 1. for _, var in ... → for _unused, var in ...
        content = re.sub(r'\bfor\s+_\s*,', 'for _unused,', content)
        # 2. _, var = expr → _unused, var = expr  
        content = re.sub(r'^(\s*)_\s*,\s*(\w+\s*=)', r'\1_unused, \2', content, flags=re.MULTILINE)
        # 3. _ = expr → _unused = expr (但不是 def _...)
        content = re.sub(r'^(\s*)_(\s*=\s*)(?!.*def)', r'\1_unused\2', content, flags=re.MULTILINE)
        
        if content != original:
            if dry_run:
                print(f"  [DRY-RUN] 将解决: {c['relative']}")
            else:
                write_file_safe(filepath, content)
                print(f"  ✓ 已解决: {c['relative']}")
            resolved.append(c['relative'])
        else:
            print(f"  - 无需修改: {c['relative']}")
    
    print(f"\n解决完成: {len(resolved)} 个文件")
    return resolved


# ─── Phase 4: 提取字符串 ────────────────────────────────

def _add_string(all_strings, s, rel):
    """Helper: add a candidate string to the collection, filtering noise."""
    if not s or len(s) < 3:
        return
    # 排除纯 ANSI 转义序列
    if re.match(r'^[\x1b\[\]\[\\0-9;mKk]+$', s):
        return
    # 排除仅由 Rich 标签组成的字符串（如 [bold red], [/bold]）
    if re.match(r'^\[/?[a-z_ ]+\]$', s):
        return
    # 排除变量占位符/纯格式化模板
    if s.startswith('{') or s.startswith('['):
        return
    all_strings[s].append(rel)


def phase4_extract_strings(dry_run=False):
    """Phase 4: 从所有已注入 i18n 的文件中提取静态字符串"""
    print("\n" + "=" * 60)
    print("Phase 4: 提取可翻译字符串")
    print("=" * 60)
    
    files = find_py_files()
    all_strings = defaultdict(list)  # msgid → [files]
    
    for f in files:
        content = read_file_safe(f)
        if 'from bwm_cli.i18n import _' not in content:
            continue
        
        rel = str(f.relative_to(PROJECT_ROOT))
        
        # ── 方法 1: 直接 _() 调用 ──
        for m in re.finditer(r'_\(["\']([^"\']{3,})["\']\)', content):
            _add_string(all_strings, m.group(1), rel)
        
        # ── 方法 2: 自动翻译辅助函数中的静态字符串（第一个参数）──
        for func in AUTO_TRANSLATE_FUNCTIONS:
            pattern = rf'{func}\(\s*["\']([^"\']{{3,}})["\']'
            for m in re.finditer(pattern, content):
                _add_string(all_strings, m.group(1), rel)
        
        # ── 方法 3: check_* 函数的第二个参数（detail）──
        for func in ['check_ok', 'check_warn', 'check_fail', 'check_info']:
            # 匹配 func("first", "second") 中的第二个静态字符串
            pattern2 = rf'{func}\(\s*["\'][^"\']+["\']\s*,\s*["\']([^"\']{{3,}})["\']'
            for m in re.finditer(pattern2, content):
                _add_string(all_strings, m.group(1), rel)
        
        # ── 方法 4: print(color("static", ...)) 嵌套模式 ──
        for m in re.finditer(r'print\(\s*color\(\s*["\']([^"\']{3,})["\']', content):
            _add_string(all_strings, m.group(1), rel)
        
        # ── 方法 5: 独立 color("static", ...) 调用 ──
        for m in re.finditer(r'(?<!print\()\bcolor\(\s*["\']([^"\']{3,})["\']', content):
            _add_string(all_strings, m.group(1), rel)
        
        # ── 方法 6: print("static text") 直接调用（非 f-string）──
        # 匹配 print("...") 或 print('...')，但不能是 print(f"...")
        for m in re.finditer(r'print\(\s*["\']([^"\']{3,})["\']', content):
            _add_string(all_strings, m.group(1), rel)
    
    print(f"提取到 {len(all_strings)} 个唯一字符串")
    
    # 按使用次数排序
    sorted_strings = sorted(all_strings.items(), key=lambda x: len(x[1]), reverse=True)
    for s, files in sorted_strings[:20]:
        print(f"  [{len(files)}x] {s[:70]}")
    if len(sorted_strings) > 20:
        print(f"  ... 还有 {len(sorted_strings) - 20} 个")
    
    return all_strings


# ─── Phase 5: 生成 .po 条目 ─────────────────────────────

def phase5_generate_po(all_strings, dry_run=False):
    """Phase 5: 生成 .po 翻译条目"""
    print("\n" + "=" * 60)
    print("Phase 5: 生成 .po 条目")
    print("=" * 60)
    
    # 读取现有 .po
    with open(PO_PATH, 'r', encoding='utf-8') as f:
        po_content = f.read()
    
    existing_ids = set(re.findall(r'^msgid "(.*)"$', po_content, re.MULTILINE))
    
    new_entries = []
    for msgid in sorted(all_strings.keys()):
        if msgid in existing_ids:
            continue
        # 生成占位翻译
        msgstr = generate_placeholder_translation(msgid)
        new_entries.append((msgid, msgstr))
    
    if not new_entries:
        print("没有新条目需要添加")
        return []
    
    # 构建新条目文本
    new_section = f"\n# ─── 自动提取 {datetime.now().strftime('%Y-%m-%d %H:%M')} ───\n"
    for msgid, msgstr in new_entries:
        new_section += f'msgid "{msgid}"\nmsgstr "{msgstr}"\n\n'
    
    if dry_run:
        print(f"[DRY-RUN] 将添加 {len(new_entries)} 个条目:")
        for msgid, msgstr in new_entries[:10]:
            print(f"  {msgid[:60]} → {msgstr[:60]}")
        if len(new_entries) > 10:
            print(f"  ... 还有 {len(new_entries) - 10} 个")
    else:
        with open(PO_PATH, 'a', encoding='utf-8', newline='') as f:
            f.write(new_section)
        print(f"已添加 {len(new_entries)} 个条目到 .po")
    
    return new_entries


# ─── 翻译生成 ───────────────────────────────────────────

# 常见科技词汇映射
TECH_GLOSSARY = {
    'Gateway Service': '网关服务',
    'Runtime Filesystem Capability': '运行时文件系统能力',
    'Persistent Memory': '持久记忆',
    'Prompt Cache Freshness': '提示缓存新鲜度',
    'Python Environment': 'Python 环境',
    'Required Packages': '依赖包',
    'Configuration Files': '配置文件',
    'Config Structure': '配置结构',
    'Auth Providers': '认证提供者',
    'Directory Structure': '目录结构',
    'Command Installation': '命令安装',
    'External Tools': '外部工具',
    'API Connectivity': 'API 连通性',
    'Plugin System': '插件系统',
    'Native install': '原生安装',
    'full host filesystem access': '完整主机文件系统访问',
    'no sandbox': '无沙箱',
    'tools run as your user': '工具以您的用户身份运行',
    'Host bridge mounted': '主机桥接已挂载',
    'Container runtime without host bridge': '无主机桥接的容器运行时',
    'only /opt/data is writable': '仅 /opt/data 可写',
    'Systemd linger enabled': 'Systemd 驻留已启用',
    'Systemd linger disabled': 'Systemd 驻留已禁用',
    'gateway service survives logout': '网关服务在注销后仍存活',
    'gateway may stop after logout': '网关可能在注销后停止',
    'Could not verify systemd linger': '无法验证 systemd 驻留',
    'Could not import runtime detectors': '无法导入运行时检测器',
    'WSL detected': '检测到 WSL',
    'Windows host visible at /mnt/c/': 'Windows 主机位于 /mnt/c/',
    'Could not resolve BOOKWORMPRO_HOME': '无法解析 BOOKWORMPRO_HOME',
    'missing': '缺失',
    'empty': '空',
    'no recall yet': '尚无回忆',
    'will be auto-seeded on next start': '下次启动时将自动初始化',
    'pruning recommended': '建议清理',
    'Checking OpenRouter API': '正在检查 OpenRouter API',
    'Checking Anthropic API': '正在检查 Anthropic API',
    'invalid API key': 'API 密钥无效',
    'out of credits': '额度不足',
    'payment required': '需要付费',
    'rate limited': '被限流',
    'key configured': '密钥已配置',
    'created': '已创建',
    'not found': '未找到',
    'will be created on first use': '将在首次使用时创建',
    'exists': '存在',
    'directory exists': '目录存在',
    'Created': '已创建',
    'Failed': '失败',
    'Verified': '已验证',
    'Available': '可用',
    'Unavailable': '不可用',
    'Enabled': '已启用',
    'Disabled': '已禁用',
    'Active': '活跃',
    'Inactive': '非活跃',
    'Running': '运行中',
    'Stopped': '已停止',
    'Starting': '启动中',
    'Restarting': '重启中',
    'Health check': '健康检查',
    'Status': '状态',
    'Error': '错误',
    'Warning': '警告',
    'Success': '成功',
    'Info': '信息',
    'Debug': '调试',
}

def generate_placeholder_translation(msgid):
    """为英文 msgid 生成中文占位翻译"""
    # 精确匹配词汇表
    if msgid in TECH_GLOSSARY:
        return TECH_GLOSSARY[msgid]
    
    # 部分匹配
    for en, zh in TECH_GLOSSARY.items():
        if en.lower() in msgid.lower() and len(en) > len(msgid) // 2:
            return f"[EN] {msgid}"
    
    # 常见后缀替换
    s = msgid
    s = s.replace('enabled', '已启用')
    s = s.replace('disabled', '已禁用')
    s = s.replace('active', '活跃')
    s = s.replace('available', '可用')
    s = s.replace('unavailable', '不可用')
    s = s.replace('running', '运行中')
    s = s.replace('stopped', '已停止')
    s = s.replace('configured', '已配置')
    s = s.replace('installed', '已安装')
    s = s.replace('detected', '已检测到')
    s = s.replace('exists', '存在')
    s = s.replace('missing', '缺失')
    s = s.replace('created', '已创建')
    s = s.replace('verified', '已验证')
    s = s.replace('loaded', '已加载')
    
    if s != msgid:
        return s
    
    # 其他：标记为待翻译
    if any('\u4e00' <= c <= '\u9fff' for c in msgid):
        return msgid  # 已经是中文
    return f"[待翻译] {msgid}"


# ─── Phase 6: 编译 ──────────────────────────────────────

def phase6_compile(dry_run=False):
    """Phase 6: 编译 .mo"""
    print("\n" + "=" * 60)
    print("Phase 6: 编译 .mo")
    print("=" * 60)
    
    if dry_run:
        print("[DRY-RUN] 将运行 compile_i18n.py")
        return
    
    import subprocess
    result = subprocess.run(
        [sys.executable, str(COMPILE_SCRIPT)],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT)
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"编译错误: {result.stderr}")
        return False
    
    # 验证
    sys.path.insert(0, str(PROJECT_ROOT))
    from bwm_cli.i18n import setup_i18n, _
    setup_i18n('zh_CN', force=True)
    
    # 测试几个翻译
    tests = [
        ('no tools', '无工具'),
    ]
    ok = 0
    for en, expected in tests:
        result = _(en)
        if result == expected:
            ok += 1
    
    print(f"验证: {ok}/{len(tests)} 通过")
    return True


# ─── 主入口 ─────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='BookwormPRO i18n 自动化管道')
    parser.add_argument('--dry-run', action='store_true', help='不实际修改文件')
    parser.add_argument('--phase', type=int, choices=[1,2,3,4,5,6], help='只运行指定阶段')
    parser.add_argument('--from-phase', type=int, choices=[1,2,3,4,5,6], help='从指定阶段开始运行')
    args = parser.parse_args()
    
    start_phase = args.from_phase or args.phase or 1
    end_phase = args.phase or 6
    
    print(f"BookwormPRO i18n 自动化管道")
    print(f"模式: {'DRY-RUN (不写文件)' if args.dry_run else 'LIVE (会修改文件)'}")
    print(f"阶段: {start_phase} → {end_phase}")
    print()
    
    results = {}
    
    if start_phase <= 1 <= end_phase:
        scan_results, needs_i18n, has_conflict = phase1_scan(dry_run=args.dry_run)
        results['scan'] = {'needs_i18n': needs_i18n, 'has_conflict': has_conflict}
    
    if start_phase <= 2 <= end_phase:
        if 'scan' not in results:
            scan_results, needs_i18n, has_conflict = phase1_scan(dry_run=True)
            results['scan'] = {'needs_i18n': needs_i18n, 'has_conflict': has_conflict}
        injected = phase2_inject_imports(
            results['scan']['needs_i18n'],
            results['scan']['has_conflict'],
            dry_run=args.dry_run
        )
        results['injected'] = injected
    
    if start_phase <= 3 <= end_phase:
        if 'scan' not in results:
            scan_results, needs_i18n, has_conflict = phase1_scan(dry_run=True)
            results['scan'] = {'needs_i18n': needs_i18n, 'has_conflict': has_conflict}
        resolved = phase3_resolve_conflicts(
            results['scan']['has_conflict'],
            dry_run=args.dry_run
        )
        results['resolved'] = resolved
    
    if start_phase <= 4 <= end_phase:
        all_strings = phase4_extract_strings(dry_run=args.dry_run)
        results['all_strings'] = all_strings
    
    if start_phase <= 5 <= end_phase:
        if 'all_strings' not in results:
            all_strings = phase4_extract_strings(dry_run=True)
            results['all_strings'] = all_strings
        new_entries = phase5_generate_po(results['all_strings'], dry_run=args.dry_run)
        results['new_entries'] = new_entries
    
    if start_phase <= 6 <= end_phase:
        success = phase6_compile(dry_run=args.dry_run)
        results['compiled'] = success
    
    print("\n" + "=" * 60)
    print("管道完成")
    print("=" * 60)
    if args.dry_run:
        print("⚠ 这是 DRY-RUN，未修改任何文件。去掉 --dry-run 以实际执行。")
