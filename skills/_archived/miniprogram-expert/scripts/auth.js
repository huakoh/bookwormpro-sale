/**
 * 小程序登录授权
 * Mini Program Auth Utils
 */

const request = require('./request')

/**
 * 检查登录状态
 */
const checkLogin = () => {
  const token = wx.getStorageSync('token')
  return !!token
}

/**
 * 登录流程
 */
const login = async () => {
  try {
    // 1. 获取 code
    const { code } = await wx.login()
    
    // 2. 发送到后端换取 token
    const res = await request.post('/auth/login', { code })
    
    // 3. 存储 token 和用户信息
    wx.setStorageSync('token', res.data.token)
    wx.setStorageSync('userInfo', res.data.userInfo)
    
    return res.data
  } catch (error) {
    console.error('登录失败:', error)
    throw error
  }
}

/**
 * 静默登录（检查并自动登录）
 */
const silentLogin = async () => {
  if (checkLogin()) {
    return wx.getStorageSync('userInfo')
  }
  return login()
}

/**
 * 获取用户信息
 * 需要通过 button 触发
 */
const getUserProfile = () => {
  return new Promise((resolve, reject) => {
    wx.getUserProfile({
      desc: '用于完善用户资料',
      success: (res) => resolve(res.userInfo),
      fail: (err) => reject(err)
    })
  })
}

/**
 * 获取手机号
 * 需要通过 button open-type="getPhoneNumber" 触发
 * @param {Object} e - button 回调事件
 */
const getPhoneNumber = async (e) => {
  if (!e.detail.code) {
    throw new Error('用户拒绝授权')
  }
  
  // 发送 code 到后端解密
  const res = await request.post('/auth/phone', { code: e.detail.code })
  return res.data.phoneNumber
}

/**
 * 检查并请求授权
 * @param {string} scope - 权限范围，如 'scope.userLocation'
 */
const checkAndRequestAuth = async (scope) => {
  const { authSetting } = await wx.getSetting()
  
  // 已授权
  if (authSetting[scope]) {
    return true
  }
  
  // 之前拒绝过
  if (authSetting[scope] === false) {
    const { confirm } = await wx.showModal({
      title: '提示',
      content: '需要您的授权才能使用此功能，是否去设置？'
    })
    
    if (confirm) {
      await wx.openSetting()
      const { authSetting: newSetting } = await wx.getSetting()
      return newSetting[scope] === true
    }
    return false
  }
  
  // 首次请求
  try {
    await wx.authorize({ scope })
    return true
  } catch {
    return false
  }
}

/**
 * 退出登录
 */
const logout = () => {
  wx.removeStorageSync('token')
  wx.removeStorageSync('userInfo')
  wx.reLaunch({ url: '/pages/index/index' })
}

module.exports = {
  checkLogin,
  login,
  silentLogin,
  getUserProfile,
  getPhoneNumber,
  checkAndRequestAuth,
  logout
}
