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

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>数据备份与恢复</span>
          </template>
          <div class="backup-section">
            <div class="backup-info">
              <p>备份内容包括：题目、考试、考生信息、考试记录等核心数据</p>
              <p class="backup-tip">建议定期备份数据，防止意外丢失</p>
            </div>

            <div class="backup-actions">
              <el-button type="primary" @click="handleBackup" :loading="backingUp">
                <el-icon><Download /></el-icon>
                创建备份
              </el-button>
              <el-button @click="handleBackupList" :loading="loadingList">
                <el-icon><List /></el-icon>
                查看备份
              </el-button>
              <el-button type="danger" @click="showRestoreDialog = true">
                <el-icon><Upload /></el-icon>
                数据恢复
              </el-button>
            </div>

            <div v-if="backupList.length > 0" class="backup-list">
              <h4>备份记录</h4>
              <el-table :data="backupList" size="small" max-height="300">
                <el-table-column prop="filename" label="文件名" />
                <el-table-column prop="size" label="大小" width="100">
                  <template #default="{ row }">
                    {{ formatSize(row.size) }}
                  </template>
                </el-table-column>
                <el-table-column prop="created_at" label="创建时间" width="180" />
                <el-table-column label="操作" width="120" fixed="right">
                  <template #default="{ row }">
                    <el-button type="primary" size="small" link @click="downloadBackup(row.filename)">
                      下载
                    </el-button>
                    <el-button type="danger" size="small" link @click="confirmRestore(row.filename)">
                      恢复
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 恢复确认对话框 -->
    <el-dialog v-model="showRestoreDialog" title="数据恢复" width="500px">
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        accept=".json"
        :on-change="handleFileChange"
        drag
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">将备份文件拖到此处，或<em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">只能上传 JSON 格式的备份文件</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showRestoreDialog = false">取消</el-button>
        <el-button type="primary" @click="handleRestore" :loading="restoring">确认恢复</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Upload, List, UploadFilled } from '@element-plus/icons-vue'
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

// 备份相关
const backingUp = ref(false)
const loadingList = ref(false)
const restoring = ref(false)
const backupList = ref([])
const showRestoreDialog = ref(false)
const uploadRef = ref(null)
const restoreFile = ref(null)

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
  e.target.value = ''
}

// 备份功能
const handleBackup = async () => {
  backingUp.value = true
  try {
    const res = await request.get('/settings/backup')
    ElMessage.success(`备份创建成功！文件：${res.filename}`)
    // 自动下载
    downloadBackup(res.filename)
    // 刷新列表
    handleBackupList()
  } catch (e) {
    ElMessage.error('备份失败')
  } finally {
    backingUp.value = false
  }
}

const handleBackupList = async () => {
  loadingList.value = true
  try {
    backupList.value = await request.get('/settings/backup/list')
  } catch (e) {
    console.error('获取备份列表失败', e)
  } finally {
    loadingList.value = false
  }
}

const downloadBackup = (filename) => {
  const link = document.createElement('a')
  link.href = `/api/settings/backup/download?filename=${encodeURIComponent(filename)}`
  link.download = filename
  link.click()
}

const handleFileChange = (file) => {
  restoreFile.value = file.raw
}

const confirmRestore = async (filename) => {
  try {
    await ElMessageBox.confirm(
      `确定要从备份文件 "${filename}" 恢复数据吗？\n恢复操作会覆盖当前所有数据！`,
      '数据恢复',
      {
        confirmButtonText: '确定恢复',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    // 下载并上传备份文件
    try {
      const response = await fetch(`/api/settings/backup/download?filename=${encodeURIComponent(filename)}`)
      const blob = await response.blob()
      const file = new File([blob], filename, { type: 'application/json' })
      restoreFile.value = file
      await handleRestore()
    } catch (e) {
      ElMessage.error('下载备份文件失败')
    }
  } catch {
    // 用户取消
  }
}

const handleRestore = async () => {
  if (!restoreFile.value) {
    ElMessage.warning('请先选择备份文件')
    return
  }

  try {
    await ElMessageBox.confirm(
      '恢复操作将覆盖当前所有数据，确定继续吗？',
      '数据恢复',
      {
        confirmButtonText: '确定恢复',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return
  }

  restoring.value = true
  try {
    const formData = new FormData()
    formData.append('file', restoreFile.value)
    await request.post('/settings/restore', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    ElMessage.success('数据恢复成功！')
    showRestoreDialog.value = false
    restoreFile.value = null
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '恢复失败')
  } finally {
    restoring.value = false
  }
}

const formatSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
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
.backup-section { padding: 10px 0; }
.backup-info { margin-bottom: 20px; }
.backup-info p { margin: 5px 0; color: #666; }
.backup-tip { color: #E6A23C; font-size: 12px; }
.backup-actions { display: flex; gap: 10px; margin-bottom: 20px; }
.backup-list { margin-top: 20px; }
.backup-list h4 { margin: 0 0 10px 0; color: #333; }
</style>
