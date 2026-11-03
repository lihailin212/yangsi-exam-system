<template>
  <div class="register-page">
    <div class="register-card">
      <div class="register-header">
        <h2>注册新账号</h2>
        <p>使用手机号注册，注册后赠免费试用</p>
      </div>

      <el-form :model="form" :rules="rules" ref="formRef" label-position="top">
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入 11 位手机号" maxlength="11" clearable />
        </el-form-item>
        <el-form-item label="姓名（选填）" prop="name">
          <el-input v-model="form.name" placeholder="真实姓名，方便成绩统计" clearable />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="至少 8 位" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm">
          <el-input v-model="form.confirm" type="password" placeholder="再输入一次" show-password />
        </el-form-item>
        <el-form-item label="机构邀请码（选填）" prop="invite_code">
          <el-input v-model="form.invite_code" placeholder="有邀请码会自动加入该机构" clearable />
          <div class="tip">没有邀请码也能注册，账号会进入待分配池，由机构管理员或管理员分配。</div>
        </el-form-item>

        <div v-if="error" class="error">{{ error }}</div>

        <el-button type="primary" class="submit" :loading="loading" @click="handleRegister">
          注册并登录
        </el-button>
        <div class="links">
          <span>已有账号？</span>
          <a @click="$router.push('/login')">返回登录</a>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref(null)
const loading = ref(false)
const error = ref('')

const form = ref({ phone: '', name: '', password: '', confirm: '', invite_code: '' })

const rules = {
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少 8 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再输入一次密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== form.value.password) callback(new Error('两次输入的密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

const handleRegister = () => {
  formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    error.value = ''
    try {
      const res = await authStore.doRegister({
        phone: form.value.phone.trim(),
        name: form.value.name.trim(),
        password: form.value.password,
        invite_code: form.value.invite_code.trim(),
      })
      ElMessage.success(res.organization_name
        ? `注册成功，已加入「${res.organization_name}」`
        : '注册成功')
      router.push('/my-exams')
    } catch (e) {
      error.value = e?.response?.data?.detail || '注册失败，请稍后重试'
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0d7377 0%, #14ffec 100%);
  padding: 24px;
}
.register-card {
  width: 100%;
  max-width: 440px;
  background: #fff;
  border-radius: 14px;
  padding: 32px 28px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18);
}
.register-header { text-align: center; margin-bottom: 20px; }
.register-header h2 { margin: 0 0 6px; font-size: 22px; color: #16333b; }
.register-header p { margin: 0; font-size: 13px; color: #7b8c93; }
.tip { font-size: 12px; color: #95a5a6; line-height: 1.5; margin-top: 4px; }
.error {
  color: #f56c6c;
  font-size: 13px;
  margin-bottom: 12px;
  background: #fef0f0;
  padding: 8px 12px;
  border-radius: 6px;
}
.submit { width: 100%; margin-top: 4px; }
.links {
  margin-top: 16px;
  text-align: center;
  font-size: 13px;
  color: #7b8c93;
}
.links a { color: #0d7377; cursor: pointer; margin-left: 6px; }
</style>
