# 小程序云开发指南

## 初始化

```javascript
// app.js
App({
  onLaunch() {
    wx.cloud.init({
      env: 'your-env-id',
      traceUser: true
    })
  }
})
```

## 云数据库

### 基础操作

```javascript
const db = wx.cloud.database()
const _ = db.command

// 添加
const { _id } = await db.collection('todos').add({
  data: { title: '待办', done: false, createTime: db.serverDate() }
})

// 查询
const { data } = await db.collection('todos')
  .where({ done: false, createTime: _.gt(new Date('2024-01-01')) })
  .orderBy('createTime', 'desc')
  .skip(0)
  .limit(20)
  .field({ title: true, done: true })
  .get()

// 更新
await db.collection('todos').doc(id).update({
  data: { done: true, updateTime: db.serverDate() }
})

// 路径更新
await db.collection('users').doc(id).update({
  data: { 'profile.avatar': newUrl }
})

// 删除
await db.collection('todos').doc(id).remove()

// 批量更新（需云函数）
await db.collection('todos').where({ done: true }).update({
  data: { archived: true }
})
```

### 查询操作符

```javascript
const _ = db.command

// 比较
_.eq(val)    // 等于
_.neq(val)   // 不等于
_.gt(val)    // 大于
_.gte(val)   // 大于等于
_.lt(val)    // 小于
_.lte(val)   // 小于等于
_.in([1,2])  // 在数组中
_.nin([1,2]) // 不在数组中

// 逻辑
_.and([cond1, cond2])
_.or([cond1, cond2])
_.not(cond)

// 示例
db.collection('orders').where({
  status: _.in(['pending', 'processing']),
  amount: _.gt(100).and(_.lt(1000))
})
```

### 聚合查询

```javascript
const $ = db.command.aggregate

const { list } = await db.collection('orders')
  .aggregate()
  .match({ status: 'paid' })
  .group({
    _id: '$userId',
    total: $.sum('$amount'),
    count: $.sum(1),
    avgAmount: $.avg('$amount')
  })
  .sort({ total: -1 })
  .limit(10)
  .end()
```

### 实时数据

```javascript
const watcher = db.collection('messages')
  .where({ roomId: 'xxx' })
  .orderBy('createTime', 'desc')
  .limit(50)
  .watch({
    onChange(snapshot) {
      console.log('变化:', snapshot.docs)
      console.log('变化类型:', snapshot.docChanges)
    },
    onError(err) { console.error(err) }
  })

// 关闭
watcher.close()
```

## 云函数

### 创建云函数

```javascript
// cloudfunctions/getUser/index.js
const cloud = require('wx-server-sdk')
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })
const db = cloud.database()

exports.main = async (event, context) => {
  const { OPENID, APPID } = cloud.getWXContext()
  
  try {
    const { data } = await db.collection('users')
      .where({ _openid: OPENID })
      .get()
    
    return { code: 0, data: data[0] || null }
  } catch (error) {
    return { code: -1, message: error.message }
  }
}
```

### 调用云函数

```javascript
const res = await wx.cloud.callFunction({
  name: 'getUser',
  data: { userId: '123' }
})
console.log(res.result)
```

### 定时触发器

```json
// config.json
{
  "triggers": [{
    "name": "dailyTask",
    "type": "timer",
    "config": "0 0 2 * * * *"
  }]
}
```

## 云存储

```javascript
// 上传
const { fileID } = await wx.cloud.uploadFile({
  cloudPath: `images/${Date.now()}.png`,
  filePath: tempFilePath
})

// 获取临时链接
const { fileList } = await wx.cloud.getTempFileURL({ fileList: [fileID] })
const url = fileList[0].tempFileURL

// 下载
const { tempFilePath } = await wx.cloud.downloadFile({ fileID })

// 删除
await wx.cloud.deleteFile({ fileList: [fileID] })
```

## 云托管

```javascript
// 调用云托管服务
const res = await wx.cloud.callContainer({
  config: { env: 'prod-xxx' },
  path: '/api/users',
  method: 'POST',
  data: { name: 'test' }
})
```
