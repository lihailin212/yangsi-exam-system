<template>
  <div class="invite-page">
    <div class="bg-grid"></div>
    <div class="bg-gradient"></div>

    <div class="invite-container">
      <!-- Header -->
      <div class="invite-header">
        <div class="brand-logo">
          <img v-if="settingsStore.logoUrl" :src="settingsStore.logoUrl" class="logo-img" />
          <svg v-else viewBox="0 0 100 100" class="logo-svg">
            <defs>
              <linearGradient id="inviteLogoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#14FFEC"/>
                <stop offset="100%" style="stop-color:#0D7377"/>
              </linearGradient>
            </defs>
            <circle cx="50" cy="50" r="45" fill="url(#inviteLogoGradient)"/>
            <path d="M50 25 L50 75 M30 50 L70 50" stroke="white" stroke-width="6" stroke-linecap="round"/>
          </svg>
        </div>
        <h1 class="brand-title">{{ settingsStore.systemName || '杨思学考试系统' }}</h1>
      </div>

      <!-- Exam Info Card -->
      <div class="exam-card" v-if="exam">
        <div class="exam-status-badge" :class="exam.exam_status">
          {{ statusLabel }}
        </div>
        <h2 class="exam-title">{{ exam.exam_title }}</h2>
        <div class="exam-meta">
          <span><el-icon><Timer /></el-icon> 考试时长 {{ exam.duration }} 分钟</span>
          <span><el-icon><Star /></el-icon> 及格分数 {{ exam.pass_score }} 分</span>
        </div>
      </div>

      <!-- Invalid Exam -->
      <div class="error-card" v-else-if="!loading">
        <el-icon class="error-icon"><CircleCloseFilled /></el-icon>
        <h2>考试不存在</h2>
        <p>该考试不存在或已失效，请联系管理员确认。</p>
      </div>

      <!-- Login Form -->
      <div class="login-card" v-if="exam">
        <h3 class="login-title">请先登录后再参加考试</h3>
        <el-form :model="form" :rules="rules" ref="formRef" @submit.prevent="handleLogin">
          <el-form-item prop="employee_id">
            <el-input
              v-model="form.employee_id"
              placeholder="请输入工号"
              size="large"
              :prefix-icon="User"
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              :prefix-icon="Lock"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-button
            type="primary"
            size="large"
            class="login-btn"
            @click="handleLogin"
            :loading="loading"
            :disabled="loading"
          >
            {{ loading ? '验证中...' : '登录并进入考试' }}
          </el-button>
        </el-form>
        <p class="login-tip" v-if="loginError">{{ loginError }}</p>
      </div>
    </div>

    <div class="loading-overlay" v-if="loading && !exam && !loginError">
      <el-icon class="is-loading" style="font-size: 32px; color: #409EFF;"><Loading /></el-icon>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Timer, Star, CircleCloseFilled, Loading } from '@element-plus/icons-vue'
import { getExamInfo, examLogin } from '@/api/exam'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const settingsStore = useSettingsStore()

const examId = route.params.examId
const exam = ref(null)
const loading = ref(false)
const loginError = ref('')
const formRef = ref(null)

const form = ref({ employee_id: '', password: '' })
const rules = {
  employee_id: [{ required: true, message: '请输入工号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const statusLabel = computed(() => {
  const map = {
    '未开始': '未开始',
    '进行中': '进行中',
    '已结束': '已结束',
    '可参加': '可参加',
  }
  return map[exam.value?.exam_status] || exam.value?.exam_status
})

const handleLogin = async () => {
  await formRef.value.validate()
  loading.value = true
  loginError.value = ''
  try {
    const res = await examLogin({
      exam_id: Number(examId),
      employee_id: form.value.employee_id,
      password: form.value.password,
    })
    // 保存 token 和用户信息
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('userId', res.user_id)
    localStorage.setItem('userName', res.name)
    localStorage.setItem('isAdmin', res.is_admin)
    authStore.token = res.access_token
    authStore.userId = res.user_id
    authStore.userName = res.name
    authStore.isAdmin = res.is_admin
    router.push({ path: `/exam-take/${examId}` })
  } catch (e) {
    if (e.response?.status === 403) {
      loginError.value = e.response.data.detail || '您已达到该考试的参加次数上限'
    } else {
      loginError.value = e.response?.data?.detail || '工号或密码错误，请确认您的账号有效'
    }
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    exam.value = await getExamInfo(examId)
  } catch {
    exam.value = null
  }
})
</script>

