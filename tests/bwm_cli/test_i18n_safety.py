from pathlib import Path
import pytest

@pytest.fixture(autouse=True)
def reset_i18n():
    import bwm_cli.i18n as m
    saved = (m._translator, m._current_language, m._initialized)
    yield
    m._translator, m._current_language, m._initialized = saved

def test_fallback_returns_original():
    from bwm_cli.i18n import _, setup_i18n
    setup_i18n(language="en", force=True)
    assert _("Hello World") == "Hello World"

def test_empty_msgstr_returns_original():
    from bwm_cli.i18n import _Translator
    t = _Translator()
    t._catalog = {"k": ""}
    assert t.gettext("k") == "k"

def test_join_renamed_placeholder_ok():
    from bwm_cli.i18n import _, setup_i18n
    setup_i18n(language="en", force=True)
    items = ["a", "b", "c"]
    r = _("Providers: {j}").format(j=", ".join(items))
    assert r == "Providers: a, b, c"

def test_join_old_pattern_crashes():
    s = "text {', '.join(x)}"
    with pytest.raises(KeyError):
        s.format(x="y")

def test_ternary_in_format_crashes():
    s = "val: {'a' if True else 'b'}"
    with pytest.raises(KeyError):
        s.format()

def test_sudo_precomputed_true():
    _sudo = "sudo " if True else ""
    assert f"{_sudo}start" == "sudo start"

def test_sudo_precomputed_false():
    _sudo = "sudo " if False else ""
    assert f"{_sudo}start" == "start"

def test_copied_files_format(capsys):
    from bwm_cli.i18n import _, setup_i18n
    setup_i18n(language="en", force=True)
    copied = ["a.py", "b.py"]
    print(_("+ {n} new: {j}").format(n=len(copied), j=", ".join(copied)))
    out = capsys.readouterr().out
    assert "2" in out and "a.py" in out

def test_pid_join(capsys):
    from bwm_cli.i18n import _, setup_i18n
    setup_i18n(language="en", force=True)
    pids = [1234, 5678]
    print(_("PID: {p}").format(p=", ".join(map(str, pids))))
    out = capsys.readouterr().out
    assert "1234" in out and "5678" in out

def test_i18n_biz_import_free():
    import bwm_cli.i18n as m
    src = Path(m.__file__).read_text(encoding="utf-8")
    biz = ("bwm_cli.", "tools.", "agent.")
    # Only top-level imports (column-0 `from`/`import`) matter for circular-import risk;
    # lazy imports inside function bodies are acceptable.
    top_level = [l for l in src.splitlines() if l.startswith(("import ", "from "))]
    for line in top_level:
        for b in biz:
            assert b not in line, f"top-level biz import found: {line!r}"

def _bwm():
    root = Path(__file__).resolve().parents[2] / "bwm_cli"
    return {f: f.read_text(encoding="utf-8") for f in root.glob("*.py")}

def test_no_join_format_crash():
    import re
    pat = re.compile(r"_\([^)]*\.join\([^)]*\)[^)]*\)\.format\(")
    hits = []
    for f, src in _bwm().items():
        for i, line in enumerate(src.splitlines(), 1):
            if pat.search(line):
                hits.append(f"{f.name}:{i}")
    assert not hits, hits

def test_no_ternary_format_crash():
    import re
    q = chr(39)
    pat = re.compile(r"_\([^)]*" + q + r" if [^)]+else " + q + r"[^)]*\)\.format\(")
    hits = []
    for f, src in _bwm().items():
        for i, line in enumerate(src.splitlines(), 1):
            if pat.search(line):
                hits.append(f"{f.name}:{i}")
    assert not hits, hits