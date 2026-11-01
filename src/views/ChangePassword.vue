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

      <el-form ref="formRef" :model="form" :rules="rules" label-width="0" @submit.prevent="submit">
        <el-form-item prop="old_password">
          <el-input
            v-model="form.old_password"
            type="password"
            show-password
            placeholder="初始密码"
            size="large"
            :prefix-icon="Lock"
          />
        </el-form-item>

        <el-form-item prop="new_password">
          <el-input
            v-model="form.new_password"
            type="password"
            show-password
            placeholder="新密码（至少 8 位）"
            size="large"
            :prefix-icon="Lock"
          />
        </el-form-item>

        <el-form-item prop="confirm_password">
          <el-input
            v-model="form.confirm_password"
            type="password"
            show-password
            placeholder="确认新密码"
            size="large"
            :prefix-icon="Lock"
            @keyup.enter="submit"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            class="submit-btn"
            :loading="loading"
            @click="submit"
          >
            {{ loading ? '提交中...' : '保存新密码' }}
          </el-button>
        </el-form-item>
      </el-form>

      <p class="tip">提示：新密码至少 8 位，建议包含字母、数字和符号</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock } from '@element-plus/icons-vue'
import { changePassword } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref(null)
const loading = ref(false)

const form = ref({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const rules = {
  old_password: [{ required: true, message: '请输入初始密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '新密码至少 8 位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== form.value.new_password) callback(new Error('两次输入的密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

const submit = () => {
  formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await changePassword({
        old_password: form.value.old_password,
        new_password: form.value.new_password,
      })
      authStore.clearMustChangePassword()
      ElMessage.success('密码修改成功，请牢记新密码')
      router.replace(authStore.isAdmin ? '/dashboard' : '/my-exams')
    } catch {
      // 错误已由 axios 拦截器提示
    } finally {
      loading.value = false
    }
  })
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

.submit-btn {
  width: 100%;
  height: 46px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 1px;
  border: none;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--primary-500), var(--primary-600));
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