<style scoped>
.invite-page {
  min-height: 100vh;
  background: var(--dark-bg);
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(13, 115, 119, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(13, 115, 119, 0.03) 1px, transparent 1px);
  background-size: 50px 50px;
}

.bg-gradient {
  position: absolute;
  top: -30%;
  right: -10%;
  width: 60%;
  height: 80%;
  background: radial-gradient(ellipse at center, rgba(13, 115, 119, 0.15) 0%, transparent 70%);
}

.invite-container {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 440px;
  padding: 20px;
}

.invite-header {
  text-align: center;
  margin-bottom: 24px;
  animation: fadeIn 0.6s ease-out;
}

.brand-logo {
  width: 56px;
  height: 56px;
  margin: 0 auto 12px;
}

.logo-svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 0 16px rgba(20, 255, 236, 0.3));
}
.logo-img {
  width: 56px;
  height: 56px;
  object-fit: contain;
}

.brand-title {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 600;
  color: #fff;
  letter-spacing: 2px;
}

.exam-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 20px;
  text-align: center;
  animation: slideUp 0.5s ease-out;
  position: relative;
}

.exam-status-badge {
  display: inline-block;
  padding: 4px 16px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 12px;
}

.exam-status-badge.进行中 { background: rgba(64,158,255,0.2); color: #409EFF; }
.exam-status-badge.未开始 { background: rgba(144,147,153,0.2); color: #909399; }
.exam-status-badge.已结束 { background: rgba(245,108,108,0.2); color: #F56C6C; }
.exam-status-badge.可参加 { background: rgba(103,194,58,0.2); color: #67C23A; }

.exam-title {
  font-size: 20px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 12px;
  line-height: 1.4;
  word-break: break-word;
}

.exam-meta {
  display: flex;
  justify-content: center;
  gap: 16px;
  flex-wrap: wrap;
  color: rgba(255, 255, 255, 0.6);
  font-size: 13px;
}

.exam-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.login-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 24px;
  animation: slideUp 0.5s ease-out 0.1s backwards;
}

.login-title {
  font-size: 15px;
  color: rgba(255, 255, 255, 0.8);
  margin-bottom: 20px;
  text-align: center;
}

.login-card :deep(.el-form-item) {
  margin-bottom: 14px;
}

.login-card :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 4px 12px;
}

.login-card :deep(.el-input__inner) {
  color: #fff;
  font-size: 15px;
}

.login-card :deep(.el-input__inner::placeholder) {
  color: rgba(255, 255, 255, 0.3);
}

.login-card :deep(.el-input__prefix .el-icon) {
  color: rgba(255, 255, 255, 0.4);
}

.login-btn {
  width: 100%;
  height: 48px;
  font-size: 15px;
  font-weight: 500;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--primary-500), var(--primary-600));
  margin-top: 8px;
}

.login-btn:hover {
  background: linear-gradient(135deg, var(--accent-500), var(--primary-500));
}

.login-tip {
  text-align: center;
  color: #F56C6C;
  font-size: 13px;
  margin-top: 8px;
}

.error-card {
  background: rgba(245, 108, 108, 0.1);
  border: 1px solid rgba(245, 108, 108, 0.3);
  border-radius: 16px;
  padding: 32px 24px;
  text-align: center;
  animation: slideUp 0.5s ease-out;
}

.error-icon {
  font-size: 48px;
  color: #F56C6C;
  margin-bottom: 16px;
}

.error-card h2 {
  color: #fff;
  font-size: 18px;
  margin-bottom: 12px;
}

.error-card p {
  color: rgba(255, 255, 255, 0.5);
  font-size: 13px;
}

.loading-overlay {
  position: fixed;
  inset: 0;
  background: rgba(10, 15, 20, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* 移动端适配 */
@media (max-width: 480px) {
  .invite-container {
    padding: 16px;
  }

  .brand-logo {
    width: 48px;
    height: 48px;
  }

  .brand-title {
    font-size: 20px;
  }

  .exam-card {
    padding: 20px;
    border-radius: 12px;
  }

  .exam-title {
    font-size: 18px;
  }

  .exam-meta {
    gap: 12px;
    font-size: 12px;
  }

  .login-card {
    padding: 20px;
    border-radius: 12px;
  }

  .login-btn {
    height: 48px;
  }
}
</style>
