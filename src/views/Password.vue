<template>
  <div class="password-page">
    <div class="page-header">
      <h2>修改密码</h2>
      <p class="subtitle">修改自己的登录密码，改完当前登录状态仍然有效，不用重新登录</p>
    </div>

    <el-card class="password-card">
      <div class="account-row">
        <el-icon><User /></el-icon>
        <span class="account-text">
          {{ authStore.userName }}（工号 {{ authStore.employeeId }}）
        </span>
      </div>

      <PasswordForm submit-text="保存新密码" old-placeholder="当前密码" />

      <p class="tip">
        新密码至少 8 位，建议包含字母、数字和符号。忘记密码请联系机构管理员重置。
      </p>
    </el-card>
  </div>
</template>

<script setup>
import { User } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import PasswordForm from '@/components/PasswordForm.vue'

const authStore = useAuthStore()
</script>

<style scoped>
.password-page {
  max-width: 720px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 18px;
  font-weight: 500;
  margin: 0 0 5px 0;
  color: var(--neutral-800);
}

.subtitle {
  color: var(--neutral-500);
  font-size: 14px;
  margin: 0;
}

.password-card {
  padding: 8px 12px 4px;
}

.account-row {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--neutral-600);
  font-size: 14px;
  padding: 4px 0 16px;
  border-bottom: 1px solid var(--neutral-100);
  margin-bottom: 18px;
}

.account-text {
  font-weight: 500;
  color: var(--neutral-800);
}

.tip {
  margin: 4px 0 12px;
  text-align: center;
  font-size: 12px;
  color: var(--neutral-400);
}
</style>
