<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>机构套餐</span>
          <el-button size="small" type="primary" @click="openEdit(null)">新建套餐</el-button>
        </div>
      </template>

      <el-table :data="plans" v-loading="loading" border size="small">
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="code" label="编码" width="140" />
        <el-table-column prop="seat_limit" label="席位" width="90" />
        <el-table-column prop="duration_days" label="有效期(天)" width="110" />
        <el-table-column label="价格" width="110">
          <template #default="{ row }">￥{{ (row.price_cents / 100).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="160" />
        <el-table-column prop="sort_order" label="排序" width="80" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="openEdit(row)">编辑</el-button>
            <el-button size="small" text type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="editVisible" :title="form.id ? '编辑套餐' : '新建套餐'" width="460px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="编码" required>
          <el-input v-model="form.code" placeholder="英文短码，如 org_basic" />
        </el-form-item>
        <el-form-item label="席位">
          <el-input-number v-model="form.seat_limit" :min="0" :max="9999" />
        </el-form-item>
        <el-form-item label="有效期(天)">
          <el-input-number v-model="form.duration_days" :min="1" :max="3650" />
        </el-form-item>
        <el-form-item label="价格(元)">
          <el-input-number v-model="form.price_yuan" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAdminPlans, createPlan, updatePlan, deletePlan } from '@/api/billing'

const plans = ref([])
const loading = ref(false)
const saving = ref(false)
const editVisible = ref(false)
const form = ref({})

const load = async () => {
  loading.value = true
  try {
    const res = await getAdminPlans()
    plans.value = res.items || []
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

const openEdit = (row) => {
  if (row) {
    form.value = {
      id: row.id, name: row.name, code: row.code,
      seat_limit: row.seat_limit, duration_days: row.duration_days,
      price_yuan: row.price_cents / 100, description: row.description,
      sort_order: row.sort_order, is_active: row.is_active,
    }
  } else {
    form.value = {
      id: null, name: '', code: '', seat_limit: 20, duration_days: 30,
      price_yuan: 0, description: '', sort_order: plans.value.length + 1, is_active: true,
    }
  }
  editVisible.value = true
}

const handleSave = async () => {
  if (!form.value.name || !form.value.code) {
    ElMessage.warning('名称和编码都要填')
    return
  }
  saving.value = true
  const payload = {
    code: form.value.code,
    name: form.value.name,
    seat_limit: form.value.seat_limit,
    duration_days: form.value.duration_days,
    price_cents: Math.round((form.value.price_yuan || 0) * 100),
    description: form.value.description || '',
    is_active: !!form.value.is_active,
    sort_order: form.value.sort_order || 0,
  }
  try {
    if (form.value.id) await updatePlan(form.value.id, payload)
    else await createPlan(payload)
    ElMessage.success('已保存')
    editVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const remove = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除套餐「${row.name}」？已生成的兑换码不受影响。`, '提示', { type: 'warning' })
    await deletePlan(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

onMounted(load)
</script>

<style scoped>
.page { max-width: 1200px; margin: 0 auto; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
