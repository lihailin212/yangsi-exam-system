import axios from 'axios'
import { ElMessage } from 'element-plus'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

const request = axios.create({
  baseURL: API_BASE,
  // 后端连的是远端库（Neon），冷启动要建表/补列/校序列，实测几十秒；
  // 15 秒太短，慢一点的请求会被当成"网络异常"。
  timeout: 60000,
})

// 后端重启期间端口是关着的，浏览器直接拿到连接失败。
// 这时候重试几次就能等到后端起来，比让用户看着"网络异常"强。
const RETRY_DELAYS = [1200, 2500, 5000]
const MAX_RETRIES = RETRY_DELAYS.length

function isRetryable(err) {
  const config = err.config || {}
  const method = (config.method || 'get').toLowerCase()
  const status = err.response?.status
  if (!err.response) {
    // 完全没拿到响应：请求多半根本没送到后端（后端正在启动/端口还没绑上）。
    // 超时不一样：请求可能已经执行过了，只对 GET 重试，免得重复交卷。
    if (err.code === 'ECONNABORTED') return method === 'get'
    return true
  }
  if ([502, 503, 504].includes(status)) return true
  // dev 代理在后端没起来时返回 500，body 是空的（不是 JSON）。
  // FastAPI 自己的 500 一定是 JSON，所以"body 不是对象"就说明是代理层挂了，
  // 这种可以重试——后端重启完就恢复。
  if (status === 500 && typeof err.response.data !== 'object') return true
  return false
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

// 把"连不上后端"翻译成人话，别一律叫网络异常
export function describeNetworkError(e) {
  if (e?.code === 'ECONNABORTED') {
    return '服务器响应超时，后端可能正在重启，请稍后重试'
  }
  const d = e?.response?.data?.detail
  if (typeof d === 'string' && d) return d
  if (d && typeof d === 'object' && d.message) return d.message
  if (e?.response) {
    // 拿到了响应但没有可读的错误内容：多半是代理/网关层挂了（后端正在重启）
    return '连不上服务器或服务器正在重启，请稍后重试'
  }
  return '连不上服务器，后端可能正在启动或已停止，请稍后重试'
}

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
  async err => {
    // 后端重启/冷启动时先重试几次，别让用户直接看到"网络异常"
    const config = err.config || {}
    const retryCount = config.__retryCount || 0
    if (retryCount < MAX_RETRIES && isRetryable(err) && !config.__noRetry) {
      config.__retryCount = retryCount + 1
      await sleep(RETRY_DELAYS[retryCount])
      return request(config)
    }

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
