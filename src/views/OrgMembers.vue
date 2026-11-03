<template>
  <div class="page">
    <el-card class="mb16" shadow="never">
      <template #header>
        <div class="card-header">
          <span>{{ orgInfo.organization?.name || '我的机构' }}</span>
          <el-button size="small" @click="load">刷新</el-button>
        </div>
      </template>
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="席位用量">
          {{ stats.seat_used ?? 0 }} / {{ stats.seat_limit ?? 0 }}
        </el-descriptions-item>
        <el-descriptions-item label="订阅到期">{{ fmt(stats.subscription_expires_at) || '未开通' }}</el-descriptions-item>
        <el-descriptions-item label="成员数">{{ stats.member_count ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="交卷记录">{{ stats.record_count ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="平均分">{{ stats.average_score ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="邀请码">
          <span class="code">{{ orgInfo.organization?.invite_code || '—' }}</span>
          <el-button size="small" text @click="rotate">重置</el-button>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>机构学员</span>
          <el-button size="small" type="primary" @click="addVisible = true">新增学员</el-button>
        </div>
      </template>

      <el-table :data="members" v-loading="loading" border size="small">
        <el-table-column prop="name" label="姓名" width="120" />
        <el-table-column prop="phone" label="手机号" width="140" />
        <el-table-column prop="employee_id" label="账号" width="140" />
        <el-table-column prop="dept" label="科室" width="120" />
        <el-table-column label="角色" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="row.org_role === 'admin' ? 'warning' : 'info'">
              {{ row.org_role === 'admin' ? '机构管理员' : '学员' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="加入时间" width="180" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="toggleActive(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
            <el-button size="small" text @click="resetPassword(row)">重置密码</el-button>
            <el-button size="small" text @click="editName(row)">改名</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="addVisible" title="新增学员" width="420px">
      <el-form :model="addForm" label-width="90px">
        <el-form-item label="手机号" required>
          <el-input v-model="addForm.phone" placeholder="11 位手机号" maxlength="11" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="addForm.name" placeholder="选填，不填自动生成" />
        </el-form-item>
        <el-form-item label="初始密码">
          <el-input v-model="addForm.password" placeholder="选填，不填系统随机生成" />
        </el-form-item>
        <el-form-item label="科室">
          <el-input v-model="addForm.dept" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleAdd">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getOrgMembers, addOrgMember, updateOrgMember, getOrgStats, rotateInviteCode } from '@/api/organizations'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const orgId = computed(() => authStore.organizationId || 0)

const members = ref([])
const stats = ref({})
const orgInfo = ref({})
const loading = ref(false)
const saving = ref(false)
const addVisible = ref(false)
const addForm = ref({ phone: '', name: '', password: '', dept: '' })

const fmt = (v) => {
  if (!v) return ''
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  return d.toLocaleString('zh-CN', { hour12: false })
}

const load = async () => {
  if (!orgId.value) {
    ElMessage.warning('当前账号没有绑定机构')
    return
  }
  loading.value = true
  try {
    const [m, s] = await Promise.all([getOrgMembers(orgId.value), getOrgStats(orgId.value)])
    members.value = m.items || []
    orgInfo.value = m
    stats.value = s
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

const handleAdd = async () => {
  if (!addForm.value.phone.trim()) {
    ElMessage.warning('请填写手机号')
    return
  }
  saving.value = true
  try {
    const res = await addOrgMember(orgId.value, addForm.value)
    ElMessage.success(`已添加${res.initial_password ? '，初始密码：' + res.initial_password : ''}`)
    addVisible.value = false
    addForm.value = { phone: '', name: '', password: '', dept: '' }
    load()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '添加失败')
  } finally {
    saving.value = false
  }
}

const toggleActive = async (row) => {
  try {
    await updateOrgMember(orgId.value, row.id, { is_active: !row.is_active })
    ElMessage.success('操作成功')
    load()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  }
}

const resetPassword = async (row) => {
  try {
    const { value } = await ElMessageBox.prompt(
      `给「${row.name}」设置新密码（至少 8 位）`, '重置密码',
      { inputType: 'password', inputPattern: /.{8,}/, inputErrorMessage: '至少 8 位' })
    await updateOrgMember(orgId.value, row.id, { password: value })
    ElMessage.success('密码已重置')
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(e?.response?.data?.detail || '重置失败')
  }
}

const editName = async (row) => {
  try {
    const { value } = await ElMessageBox.prompt('新姓名', '修改姓名', { inputValue: row.name })
    await updateOrgMember(orgId.value, row.id, { name: value })
    ElMessage.success('已修改')
    load()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(e?.response?.data?.detail || '修改失败')
  }
}

const rotate = async () => {
  try {
    const res = await rotateInviteCode(orgId.value)
    ElMessage.success('新邀请码：' + res.invite_code)
    load()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '重置失败')
  }
}

onMounted(load)
</script>

<style scoped>
.page { max-width: 1200px; margin: 0 auto; }
.mb16 { margin-bottom: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.code { font-family: monospace; font-size: 15px; letter-spacing: 1px; color: #0d7377; }
</style>
