---
name: china-web-font-stack
description: >
  Chinese web font deployment — Google Fonts CDN replacement for China-hosted sites.
  Covers: system font stack (PingFang SC / Microsoft YaHei), Alibaba PuHuiTi 
  download attempts and why they fail, woff2 vs TTF tradeoffs, and pragmatic 
  fallback decisions. Trigger: China font, Google Fonts blocked, Chinese typography,
  国内字体, system font stack.
safety:
  level: low
maturity: stable
cost_level: low
last-reviewed: 2026-05-02
---

# China Web Font Stack

When a China-hosted site uses Google Fonts, replace with system fonts — zero download, instant load, 100% domestic availability.

## The Problem

Google Fonts CDN (`fonts.googleapis.com` / `fonts.gstatic.com`) is unreliable in China:
- Intermittently blocked or extremely slow
- Not a license issue (OFL fonts are legal in China) — it's a network reachability issue

## Solution: System Font Stack

```css
font-family: 'PingFang SC', 'Microsoft YaHei', 'Hiragino Sans GB', 'WenQuanYi Micro Hei', sans-serif;
```

| Font | Platform | Quality | Coverage |
|------|----------|---------|----------|
| PingFang SC | macOS / iOS | Excellent, modern | 100% of Apple China users |
| Microsoft YaHei | Windows | Very good, clean | 99%+ of Win China users |
| Hiragino Sans GB | Older macOS | Good | Fallback |
| WenQuanYi Micro Hei | Linux | Acceptable | Fallback |

## Why Not Alibaba PuHuiTi (self-hosted)

Alibaba PuHuiTi is free for commercial use and visually excellent. But self-hosting is impractical:

1. **File size**: Chinese TTF per weight = ~8MB. 6 weights = ~48MB. Too large for page load.
2. **woff2 unavailable**: npm packages contain only TTF, not woff2. Converting TTF→woff2 for full CJK requires fonttools + significant CPU.
3. **No reliable CDN**: jsdelivr, BootCDN, staticaly — all failed to serve woff2 files for PuHuiTi (tested 2026-05).
4. **npm direct download**: `registry.npmjs.org` blocked from China. `npmmirror.com` works but only serves TTF.

**Verdict**: System fonts are the practical choice for China-only sites. PuHuiTi only viable via paid Chinese font CDN services (有字库 youziku.com, 字体天下).

## Migration Steps

1. Remove Google Fonts `<link>` from HTML
2. Remove `@import` or CDN URLs
3. Replace all `font-family` references with the system stack
4. Update CSS variables: `--font-display` and `--font-body`
5. Deploy and verify no external font requests in DevTools Network tab

## CSS Variables Pattern

```css
:root {
  --font-display: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --font-body:    'PingFang SC', 'Microsoft YaHei', sans-serif;
}

/* Heavy weights for headings */
h1, h2 { font-weight: 900; letter-spacing: 0.02em; }
h3 { font-weight: 700; }
```

## Verification

```bash
# Check no Google Fonts references remain
grep -r "fonts.googleapis" /var/www/site/
grep -r "fonts.gstatic" /var/www/site/

# Should return empty
```

## Known Limitation

System fonts are sans-serif. If the site design requires a serif Chinese font (like Noto Serif SC), the system fallback is `STSong` / `SimSun` — which are dated. For serif needs, self-host a subset of Noto Serif CJK SC (woff2, ~2MB for regular weight only).
