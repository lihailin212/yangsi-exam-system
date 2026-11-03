<template>
  <div class="login-page">
    <!-- Background Elements -->
    <div class="bg-grid"></div>
    <div class="bg-gradient"></div>
    <div class="bg-glow"></div>
    
    <!-- Floating Shapes -->
    <div class="floating-shapes">
      <div class="shape shape-1"></div>
      <div class="shape shape-2"></div>
      <div class="shape shape-3"></div>
      <div class="shape shape-4"></div>
    </div>

    <!-- Login Container -->
    <div class="login-container">
      <!-- Left Side - Branding -->
      <div class="login-branding">
        <div class="brand-content">
          <div class="brand-logo">
            <img v-if="settingsStore.logoUrl" :src="settingsStore.logoUrl" class="logo-img" />
            <svg v-else viewBox="0 0 100 100" class="logo-svg">
              <defs>
                <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" style="stop-color:#14FFEC"/>
                  <stop offset="100%" style="stop-color:#0D7377"/>
                </linearGradient>
              </defs>
              <circle cx="50" cy="50" r="45" fill="url(#logoGradient)"/>
              <path d="M50 25 L50 75 M30 50 L70 50" stroke="white" stroke-width="6" stroke-linecap="round"/>
            </svg>
          </div>
          <h1 class="brand-title">{{ settingsStore.systemName || '杨思学考试系统' }}</h1>
          <p class="brand-subtitle">{{ settingsStore.hospitalName || '专业在线医学考试平台' }}</p>
          
          <div class="brand-features">
            <div class="feature-item" v-for="(feature, index) in features" :key="index">
              <div class="feature-icon">
                <el-icon><component :is="feature.icon" /></el-icon>
              </div>
              <span>{{ feature.text }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Side - Login Form -->
      <div class="login-form-wrapper">
        <div class="login-card">
          <div class="login-header">
            <h2>欢迎回来</h2>
            <p>请登录您的账户继续</p>
          </div>

          <el-tabs v-model="activeTab" class="login-tabs" :before-leave="handleTabChange">
            <el-tab-pane label="账号登录" name="account">
              <el-form :model="form" :rules="rules" ref="formRef" class="login-form" @submit.prevent="handleLogin">
                <div class="form-group">
                  <label class="form-label">工号 / 手机号</label>
                  <el-form-item prop="employee_id">
                    <el-input 
                      v-model="form.employee_id" 
                      placeholder="请输入工号或手机号" 
                      size="large"
                      :prefix-icon="User"
                      class="custom-input"
                    />
                  </el-form-item>
                </div>

                <div class="form-group">
                  <label class="form-label">密码</label>
                  <el-form-item prop="password">
                    <el-input 
                      v-model="form.password" 
                      type="password" 
                      placeholder="请输入密码" 
                      size="large"
                      :prefix-icon="Lock"
                      show-password
                      class="custom-input"
                      @keyup.enter="handleLogin"
                    />
                  </el-form-item>
                </div>

                <el-form-item>
                  <el-button 
                    type="primary" 
                    size="large" 
                    class="login-btn" 
                    @click="handleLogin" 
                    :loading="loading"
                    :disabled="loading"
                  >
                    <span v-if="!loading">登 录</span>
                    <span v-else class="loading-text">登录中...</span>
                  </el-button>
                </el-form-item>

                <p v-if="loginError" class="login-error">{{ loginError }}</p>
              </el-form>
            </el-tab-pane>

            <el-tab-pane label="扫码登录" name="qrcode">
              <div class="qrcode-area">
                <div class="qrcode-container">
                  <div class="qrcode-wrapper">
                    <div ref="qrcodeRef" class="qrcode-img"></div>
                  </div>
                  <div class="qrcode-decoration">
                    <div class="qrcode-corner tl"></div>
                    <div class="qrcode-corner tr"></div>
                    <div class="qrcode-corner bl"></div>
                    <div class="qrcode-corner br"></div>
                  </div>
                </div>
                <p class="qrcode-tip">使用手机扫描二维码</p>
                <p class="qrcode-url">{{ currentUrl }}</p>
              </div>
            </el-tab-pane>

            <el-tab-pane label="验证码登录" name="sms" :disabled="!smsEnabled">
              <el-form :model="smsForm" class="login-form" @submit.prevent="handleSmsLogin">
                <div class="form-group">
                  <label class="form-label">手机号</label>
                  <el-form-item prop="phone">
                    <el-input
                      v-model="smsForm.phone"
                      placeholder="请输入手机号"
                      size="large"
                      :prefix-icon="Iphone"
                      class="custom-input"
                    />
                  </el-form-item>
                </div>

                <div class="form-group">
                  <label class="form-label">验证码</label>
                  <el-form-item prop="code">
                    <el-input
                      v-model="smsForm.code"
                      placeholder="请输入验证码"
                      size="large"
                      class="custom-input"
                      @keyup.enter="handleSmsLogin"
                    >
                      <template #append>
                        <el-button
                          :disabled="smsCountdown > 0 || smsSending"
                          @click="handleSendSmsCode"
                        >{{ smsCountdown > 0 ? smsCountdown + 's' : '获取验证码' }}</el-button>
                      </template>
                    </el-input>
                  </el-form-item>
                </div>

                <el-form-item>
                  <el-button
                    type="primary"
                    size="large"
                    class="login-btn"
                    @click="handleSmsLogin"
                    :loading="loading"
                    :disabled="loading"
                  >
                    <span v-if="!loading">登 录</span>
                    <span v-else class="loading-text">登录中...</span>
                  </el-button>
                </el-form-item>

                <p v-if="smsError" class="login-error">{{ smsError }}</p>
              </el-form>
            </el-tab-pane>
          </el-tabs>

          <p v-if="!smsEnabled" class="login-hint">
            短信验证码登录即将开放，请先用工号或手机号登录
          </p>
        </div>

        <!-- Footer -->
        <div class="login-footer">
          <p>© 2024 {{ settingsStore.systemName || '杨思学考试系统' }}</p>
          <p class="register-tip">
            没有账号？<a @click="goRegister">立即注册</a>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import { sendSmsCode, smsLogin } from '@/api/auth'
import { User, Lock, Check, TrendCharts, DataLine, Medal, Iphone } from '@element-plus/icons-vue'

const router = useRouter()
const authStore = useAuthStore()
const settingsStore = useSettingsStore()
const formRef = ref(null)
const loading = ref(false)
const loginError = ref('')
const activeTab = ref('account')
const qrcodeRef = ref(null)
const currentUrl = ref(window.location.origin + window.location.pathname)

const form = ref({ employee_id: '', password: '' })
const rules = {
  employee_id: [{ required: true, message: '请输入工号或手机号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

// ---- 短信验证码登录（服务端未开通短信时禁用这个 Tab）----
const smsEnabled = ref(localStorage.getItem('smsLoginEnabled') === 'true')
const smsSending = ref(false)
const smsCountdown = ref(0)
const smsError = ref('')
const smsForm = ref({ phone: '', code: '' })
let smsTimer = null

const features = [
  { icon: Check, text: '智能题库管理' },
  { icon: TrendCharts, text: '数据分析可视化' },
  { icon: Medal, text: '专业考试认证' },
]

const handleLogin = () => {
  formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    loginError.value = ''
    try {
      const res = await authStore.doLogin(form.value.employee_id, form.value.password)
      afterLogin(res)
    } catch (e) {
      // 登录接口的错误不走全局拦截器（避免被当成 token 失效跳走），这里直接展示
      loginError.value = e?.response?.data?.detail
        || (e?.response ? '登录失败，请检查工号和密码' : '网络异常，请稍后重试')
    } finally {
      loading.value = false
    }
  })
}

// 登录成功后统一处理：初始密码强制改密 / 按角色进首页
const afterLogin = (res) => {
  if (res.must_change_password) {
    // 初始密码首次登录：先去改密码，改完才能用系统
    ElMessage.warning('首次登录，请先修改初始密码')
    router.push('/change-password')
  } else {
    ElMessage.success({ message: '登录成功，欢迎回来！', duration: 2000 })
    router.push(res.is_admin ? '/dashboard' : '/my-exams')
  }
}

const goRegister = () => {
  router.push('/register')
}

const handleSendSmsCode = async () => {
  const phone = (smsForm.value.phone || '').trim()
  if (!/^1[3-9]\d{9}$/.test(phone)) {
    ElMessage.warning('请输入正确的 11 位手机号')
    return
  }
  smsSending.value = true
  try {
    await sendSmsCode(phone)
    ElMessage.success('验证码已发送')
    smsCountdown.value = 60
    if (smsTimer) clearInterval(smsTimer)
    smsTimer = setInterval(() => {
      smsCountdown.value -= 1
      if (smsCountdown.value <= 0 && smsTimer) {
        clearInterval(smsTimer)
        smsTimer = null
      }
    }, 1000)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '验证码发送失败')
  } finally {
    smsSending.value = false
  }
}

const handleSmsLogin = async () => {
  const phone = (smsForm.value.phone || '').trim()
  const code = (smsForm.value.code || '').trim()
  if (!/^1[3-9]\d{9}$/.test(phone)) {
    ElMessage.warning('请输入正确的 11 位手机号')
    return
  }
  if (!code) {
    ElMessage.warning('请输入验证码')
    return
  }
  loading.value = true
  smsError.value = ''
  try {
    const res = await smsLogin({ phone, code })
    authStore.applySession(res)
    afterLogin(res)
  } catch (e) {
    smsError.value = e?.response?.data?.detail || '登录失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

const handleTabChange = (activeName) => {
  if (activeName === 'qrcode') {
    setTimeout(generateQrcode, 100)
  }
  return true
}

const generateQrcode = async () => {
  if (!qrcodeRef.value) return
  try {
    const QRCode = (await import('qrcode')).default
    qrcodeRef.value.innerHTML = ''
    const canvas = document.createElement('canvas')
    await QRCode.toCanvas(canvas, currentUrl.value, { 
      width: 180, 
      margin: 2,
      color: {
        dark: '#0D7377',
        light: '#ffffff'
      }
    })
    qrcodeRef.value.appendChild(canvas)
  } catch (e) {
    qrcodeRef.value.innerHTML = '<p style="color:#999">二维码生成失败</p>'
  }
}

watch(activeTab, handleTabChange)

onMounted(() => {
  // main.js 启动时会拉一次全局能力开关，这里同步一次最新值
  smsEnabled.value = localStorage.getItem('smsLoginEnabled') === 'true'
})

onUnmounted(() => {
  if (smsTimer) clearInterval(smsTimer)
})
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  background: var(--dark-bg);
}

/* Background Elements */
.bg-grid {
  position: absolute;
  inset: 0;
  background-image: 
    linear-gradient(rgba(13, 115, 119, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(13, 115, 119, 0.03) 1px, transparent 1px);
  background-size: 50px 50px;
  pointer-events: none;
}

.bg-gradient {
  position: absolute;
  top: -50%;
  right: -20%;
  width: 80%;
  height: 100%;
  background: radial-gradient(ellipse at center, rgba(13, 115, 119, 0.15) 0%, transparent 70%);
  pointer-events: none;
}

.bg-glow {
  position: absolute;
  bottom: -30%;
  left: -10%;
  width: 60%;
  height: 80%;
  background: radial-gradient(ellipse at center, rgba(20, 255, 236, 0.08) 0%, transparent 60%);
  pointer-events: none;
}

/* Floating Shapes */
.floating-shapes {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}

.shape {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  animation: float 8s ease-in-out infinite;
}

.shape-1 {
  width: 300px;
  height: 300px;
  background: rgba(13, 115, 119, 0.3);
  top: 10%;
  left: 5%;
  animation-delay: 0s;
}

.shape-2 {
  width: 200px;
  height: 200px;
  background: rgba(20, 255, 236, 0.2);
  top: 60%;
  right: 10%;
  animation-delay: -2s;
}

.shape-3 {
  width: 150px;
  height: 150px;
  background: rgba(13, 115, 119, 0.25);
  bottom: 20%;
  left: 15%;
  animation-delay: -4s;
}

.shape-4 {
  width: 100px;
  height: 100px;
  background: rgba(20, 255, 236, 0.15);
  top: 30%;
  right: 30%;
  animation-delay: -6s;
}

/* Login Container */
.login-container {
  display: flex;
  min-height: 100vh;
  position: relative;
  z-index: 1;
}

/* Branding Side */
.login-branding {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-8);
  background: linear-gradient(135deg, rgba(13, 115, 119, 0.1) 0%, transparent 100%);
}

.brand-content {
  max-width: 400px;
  animation: slideUp 0.8s ease-out;
}

.brand-logo {
  width: 80px;
  height: 80px;
  margin-bottom: var(--space-6);
  animation: float 4s ease-in-out infinite;
}

.logo-svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 0 20px rgba(20, 255, 236, 0.3));
}
.logo-img {
  width: 80px;
  height: 80px;
  object-fit: contain;
}

