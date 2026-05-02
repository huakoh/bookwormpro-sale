---
name: miniprogram-expert
description: >
  小程序开发专家。当用户需要微信小程序、支付宝小程序、抖音小程序开发，
  Taro、uni-app 跨端框架，云开发、云函数、分包优化、setData 优化、
  登录授权、支付功能、审核上架，或说 "小程序"、"Taro" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
maturity: stable
last-reviewed: 2026-02-18
---

# 小程序开发专家 (Mini Program Expert)

> **Output Style**: 本技能使用内联输出规范

专注于微信/支付宝/抖音等平台小程序开发，以及 Taro、uni-app 跨端开发。

## 触发关键词

- **平台**: `微信小程序`, `支付宝小程序`, `抖音小程序`, `百度小程序`
- **框架**: `Taro`, `uni-app`, `Remax`
- **功能**: `云开发`, `小程序登录`, `小程序支付`, `分享`
- **优化**: `分包`, `性能优化`, `启动优化`

## 核心能力

- **原生开发**: 微信、支付宝、抖音、百度小程序
- **跨端框架**: Taro 3.x、uni-app
- **云开发**: 云函数、云数据库、云存储
- **性能优化**: 启动、渲染、包体积优化
- **核心功能**: 登录授权、支付、分享

## 项目结构

### 微信小程序
```
miniprogram/
├── app.js / app.json / app.wxss
├── pages/
│   └── index/
│       ├── index.js / index.json
│       ├── index.wxml / index.wxss
├── components/
├── utils/
│   ├── request.js
│   └── auth.js
├── services/
└── packageA/  # 分包
```

### Taro 项目
```
src/
├── app.tsx / app.config.ts
├── pages/
│   └── index/
│       ├── index.tsx
│       └── index.config.ts
├── components/
├── hooks/
├── store/
└── services/
```

## 页面模板

```javascript
Page({
  data: { list: [], loading: false },
  
  onLoad(options) { this.init(options) },
  onShow() { },
  onPullDownRefresh() {
    this.loadData().then(() => wx.stopPullDownRefresh())
  },
  onReachBottom() { this.loadMore() },
  onShareAppMessage() {
    return { title: '分享', path: '/pages/index/index' }
  },
  
  async init(options) {
    this.setData({ loading: true })
    try {
      const data = await this.fetchData()
      this.setData({ list: data })
    } finally {
      this.setData({ loading: false })
    }
  }
})
```

## setData 优化

```javascript
// ❌ 全量更新
this.setData({ list: this.data.list })

// ✅ 路径更新
this.setData({
  'list[0].name': '新名称',
  [`list[${i}].done`]: true
})

// ✅ 合并更新
const updates = {}
items.forEach((item, i) => { updates[`list[${i}].checked`] = true })
this.setData(updates)
```

## 性能优化清单

**启动优化**
- 主包 < 2MB，分包加载
- `"lazyCodeLoading": "requiredComponents"`
- 骨架屏

**渲染优化**
- 减少 setData 频率和数据量
- 长列表用虚拟列表
- 图片懒加载

## 参考文档

详细API和代码请查阅:
- `references/wx-api.md` - 微信小程序API速查
- `references/taro-guide.md` - Taro跨端开发指南
- `references/cloud-dev.md` - 云开发完整指南
- `references/optimization.md` - 性能优化详解
- `scripts/request.js` - 请求封装模板
- `scripts/auth.js` - 登录授权模板

## 输出规范

- 中文回复，注释中文
- 代码完整可运行
- 说明平台兼容性差异
- 提供性能优化建议
- 避免废弃API
- 不在setData传大量数据
