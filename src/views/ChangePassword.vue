<template>
  <div class="change-page">
    <div class="change-card">
      <div class="change-header">
        <div class="change-icon">
          <el-icon><Lock /></el-icon>
        </div>
        <h2>修改初始密码</h2>
        <p>您当前使用的是初始密码，为保障账号安全，请先设置新密码后再使用系统</p>
      </div>

      <PasswordForm submit-text="保存新密码" old-placeholder="初始密码" @success="onSuccess" />

      <p class="tip">提示：新密码至少 8 位，建议包含字母、数字和符号</p>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import PasswordForm from '@/components/PasswordForm.vue'

const router = useRouter()
const authStore = useAuthStore()

// 强制改密（初始密码）改完后回到自己的首页
const onSuccess = () => {
  router.replace(authStore.isAdmin ? '/dashboard' : '/my-exams')
}
</script>

<style scoped>
.change-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: var(--neutral-100);
}

.change-card {
  width: 100%;
  max-width: 440px;
  background: #fff;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  padding: 40px 36px 28px;
}

.change-header {
  text-align: center;
  margin-bottom: 28px;
}

.change-icon {
  width: 56px;
  height: 56px;
  margin: 0 auto 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  color: #fff;
  background: linear-gradient(135deg, var(--primary-400), var(--primary-600));
}

.change-header h2 {
  font-size: 22px;
  font-weight: 600;
  color: var(--neutral-800);
  margin-bottom: 10px;
}

.change-header p {
  font-size: 14px;
  line-height: 1.6;
  color: var(--neutral-500);
}

.tip {
  margin-top: 4px;
  text-align: center;
  font-size: 12px;
  color: var(--neutral-400);
}

@media (max-width: 480px) {
  .change-card {
    padding: 32px 20px 24px;
  }
}
</style>
