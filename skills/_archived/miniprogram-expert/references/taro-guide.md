# Taro 跨端开发指南

## 函数组件 + Hooks

```tsx
import { View, Text, Button } from '@tarojs/components'
import { useLoad, useDidShow, useShareAppMessage } from '@tarojs/taro'
import { useState, useCallback } from 'react'
import './index.scss'

const Index: React.FC = () => {
  const [list, setList] = useState<Item[]>([])
  const [loading, setLoading] = useState(false)

  useLoad((options) => {
    console.log('参数:', options)
    fetchData()
  })

  useDidShow(() => { /* 每次显示 */ })

  useShareAppMessage(() => ({
    title: '分享',
    path: '/pages/index/index'
  }))

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.getList()
      setList(res.data)
    } finally {
      setLoading(false)
    }
  }, [])

  return (
    <View className='index'>
      {list.map(item => (
        <View key={item.id} onClick={() => handleClick(item.id)}>
          <Text>{item.name}</Text>
        </View>
      ))}
    </View>
  )
}

export default Index
```

## 页面配置

```typescript
// index.config.ts
export default definePageConfig({
  navigationBarTitleText: '首页',
  enablePullDownRefresh: true
})
```

## 常用 Hooks

```tsx
import Taro, {
  useLoad,           // onLoad
  useReady,          // onReady
  useDidShow,        // onShow
  useDidHide,        // onHide
  useUnload,         // onUnload
  usePullDownRefresh,
  useReachBottom,
  useShareAppMessage,
  useShareTimeline,
  useRouter          // 获取路由参数
} from '@tarojs/taro'

// 路由参数
const { params } = useRouter()
console.log(params.id)

// 下拉刷新
usePullDownRefresh(() => {
  fetchData().then(() => Taro.stopPullDownRefresh())
})
```

## API 调用

```tsx
// 统一 API
Taro.request({ url, data, method })
Taro.navigateTo({ url: '/pages/detail/detail?id=1' })
Taro.showToast({ title: '成功', icon: 'success' })
Taro.setStorageSync('key', value)
Taro.getStorageSync('key')

// 环境判断
if (process.env.TARO_ENV === 'weapp') { /* 微信 */ }
if (process.env.TARO_ENV === 'alipay') { /* 支付宝 */ }
if (process.env.TARO_ENV === 'h5') { /* H5 */ }
```

## 状态管理 (Zustand)

```tsx
// store/user.ts
import { create } from 'zustand'

interface UserStore {
  user: User | null
  setUser: (user: User) => void
  logout: () => void
}

export const useUserStore = create<UserStore>(set => ({
  user: null,
  setUser: (user) => set({ user }),
  logout: () => set({ user: null })
}))

// 使用
const { user, setUser } = useUserStore()
```

## 请求封装

```tsx
// services/request.ts
import Taro from '@tarojs/taro'

const BASE_URL = 'https://api.example.com'

export const request = async <T>(options: Taro.request.Option): Promise<T> => {
  const token = Taro.getStorageSync('token')
  
  const res = await Taro.request({
    ...options,
    url: BASE_URL + options.url,
    header: {
      'Authorization': token ? `Bearer ${token}` : '',
      ...options.header
    }
  })
  
  if (res.statusCode === 401) {
    Taro.removeStorageSync('token')
    Taro.navigateTo({ url: '/pages/login/login' })
    throw new Error('未授权')
  }
  
  if (res.data.code !== 0) {
    Taro.showToast({ title: res.data.message, icon: 'none' })
    throw new Error(res.data.message)
  }
  
  return res.data.data
}

export const get = <T>(url: string, data?: any) => 
  request<T>({ url, method: 'GET', data })

export const post = <T>(url: string, data?: any) => 
  request<T>({ url, method: 'POST', data })
```

## 样式

```scss
// 使用 rpx 或 Taro 默认转换 px
.container {
  padding: 20px;  // 会自动转换
  font-size: 28px;
}

// 条件编译
/* #ifdef weapp */
.weapp-only { }
/* #endif */
```

## 条件编译

```tsx
// JS 条件编译
/* @conditional-compile {"mp-weapp": true} */
console.log('只在微信小程序')

// JSX 条件编译
{process.env.TARO_ENV === 'weapp' && <WxComponent />}
```
