import axios from 'axios'
import { ElMessage } from 'element-plus'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

const request = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
})

request.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 清空本地登录态（token 失效时用）
const clearAuthStorage = () => {
  ['token', 'userId', 'userName', 'isAdmin', 'employeeId', 'mustChangePassword',
   'organizationId', 'organizationName', 'orgRole', 'trialExpiresAt', 'entitlementActive']
    .forEach(k => localStorage.removeItem(k))
  // 同步清掉 Pinia 里的登录态（动态引入，避免与 stores/auth 形成循环依赖）
  import('@/stores/auth')
    .then(({ useAuthStore }) => useAuthStore().logout())
    .catch(() => {})
}

// 并发请求同时 401 时，只提示一次、只跳一次
let handlingUnauthorized = false

request.interceptors.response.use(
  res => res.data,
  err => {
    const status = err.response?.status
    // skipAuthRedirect：登录类接口的 401 表示"工号或密码错误"，
    //   不能当成 token 失效去清 token + 跳转，否则错误提示会被吞掉。
    // silent：错误由页面自行内联展示，不再弹全局 toast，避免重复提示。
    const skipAuthRedirect = err.config?.skipAuthRedirect
    const silent = err.config?.silent

    if (status === 402) {
      // 订阅过期/未开通：不清登录态（成绩记录还要能查），只把用户领到订阅页
      if (!silent) {
        const d = err.response?.data?.detail
        ElMessage.warning(typeof d === 'string' ? d : (d?.message || '订阅已过期或未开通'))
      }
      if (!window.location.hash.startsWith('#/subscribe')) {
        window.location.hash = '#/subscribe'
      }
      return Promise.reject(err)
    } else if (status === 401 && !skipAuthRedirect) {
      // 已登录后的接口返回 401：token 失效/过期
      if (!handlingUnauthorized) {
        handlingUnauthorized = true
        clearAuthStorage()
        ElMessage.warning('登录已过期，请重新登录')
        if (!window.location.hash.startsWith('#/login')) {
          window.location.hash = '#/login'
        }
        setTimeout(() => { handlingUnauthorized = false }, 1000)
      }
    } else if (!silent) {
      ElMessage.error(err.response?.data?.detail || '请求失败')
    }
    return Promise.reject(err)
  }
)

export default request