.brand-title {
  font-family: var(--font-display);
  font-size: 48px;
  font-weight: 700;
  color: #fff;
  margin-bottom: var(--space-2);
  letter-spacing: 4px;
}

.brand-subtitle {
  font-size: 18px;
  color: var(--neutral-400);
  margin-bottom: var(--space-10);
}

.brand-features {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.feature-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--neutral-300);
  font-size: 15px;
  animation: slideUp 0.8s ease-out backwards;
}

.feature-item:nth-child(1) { animation-delay: 0.2s; }
.feature-item:nth-child(2) { animation-delay: 0.3s; }
.feature-item:nth-child(3) { animation-delay: 0.4s; }

.feature-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--primary-500), var(--accent-500));
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 16px;
}

/* Form Side */
.login-form-wrapper {
  width: 520px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-8);
  animation: fadeIn 0.6s ease-out 0.2s backwards;
}

.login-card {
  width: 100%;
  max-width: 400px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-lg);
  padding: var(--space-10);
  backdrop-filter: blur(20px);
}

.login-header {
  text-align: center;
  margin-bottom: var(--space-8);
}

.login-header h2 {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 600;
  color: #fff;
  margin-bottom: var(--space-2);
}

.login-header p {
  color: var(--neutral-400);
  font-size: 14px;
}

