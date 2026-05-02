# 小程序性能优化

## 启动优化

### 分包配置

```json
// app.json
{
  "pages": ["pages/index/index", "pages/user/user"],
  "subpackages": [
    {
      "root": "packageA",
      "name": "pack-a",
      "pages": ["pages/detail/detail"]
    },
    {
      "root": "packageB",
      "independent": true,  // 独立分包
      "pages": ["pages/login/login"]
    }
  ],
  "preloadRule": {
    "pages/index/index": {
      "network": "all",
      "packages": ["pack-a"]
    }
  }
}
```

### 按需注入

```json
// app.json
{
  "lazyCodeLoading": "requiredComponents"
}
```

### 初始渲染缓存

```json
// page.json
{
  "initialRenderingCache": "static"
}
```

## 渲染优化

### setData 优化

```javascript
// ❌ 错误：全量更新
this.setData({ list: this.data.list })

// ✅ 正确：路径更新
this.setData({ 'list[0].name': '新名称' })

// ✅ 正确：合并更新
const updates = {}
items.forEach((item, i) => {
  updates[`list[${i}].checked`] = true
})
this.setData(updates)

// ✅ 分离渲染数据
Page({
  data: { displayList: [] },  // 只放渲染数据
  fullList: [],               // 完整数据放 data 外
  
  filter(keyword) {
    this.setData({
      displayList: this.fullList.filter(i => i.name.includes(keyword))
    })
  }
})
```

### 虚拟列表

```javascript
Component({
  properties: { list: Array, itemHeight: { type: Number, value: 80 } },
  data: { startIndex: 0, visibleList: [] },
  
  methods: {
    onScroll(e) {
      const startIndex = Math.floor(e.detail.scrollTop / this.data.itemHeight)
      if (startIndex !== this.data.startIndex) {
        this.setData({ startIndex }, () => this.updateVisible())
      }
    },
    
    updateVisible() {
      const { list, startIndex, itemHeight } = this.data
      const visibleCount = Math.ceil(wx.getSystemInfoSync().windowHeight / itemHeight) + 2
      this.setData({
        visibleList: list.slice(startIndex, startIndex + visibleCount),
        offsetY: startIndex * itemHeight
      })
    }
  }
})
```

### WXS 视图层计算

```html
<!-- utils.wxs -->
<wxs module="utils">
module.exports = {
  formatPrice: function(price) {
    return '¥' + (price / 100).toFixed(2)
  }
}
</wxs>

<view>{{utils.formatPrice(item.price)}}</view>
```

## 图片优化

```html
<!-- 懒加载 -->
<image src="{{url}}" lazy-load mode="aspectFill" />

<!-- WebP 格式 -->
<image src="{{url}}?x-oss-process=image/format,webp" />

<!-- 响应式尺寸 -->
<image src="{{url}}?x-oss-process=image/resize,w_{{width * 2}}" />
```

## 包体积优化

1. **图片处理**
   - 压缩图片
   - 使用 CDN
   - 按需加载

2. **代码优化**
   - 移除未使用代码
   - 分包加载
   - 组件按需引入

3. **依赖优化**
   - 精简 npm 包
   - 使用小程序原生能力

## 骨架屏

```javascript
// 开发者工具 -> 工具 -> 生成骨架屏
// 会生成 page.skeleton.wxml 和 page.skeleton.wxss
```

```html
<view wx:if="{{loading}}">
  <include src="page.skeleton.wxml"/>
</view>
<view wx:else>
  <!-- 实际内容 -->
</view>
```

## 性能指标

```javascript
// 获取性能数据
const performance = wx.getPerformance()
const observer = performance.createObserver((entryList) => {
  console.log(entryList.getEntries())
})
observer.observe({ entryTypes: ['render', 'script', 'navigation'] })
```

## 优化清单

**启动**
- [ ] 主包 < 2MB
- [ ] 分包加载
- [ ] 按需注入
- [ ] 骨架屏
- [ ] 首屏 setData 最小化

**渲染**
- [ ] setData 路径更新
- [ ] 长列表虚拟化
- [ ] 图片懒加载
- [ ] 避免 onPageScroll 频繁操作

**包体积**
- [ ] 图片 CDN 化
- [ ] 移除无用代码
- [ ] 精简依赖
