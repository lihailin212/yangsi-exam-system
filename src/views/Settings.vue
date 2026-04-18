<template>
  <div class="settings-page">
    <div class="page-header">
      <h2>系统设置</h2>
    </div>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header>基本信息</template>
          <el-form :model="form" label-width="120px">
            <el-form-item label="系统名称">
              <el-input v-model="form.system_name" />
            </el-form-item>
            <el-form-item label="医院名称">
              <el-input v-model="form.hospital_name" />
            </el-form-item>
            <el-form-item label="系统Logo">
              <div class="logo-upload">
                <div class="logo-uploader" @click="logoInput.click()">
                  <img v-if="form.logo_url" :src="form.logo_url" class="logo-image" />
                  <el-icon v-else class="logo-uploader-icon"><Plus /></el-icon>
                </div>
                <input
                  ref="logoInput"
                  type="file"
                  accept="image/*"
                  style="display:none"
                  @change="handleLogoChange"
                />
                <span class="logo-tip">建议尺寸 200x60 像素，支持 JPG、PNG 格式</span>
              </div>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSave" :loading="saving">保存设置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header>考试设置</template>
          <el-form :model="form" label-width="140px">
            <el-form-item label="显示答案解析">
              <el-switch v-model="form.exam_show_analysis" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSave" :loading="saving">保存设置</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card style="margin-top: 20px">
          <template #header>通知设置</template>
          <el-form :model="form" label-width="140px">
            <el-form-item label="考试开始提醒">
              <el-switch v-model="form.notify_exam_start" />
            </el-form-item>
            <el-form-item label="成绩发布通知">
              <el-switch v-model="form.notify_score_release" />
            </el-form-item>
            <el-form-item label="课程更新通知">
              <el-switch v-model="form.notify_course_update" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSave" :loading="saving">保存设置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings, updateSettings } from '@/api/settings'
import request from '@/api/index'

const saving = ref(false)
const logoInput = ref(null)
const form = ref({
  system_name: '杨思学考试系统',
  hospital_name: '',
  logo_url: '',
  exam_show_analysis: true,
  notify_exam_start: true,
  notify_score_release: true,
  notify_course_update: false,
})

const loadSettings = async () => {
  try {
    const data = await getSettings()
    if (data && Object.keys(data).length > 0) {
      form.value = { ...form.value, ...data }
    }
  } catch (e) {
    console.error('Failed to load settings:', e)
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    await updateSettings(form.value)
    ElMessage.success('设置已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleLogoChange = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.error('只能上传图片文件')
    return
  }
  if (file.size / 1024 / 1024 > 2) {
    ElMessage.error('图片大小不能超过 2MB')
    return
  }
  const formData = new FormData()
  formData.append('file', file)
  try {
    const res = await request.post('/upload/image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    form.value.logo_url = res.data?.url || res.url
  } catch (e) {
    ElMessage.error('上传失败')
  }
  // 清空 input，允许重复选择同一文件
  e.target.value = ''
}

onMounted(loadSettings)
</script>

<style scoped>
.settings-page { padding: 20px; }
.page-header { margin-bottom: 20px; }
.page-header h2 { font-size: 18px; font-weight: 500; }
.logo-upload { display: flex; align-items: center; gap: 16px; }
.logo-uploader { width: 120px; height: 60px; border: 1px dashed #d9d9d9; border-radius: 4px; cursor: pointer; overflow: hidden; display: flex; align-items: center; justify-content: center; }
.logo-uploader:hover { border-color: #409EFF; }
.logo-uploader-icon { font-size: 24px; color: #8c939d; }
.logo-image { width: 100%; height: 100%; object-fit: contain; }
.logo-tip { font-size: 12px; color: #909399; }
</style>