/* Tabs */
.login-tabs {
  margin-top: var(--space-4);
}

.login-tabs :deep(.el-tabs__header) {
  margin-bottom: var(--space-6);
}

.login-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.login-tabs :deep(.el-tabs__active-bar) {
  height: 3px;
  border-radius: var(--radius-full);
  background: linear-gradient(90deg, var(--primary-500), var(--accent-500));
}

.login-tabs :deep(.el-tabs__item) {
  color: var(--neutral-400);
  font-size: 15px;
  padding: 0 var(--space-6);
  height: 44px;
  line-height: 44px;
}

.login-tabs :deep(.el-tabs__item.is-active) {
  color: #fff;
  font-weight: 500;
}

.login-tabs :deep(.el-tabs__item:hover) {
  color: var(--neutral-200);
}

/* Form Styles */
.login-form {
  margin-top: var(--space-4);
}

.form-group {
  margin-bottom: var(--space-4);
}

.form-label {
  display: block;
  font-size: 13px;
  color: var(--neutral-300);
  margin-bottom: var(--space-2);
}

.login-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.login-form :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-4);
  transition: all var(--transition-fast);
}

.login-form :deep(.el-input__wrapper:hover) {
  border-color: var(--primary-400);
}

.login-form :deep(.el-input__wrapper.is-focus) {
  background: rgba(255, 255, 255, 0.08);
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px rgba(13, 115, 119, 0.2) !important;
}

