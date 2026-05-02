---
name: china-web-font-deployment
description: >
  面向中国用户的网站字体部署方案。当需要为国内网站选择/替换字体、
  解决 Google Fonts 国内不可达、或需要免费商用中文字体时使用。
  覆盖：系统字体栈策略、CDN字体下载排障、npm包提取、
  woff2 vs ttf选择、阿里普惠体/思源字体实践。
category: devops
maturity: stable
cost_level: low
last_updated: 2026-05-02
---

# 中国网站字体部署实战

> 基于真实踩坑：CDN不可达→npm只有TTF太大→系统字体栈最优

## 决策树

```
网站目标用户在中国？
├─ 是 → 优先系统字体栈（零下载/全覆盖）
│   └─ font-family: 'PingFang SC','Microsoft YaHei','Hiragino Sans GB',sans-serif
│   └─ PingFang SC(Mac) / Microsoft YaHei(Windows) 覆盖99%+中文设备
│
├─ 需要品牌差异化字体？
│   ├─ Google Fonts → ❌ fonts.googleapis.com 国内不稳定
│   ├─ jsdelivr CDN → ❌ 部分节点不可达
│   ├─ 阿里OSS → ❌ 需认证，直链403
│   ├─ npm包(@fontpkg/alibaba-pu-hui-ti-2-0) → ⚠️ 只含TTF(8MB/个)，无woff2
│   └─ npmmirror.com → ✅ 可下载，但只有TTF需自转woff2
│
└─ 自托管 → 下载woff2到 assets/fonts/ → @font-face → 推服务器
```

## 系统字体栈（推荐首选）

```css
/* 中文无衬线 — 全平台覆盖 */
--font-body: 'PingFang SC', 'Microsoft YaHei', 'Hiragino Sans GB',
             'WenQuanYi Micro Hei', 'Noto Sans CJK SC', sans-serif;

/* 中文衬线 */
--font-serif: 'Noto Serif CJK SC', 'Source Han Serif SC',
              'STSong', 'SimSun', 'PMingLiU', serif;
```

| 平台 | 字体 | 覆盖率 |
|------|------|:--:|
| macOS/iOS | PingFang SC（苹方） | 99%+ |
| Windows | Microsoft YaHei（微软雅黑） | 99%+ |
| Linux | WenQuanYi Micro Hei | 80%+ |
| Android | Noto Sans CJK SC | 90%+ |

## 阿里普惠体自托管流程

### 1. 下载
```bash
# npmmirror 可下载（国内可达）
wget https://registry.npmmirror.com/@fontpkg/alibaba-pu-hui-ti-2-0/-/alibaba-pu-hui-ti-2-0-2.0.2.tgz
tar xzf alibaba-pu-hui-ti-2-0-2.0.2.tgz
# 提取 package/*.ttf → 需自转woff2（fonttools）
```

### 2. TTF→WOFF2转换
```bash
pip install fonttools brotli
fonttools ttLib.woff2 compress AlibabaPuHuiTi-3-55-Regular.ttf
# 输出: AlibabaPuHuiTi-3-55-Regular.woff2 (~800KB，比TTF小10倍)
```

### 3. @font-face 配置
```css
@font-face {
  font-family: 'AlibabaPuHuiTi';
  src: url('AlibabaPuHuiTi-3-55-Regular.woff2') format('woff2');
  font-weight: 400;
  font-display: swap;  /* 关键：先显示系统字体，加载后切换 */
}
```

## 踩坑记录

| 坑 | 现象 | 解决 |
|----|------|------|
| Google Fonts CDN | 间歇超时/白屏 | 切系统字体栈 |
| npm 含TTF无woff2 | 8MB/个，网页不可用 | fonttools转woff2 |
| jsdelivr 部分节点 | 国内404 | 换npmmirror |
| 阿里OSS直链 | 403需认证 | 不可直链 |
| 字体文件过大 | 首次加载慢 | 子集化(subset)只保留常用字 |

## 许可证速查

| 字体 | 许可证 | 商用 |
|------|--------|:--:|
| 阿里普惠体 | 免费商用 | ✅ |
| 思源黑体/宋体 | SIL OFL | ✅ |
| 站酷系列 | SIL OFL | ✅ |
| 系统字体(PingFang/雅黑) | OS自带 | ✅ |
| Google Fonts所有 | SIL OFL | ✅ |
