<template>
  <div class="password-form">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="0" @submit.prevent="submit">
      <el-form-item prop="old_password">
        <el-input
          v-model="form.old_password"
          type="password"
          show-password
          :placeholder="oldPlaceholder"
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
          {{ loading ? '提交中...' : submitText }}
        </el-button>
      </el-form-item>
    </el-form>

    <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Lock } from '@element-plus/icons-vue'
import { changePassword } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const props = defineProps({
  // 按钮上的文字
  submitText: { type: String, default: '保存新密码' },
  // 原密码输入框的提示语：强制改密时叫「初始密码」，自己改时叫「当前密码」
  oldPlaceholder: { type: String, default: '当前密码' },
})
const emit = defineEmits(['success'])

const authStore = useAuthStore()
const formRef = ref(null)
const loading = ref(false)
const errorMessage = ref('')

const form = ref({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const rules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
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
    errorMessage.value = ''
    try {
      await changePassword({
        old_password: form.value.old_password,
        new_password: form.value.new_password,
      })
      // 初始密码改完，把「必须改密」的标记清掉
      authStore.clearMustChangePassword()
      form.value = { old_password: '', new_password: '', confirm_password: '' }
      ElMessage.success('密码修改成功，请牢记新密码')
      emit('success')
    } catch (e) {
      // 原密码错误等由后端返回 400 + detail，这里内联展示
      errorMessage.value = e?.response?.data?.detail
        || (e?.response ? '修改失败，请检查输入' : '网络异常，请稍后重试')
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
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

.error-message {
  margin: 0 0 10px;
  text-align: center;
  font-size: 13px;
  line-height: 1.5;
  color: #F56C6C;
}
</style>