.login-form :deep(.el-input__inner) {
  color: #fff;
  font-size: 15px;
}

.login-form :deep(.el-input__inner::placeholder) {
  color: var(--neutral-500);
}

.login-form :deep(.el-input__prefix .el-icon) {
  color: var(--neutral-500);
  font-size: 16px;
}

/* Login Button */
.login-btn {
  width: 100%;
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 2px;
  border: none;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--primary-500), var(--primary-600));
  color: #fff;
  cursor: pointer;
  transition: all var(--transition-base);
  margin-top: var(--space-4);
  position: relative;
  overflow: hidden;
}

.login-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, var(--accent-500), var(--primary-500));
  opacity: 0;
  transition: opacity var(--transition-base);
}

.login-btn:hover::before {
  opacity: 1;
}

.login-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(13, 115, 119, 0.4);
}

.login-btn:active {
  transform: translateY(0);
}

.login-btn:disabled {
  cursor: not-allowed;
  transform: none;
}

.loading-text {
  position: relative;
  z-index: 1;
}

/* SMS 提示 */
.login-hint {
  margin-top: var(--space-3);
  text-align: center;
  font-size: 13px;
  color: var(--neutral-400);
}

/* 注册引导 */
.register-tip {
  margin-top: var(--space-2);
  font-size: 13px;
  color: var(--neutral-400);
}

