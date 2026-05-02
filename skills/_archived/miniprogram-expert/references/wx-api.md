# 微信小程序 API 速查

## 路由导航

```javascript
// 保留当前页跳转（最多10层）
wx.navigateTo({
  url: '/pages/detail/detail?id=123',
  success(res) {
    res.eventChannel.emit('sendData', { data: 'hello' })
  }
})

// 被打开页接收
onLoad() {
  this.getOpenerEventChannel().on('sendData', data => {})
}

// 关闭当前页跳转
wx.redirectTo({ url: '/pages/other/other' })

// 关闭所有页面
wx.reLaunch({ url: '/pages/index/index' })

// 返回
wx.navigateBack({ delta: 1 })

// TabBar页面
wx.switchTab({ url: '/pages/home/home' })
```

## 数据存储

```javascript
// 同步
wx.setStorageSync('key', { name: 'value' })
const data = wx.getStorageSync('key')
wx.removeStorageSync('key')

// 异步
wx.setStorage({ key: 'key', data: value, encrypt: true })
wx.getStorage({ key: 'key', success(res) { console.log(res.data) } })
```

## 网络请求

```javascript
wx.request({
  url: 'https://api.example.com/data',
  method: 'POST',
  data: { id: 1 },
  header: { 'Authorization': 'Bearer token' },
  timeout: 10000,
  success(res) { console.log(res.data) },
  fail(err) { console.error(err) }
})

// 上传
wx.uploadFile({
  url: 'https://api.example.com/upload',
  filePath: tempFilePath,
  name: 'file',
  formData: { userId: '123' }
})

// 下载
wx.downloadFile({
  url: 'https://example.com/file.pdf',
  success(res) { wx.openDocument({ filePath: res.tempFilePath }) }
})
```

## 用户授权

```javascript
// 登录
wx.login({ success(res) { /* 发送 res.code 到后端 */ } })

// 获取手机号（button触发）
// <button open-type="getPhoneNumber" bindgetphonenumber="onGetPhone">
onGetPhone(e) {
  if (e.detail.code) { /* 发送code到后端解密 */ }
}

// 检查授权
wx.getSetting({ success(res) {
  if (res.authSetting['scope.userLocation']) { /* 已授权 */ }
}})

// 请求授权
wx.authorize({ scope: 'scope.userLocation' })

// 打开设置
wx.openSetting()
```

## 支付

```javascript
wx.requestPayment({
  timeStamp: '',   // 后端返回
  nonceStr: '',    // 后端返回
  package: '',     // prepay_id
  signType: 'RSA',
  paySign: '',     // 后端返回
  success() { console.log('支付成功') },
  fail(err) {
    if (err.errMsg.includes('cancel')) { /* 取消 */ }
  }
})
```

## 媒体

```javascript
// 选择图片/视频
wx.chooseMedia({
  count: 9,
  mediaType: ['image', 'video'],
  sourceType: ['album', 'camera'],
  success(res) { console.log(res.tempFiles) }
})

// 预览图片
wx.previewImage({ current: url, urls: imageList })

// 保存到相册
wx.saveImageToPhotosAlbum({ filePath: path })
```

## 位置

```javascript
// 获取位置
wx.getLocation({
  type: 'gcj02',
  isHighAccuracy: true,
  success(res) { const { latitude, longitude } = res }
})

// 选择位置
wx.chooseLocation({ success(res) { /* name, address, lat, lng */ } })

// 打开地图
wx.openLocation({ latitude, longitude, name: '位置', scale: 18 })
```

## 界面交互

```javascript
// Toast
wx.showToast({ title: '成功', icon: 'success', duration: 2000 })
wx.showLoading({ title: '加载中', mask: true })
wx.hideLoading()

// Modal
wx.showModal({
  title: '提示',
  content: '确定删除？',
  success(res) { if (res.confirm) { /* 确定 */ } }
})

// ActionSheet
wx.showActionSheet({
  itemList: ['选项1', '选项2'],
  success(res) { console.log(res.tapIndex) }
})

// 导航栏
wx.setNavigationBarTitle({ title: '标题' })

// TabBar
wx.setTabBarBadge({ index: 0, text: '99' })
wx.showTabBarRedDot({ index: 0 })
```

## 自定义组件

```javascript
Component({
  options: { multipleSlots: true, styleIsolation: 'isolated' },
  
  properties: {
    title: { type: String, value: '' },
    data: { type: Object, observer(val) { this.process(val) } }
  },
  
  data: { internal: null },
  
  observers: { 'data.status': function(status) { } },
  
  lifetimes: {
    attached() { },
    detached() { }
  },
  
  methods: {
    handleTap() {
      this.triggerEvent('click', { id: this.data.data.id })
    }
  }
})
```

## Behaviors

```javascript
// behavior.js
module.exports = Behavior({
  properties: { commonProp: String },
  data: { commonData: '' },
  methods: { commonMethod() { } }
})

// 组件中使用
Component({ behaviors: [require('./behavior')] })
```
