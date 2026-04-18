<template>
  <div class="students-page">
    <div class="page-header">
      <h2>学员管理</h2>
      <el-button type="primary" @click="openAdd">
        <el-icon><Plus /></el-icon> 添加学员
      </el-button>
    </div>

    <el-card>
      <div class="search-bar">
        <el-input v-model="searchText" placeholder="搜索姓名/工号" style="width:200px" clearable @change="loadData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="filterDept" placeholder="科室" clearable style="width:140px" @change="loadData">
          <el-option v-for="d in depts" :key="d" :label="d" :value="d" />
        </el-select>
      </div>

      <el-table :data="tableData" v-loading="loading" style="width:100%;margin-top:16px">
        <el-table-column prop="employee_id" label="工号" width="100" />
        <el-table-column prop="name" label="姓名" width="90" />
        <el-table-column prop="dept" label="科室" width="110" />
        <el-table-column prop="role" label="职位" width="120" />
        <el-table-column label="角色" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="row.is_admin ? 'danger' : 'info'">
              {{ row.is_admin ? '管理员' : '学员' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-switch
              v-model="row.is_active"
              active-text="启用"
              inactive-text="禁用"
              inline-prompt
              style="--el-switch-on-color: #67C23A; --el-switch-off-color: #909399"
              @change="handleToggleActive(row)"
              :disabled="row.is_admin"
            />
            <el-button size="small" @click="openEdit(row)" style="margin-left:8px">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)" :disabled="row.is_admin">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top:16px;justify-content:flex-end"
        @current-change="loadData"
      />
    </el-card>

    <!-- 添加/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑学员' : '添加学员'" width="480px" :close-on-click-modal="false">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="90px">
        <el-form-item label="工号" prop="employee_id">
          <el-input v-model="form.employee_id" placeholder="员工工号" :disabled="!!editingId" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="真实姓名" />
        </el-form-item>
        <el-form-item label="密码" :prop="editingId ? '' : 'password'">
          <el-input v-model="form.password" type="password" :placeholder="editingId ? '不填则不修改' : '登录密码'" show-password />
        </el-form-item>
        <el-form-item label="科室">
          <el-input v-model="form.dept" placeholder="所在科室" />
        </el-form-item>
        <el-form-item label="职位">
          <el-input v-model="form.role" placeholder="职位/职称" />
        </el-form-item>
        <el-form-item label="管理员">
          <el-switch v-model="form.is_admin" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getStudents, createStudent, updateStudent, deleteStudent } from '@/api/students'

const loading = ref(false)
const saving = ref(false)
const tableData = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(15)
const searchText = ref('')
const filterDept = ref('')
const dialogVisible = ref(false)
const editingId = ref(null)
const formRef = ref(null)

const depts = ['内科', '外科', '护理部', '急诊科', '检验科', '放射科', '药剂科', '管理部']

const form = reactive({
  employee_id: '',
  name: '',
  password: '',
  dept: '',
  role: '',
  is_admin: false,
  is_active: true,
})

const formRules = {
  employee_id: [{ required: true, message: '请输入工号' }],
  name: [{ required: true, message: '请输入姓名' }],
  password: [{ required: true, message: '请输入密码' }],
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getStudents({
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
      search: searchText.value,
      dept: filterDept.value,
    })
    tableData.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

const openAdd = () => {
  editingId.value = null
  Object.assign(form, { employee_id: '', name: '', password: '', dept: '', role: '', is_admin: false, is_active: true })
  dialogVisible.value = true
}

const openEdit = (row) => {
  editingId.value = row.id
  Object.assign(form, { employee_id: row.employee_id, name: row.name, password: '', dept: row.dept, role: row.role, is_admin: row.is_admin, is_active: row.is_active })
  dialogVisible.value = true
}

const handleSave = async () => {
  await formRef.value.validate()
  saving.value = true
  try {
    if (editingId.value) {
      const payload = { name: form.name, dept: form.dept, role: form.role, is_admin: form.is_admin, is_active: form.is_active }
      if (form.password) payload.password = form.password
      await updateStudent(editingId.value, payload)
      ElMessage.success('修改成功')
    } else {
      await createStudent({ ...form })
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    loadData()
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm(`确定删除学员「${row.name}」？`, '提示', { type: 'warning' })
  await deleteStudent(row.id)
  ElMessage.success('已删除')
  loadData()
}

const handleToggleActive = async (row) => {
  try {
    await updateStudent(row.id, { is_active: row.is_active })
    ElMessage.success(row.is_active ? '已启用' : '已禁用')
  } catch (e) {
    // 回滚
    row.is_active = !row.is_active
    ElMessage.error('操作失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.students-page { padding: 20px; }
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 { font-size: 18px; font-weight: 500; }
.search-bar { display: flex; gap: 10px; flex-wrap: wrap; }
</style>