.register-tip a {
  color: var(--primary-400);
  cursor: pointer;
  text-decoration: underline;
}

.register-tip a:hover {
  color: var(--primary-500);
}

/* Error Tip */
.login-error {
  margin-top: var(--space-3);
  text-align: center;
  font-size: 13px;
  line-height: 1.5;
  color: #F56C6C;
}

/* QR Code Area */
.qrcode-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-6) 0;
}

.qrcode-container {
  position: relative;
  padding: var(--space-4);
}

.qrcode-wrapper {
  background: #fff;
  border-radius: var(--radius-md);
  padding: var(--space-3);
  position: relative;
  z-index: 1;
}

.qrcode-img canvas {
  display: block;
}

.qrcode-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.qrcode-corner {
  position: absolute;
  width: 24px;
  height: 24px;
  border: 3px solid var(--primary-500);
}

.qrcode-corner.tl { top: 0; left: 0; border-right: none; border-bottom: none; border-radius: var(--radius-sm) 0 0 0; }
.qrcode-corner.tr { top: 0; right: 0; border-left: none; border-bottom: none; border-radius: 0 var(--radius-sm) 0 0; }
.qrcode-corner.bl { bottom: 0; left: 0; border-right: none; border-top: none; border-radius: 0 0 0 var(--radius-sm); }
.qrcode-corner.br { bottom: 0; right: 0; border-left: none; border-top: none; border-radius: 0 0 var(--radius-sm) 0; }

.qrcode-tip {
  font-size: 14px;
  color: var(--neutral-300);
  margin-top: var(--space-4);
}

.qrcode-url {
  font-size: 12px;
  color: var(--neutral-500);
  margin-top: var(--space-2);
  word-break: break-all;
  text-align: center;
  max-width: 280px;
}

/* Footer */
.login-footer {
  margin-top: var(--space-8);
  text-align: center;
}

.login-footer p {
  font-size: 12px;
  color: var(--neutral-500);
}

/* Responsive */
@media (max-width: 900px) {
  .login-container {
    flex-direction: column;
  }

  .login-branding {
    padding: var(--space-6);
    min-height: auto;
    padding: 40px 20px;
  }

  .brand-content {
    text-align: center;
  }

  .brand-features {
    align-items: center;
  }

  .brand-title {
    font-size: 36px;
  }

  .login-form-wrapper {
    width: 100%;
    padding: var(--space-6);
    min-height: auto;
    padding: 32px 20px 40px;
  }
}

@media (max-width: 480px) {
  .login-card {
    padding: 24px 20px;
    border-radius: 12px;
  }

  .login-header h2 {
    font-size: 22px;
  }

  .brand-logo {
    width: 56px;
    height: 56px;
  }

  .brand-title {
    font-size: 24px;
    letter-spacing: 2px;
  }

  .brand-subtitle {
    font-size: 14px;
    margin-bottom: 32px;
  }

  .brand-features {
    display: none;
  }

  .login-form-wrapper {
    padding: 24px 16px 32px;
  }

  .login-btn {
    height: 48px;
    font-size: 15px;
  }

  .login-tabs :deep(.el-tabs__item) {
    font-size: 14px;
    padding: 0 16px;
  }

  .qrcode-tip {
    font-size: 13px;
  }

  .qrcode-url {
    font-size: 11px;
    max-width: 240px;
  }

  .login-footer {
    margin-top: 24px;
  }
}

@media (max-width: 360px) {
  .login-card {
    padding: 20px 16px;
  }

  .brand-title {
    font-size: 20px;
  }

  .login-header h2 {
    font-size: 20px;
  }
}
</style>
