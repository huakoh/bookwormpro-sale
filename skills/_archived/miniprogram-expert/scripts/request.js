/**
 * 小程序请求封装
 * Mini Program Request Wrapper
 */

const BASE_URL = 'https://api.example.com'

/**
 * 请求封装
 */
const request = (options) => {
  return new Promise((resolve, reject) => {
    const token = wx.getStorageSync('token')
    
    wx.request({
      url: BASE_URL + options.url,
      method: options.method || 'GET',
      data: options.data,
      header: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
        ...options.header
      },
      timeout: options.timeout || 10000,
      
      success(res) {
        if (res.statusCode === 200) {
          if (res.data.code === 0) {
            resolve(res.data)
          } else if (res.data.code === 401) {
            // Token 过期
            wx.removeStorageSync('token')
            wx.removeStorageSync('userInfo')
            wx.navigateTo({ url: '/pages/login/login' })
            reject(res.data)
          } else {
            wx.showToast({ title: res.data.message || '请求失败', icon: 'none' })
            reject(res.data)
          }
        } else {
          wx.showToast({ title: `请求失败: ${res.statusCode}`, icon: 'none' })
          reject(new Error(`HTTP ${res.statusCode}`))
        }
      },
      
      fail(err) {
        wx.showToast({ title: '网络异常', icon: 'none' })
        reject(err)
      }
    })
  })
}

// 便捷方法
request.get = (url, data, options = {}) => 
  request({ url, method: 'GET', data, ...options })

request.post = (url, data, options = {}) => 
  request({ url, method: 'POST', data, ...options })

request.put = (url, data, options = {}) => 
  request({ url, method: 'PUT', data, ...options })

request.delete = (url, data, options = {}) => 
  request({ url, method: 'DELETE', data, ...options })

module.exports = request
