import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import App from './App.vue'
import router from './router'
import './assets/styles.css'
import draggableDialog from './plugins/draggableDialog'

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.use(draggableDialog)
app.mount('#app')

// 启动时拉一次全局能力开关（收费总开关 / 短信登录是否可用）。
// 路由守卫要靠它判断「订阅过期要不要拦」，所以必须在第一次导航前拿到。
// 拉取失败不影响使用：默认按「未开启收费」处理，最多是少拦一道。
import { getCapabilities } from '@/api/auth'
getCapabilities().then((caps) => {
  localStorage.setItem('billingEnabled', caps.billing_enabled ? 'true' : 'false')
  localStorage.setItem('smsLoginEnabled', caps.sms_login ? 'true' : 'false')
  localStorage.setItem('freeTrialDays', caps.free_trial_days ?? 7)
}).catch(() => {
  localStorage.setItem('billingEnabled', 'false')
  localStorage.setItem('smsLoginEnabled', 'false')
})
