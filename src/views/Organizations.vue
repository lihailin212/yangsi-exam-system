<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>机构管理</span>
          <div>
            <el-button size="small" @click="loadOrgs">刷新</el-button>
            <el-button size="small" type="primary" @click="openCreate">新建机构</el-button>
          </div>
        </div>
      </template>

      <el-table :data="orgs" v-loading="loading" border size="small">
        <el-table-column prop="name" label="机构名称" min-width="150" />
        <el-table-column prop="invite_code" label="邀请码" width="110" />
        <el-table-column label="席位" width="100">
          <template #default="{ row }">
            <span :class="{ over: row.seat_used > row.seat_limit }">
              {{ row.seat_used }} / {{ row.seat_limit }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="订阅到期" width="180">
          <template #default="{ row }">{{ fmt(row.subscription_expires_at) || '未开通' }}</template>
        </el-table-column>
        <el-table-column prop="subscription_plan_code" label="套餐" width="120" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="contact_name" label="联系人" width="110" />
        <el-table-column prop="contact_phone" label="联系电话" width="130" />
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="openGrant(row)">开通/续费</el-button>
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" @click="openMembers(row)">成员</el-button>
            <el-button size="small" @click="openAssign(row)">机构管理员</el-button>
            <el-button size="small" text @click="rotateCode(row)">重置邀请码</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建机构 -->
    <el-dialog v-model="createVisible" title="新建机构" width="480px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="机构名称" required>
          <el-input v-model="createForm.name" placeholder="如：XX医院" />
        </el-form-item>
        <el-form-item label="席位数">
          <el-input-number v-model="createForm.seat_limit" :min="0" :max="9999" />
          <span class="tip">可用的学员账号总数</span>
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="createForm.contact_name" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="createForm.contact_phone" />
        </el-form-item>
        <el-form-item label="同时开通">
          <el-select v-model="createForm.plan_id" clearable placeholder="可选：创建时一并开通订阅">
            <el-option v-for="p in plans" :key="p.id" :label="`${p.name}（${p.seat_limit}席/${p.duration_days}天）`"
                       :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑机构 -->
    <el-dialog v-model="editVisible" title="编辑机构" width="460px">
      <el-form :model="editForm" label-width="110px">
        <el-form-item label="机构名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="席位数">
          <el-input-number v-model="editForm.seat_limit" :min="0" :max="9999" />
          <span class="tip">可用的学员账号总数</span>
        </el-form-item>
        <el-form-item label="订阅到期日">
          <el-date-picker
            v-model="editForm.subscription_expires_at"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="留空表示未开通"
            style="width:100%"
          />
          <span class="tip">手工改期（退款/纠错用）；正常开通请用「开通/续费」</span>
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="editForm.contact_name" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="editForm.contact_phone" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="editForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 开通/续费 -->
    <el-dialog v-model="grantVisible" title="开通 / 续费" width="460px">
      <el-form :model="grantForm" label-width="110px">
        <el-form-item label="机构">
          <span>{{ currentOrg?.name }}</span>
        </el-form-item>
        <el-form-item label="套餐">
          <el-select v-model="grantForm.plan_id" clearable placeholder="选择套餐">
            <el-option v-for="p in plans" :key="p.id" :label="`${p.name}（${p.seat_limit}席/${p.duration_days}天/￥${(p.price_cents/100).toFixed(0)}）`"
                       :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="有效期天数">
          <el-input-number v-model="grantForm.duration_days" :min="0" :max="3650" />
          <span class="tip">选了套餐就按套餐的来；这里填 0 表示用套餐时长</span>
        </el-form-item>
        <el-form-item label="席位数">
          <el-input-number v-model="grantForm.seat_limit" :min="0" :max="9999" />
          <span class="tip">填 0 表示用套餐席位数；续期只会扩容不会缩容</span>
        </el-form-item>
        <el-form-item label="金额（元）">
          <el-input-number v-model="grantAmount" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="grantForm.note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="grantVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleGrant">确认开通</el-button>
      </template>
    </el-dialog>

    <!-- 成员 -->
    <el-dialog v-model="memberVisible" title="机构成员" width="720px">
      <el-table :data="members" v-loading="memberLoading" border size="small">
        <el-table-column prop="name" label="姓名" width="110" />
        <el-table-column prop="phone" label="手机号" width="140" />
        <el-table-column prop="dept" label="科室" width="110" />
        <el-table-column label="角色" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="row.org_role === 'admin' ? 'warning' : 'info'">
              {{ row.org_role === 'admin' ? '机构管理员' : '学员' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" text @click="toggleActive(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
            <el-button size="small" text @click="resetPassword(row)">重置密码</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="tip">席位：{{ memberSeatUsed }} / {{ memberSeatLimit }}</div>
    </el-dialog>

    <!-- 指定机构管理员 -->
    <el-dialog v-model="assignVisible" title="指定机构管理员" width="420px">
      <el-select v-model="assignUserId" placeholder="选择一位机构成员" style="width: 100%">
        <el-option v-for="m in members" :key="m.id" :label="`${m.name}（${m.phone || m.employee_id}）`"
                   :value="m.id" />
      </el-select>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleAssign">设为机构管理员</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getOrganizations, createOrganization, grantOrganization, rotateInviteCode, updateOrganization,
  getOrgMembers, updateOrgMember,
} from '@/api/organizations'
import { getAdminPlans } from '@/api/billing'

const orgs = ref([])
const plans = ref([])
const members = ref([])
const loading = ref(false)
const saving = ref(false)
const memberLoading = ref(false)
const memberSeatUsed = ref(0)
const memberSeatLimit = ref(0)
const currentOrg = ref(null)

const createVisible = ref(false)
const createForm = ref({ name: '', seat_limit: 20, contact_name: '', contact_phone: '', plan_id: null })

const editVisible = ref(false)
const editForm = ref({
  id: null, name: '', seat_limit: 0, contact_name: '', contact_phone: '',
  is_active: true, subscription_expires_at: '',
})

const grantVisible = ref(false)
const grantAmount = ref(0)
const grantForm = ref({ plan_id: null, duration_days: 0, seat_limit: 0, note: '' })

const memberVisible = ref(false)
const assignVisible = ref(false)
const assignUserId = ref(null)

const fmt = (v) => {
  if (!v) return ''
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  return d.toLocaleString('zh-CN', { hour12: false })
}

const loadOrgs = async () => {
  loading.value = true
  try {
    const res = await getOrganizations()
    orgs.value = res.items || []
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

const loadPlans = async () => {
  try {
    const res = await getAdminPlans()
    plans.value = res.items || []
  } catch (e) { /* 忽略 */ }
}

const openCreate = () => {
  createForm.value = { name: '', seat_limit: 20, contact_name: '', contact_phone: '', plan_id: null }
  createVisible.value = true
}

const handleCreate = async () => {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请填写机构名称')
    return
  }
  saving.value = true
  try {
    await createOrganization(createForm.value)
    ElMessage.success('机构已创建')
    createVisible.value = false
    loadOrgs()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '创建失败')
  } finally {
    saving.value = false
  }
}

const openEdit = (row) => {
  editForm.value = {
    id: row.id,
    name: row.name,
    seat_limit: row.seat_limit,
    contact_name: row.contact_name || '',
    contact_phone: row.contact_phone || '',
    is_active: !!row.is_active,
    subscription_expires_at: row.subscription_expires_at
      ? String(row.subscription_expires_at).slice(0, 10) : '',
  }
  editVisible.value = true
}

const handleEdit = async () => {
  saving.value = true
  try {
    await updateOrganization(editForm.value.id, {
      name: editForm.value.name,
      seat_limit: editForm.value.seat_limit,
      contact_name: editForm.value.contact_name,
      contact_phone: editForm.value.contact_phone,
      is_active: editForm.value.is_active,
      subscription_expires_at: editForm.value.subscription_expires_at || null,
    })
    ElMessage.success('机构已更新')
    editVisible.value = false
    loadOrgs()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const openGrant = (row) => {
  currentOrg.value = row
  grantForm.value = { plan_id: null, duration_days: 0, seat_limit: 0, note: '' }
  grantAmount.value = 0
  grantVisible.value = true
}

const handleGrant = async () => {
  if (!grantForm.value.plan_id && !grantForm.value.duration_days) {
    ElMessage.warning('请选择套餐或填写有效期天数')
    return
  }
  saving.value = true
  try {
    const payload = {
      plan_id: grantForm.value.plan_id || null,
      duration_days: grantForm.value.duration_days || null,
      seat_limit: grantForm.value.seat_limit || null,
      amount_cents: Math.round((grantAmount.value || 0) * 100),
      note: grantForm.value.note,
    }
    const res = await grantOrganization(currentOrg.value.id, payload)
    ElMessage.success('已开通：到期时间 ' + fmt(res.subscription_expires_at))
    grantVisible.value = false
    loadOrgs()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '开通失败')
  } finally {
    saving.value = false
  }
}

const rotateCode = async (row) => {
  try {
    const res = await rotateInviteCode(row.id)
    ElMessage.success('新邀请码：' + res.invite_code)
    loadOrgs()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '重置失败')
  }
}

const loadMembers = async (row) => {
  memberLoading.value = true
  try {
    const res = await getOrgMembers(row.id)
    members.value = res.items || []
    memberSeatUsed.value = res.seat_used || 0
    memberSeatLimit.value = res.seat_limit || 0
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载成员失败')
  } finally {
    memberLoading.value = false
  }
}

const openMembers = async (row) => {
  currentOrg.value = row
  memberVisible.value = true
  await loadMembers(row)
}

const openAssign = async (row) => {
  currentOrg.value = row
  await loadMembers(row)
  assignUserId.value = null
  assignVisible.value = true
}

const handleAssign = async () => {
  if (!assignUserId.value) {
    ElMessage.warning('请选择一位成员')
    return
  }
  saving.value = true
  try {
    await updateOrgMember(currentOrg.value.id, assignUserId.value, { org_role: 'admin' })
    ElMessage.success('已设为机构管理员')
    assignVisible.value = false
    loadMembers(currentOrg.value)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '设置失败')
  } finally {
    saving.value = false
  }
}

const toggleActive = async (row) => {
  try {
    await updateOrgMember(currentOrg.value.id, row.id, { is_active: !row.is_active })
    ElMessage.success(row.is_active ? '已停用' : '已启用')
    loadMembers(currentOrg.value)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  }
}

const resetPassword = async (row) => {
  try {
    const { value } = await ElMessageBox.prompt(
      `给「${row.name}」设置新密码（至少 8 位）`, '重置密码',
      { inputType: 'password', inputPattern: /.{8,}/, inputErrorMessage: '至少 8 位' })
    await updateOrgMember(currentOrg.value.id, row.id, { password: value })
    ElMessage.success('密码已重置')
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(e?.response?.data?.detail || '重置失败')
  }
}

onMounted(() => {
  loadOrgs()
  loadPlans()
})
</script>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.tip { font-size: 12px; color: #909399; margin-left: 8px; }
.over { color: #f56c6c; font-weight: 600; }
</style>
