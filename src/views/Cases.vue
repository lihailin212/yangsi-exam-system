<template>
  <div class="cases-page">
    <div class="page-header">
      <h2>案例管理</h2>
      <el-button type="primary" @click="handleAdd">
        <el-icon><Plus /></el-icon>
        添加案例
      </el-button>
    </div>

    <el-card>
      <el-table :data="tableData" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="案例标题" />
        <el-table-column prop="type" label="案例类型" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === '已发布' ? 'success' : 'info'">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="创建时间" width="180" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="currentPage"
        :page-size="10"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const currentPage = ref(1)
const total = ref(30)

const tableData = ref([
  { id: 1, title: '心脏病诊断案例', type: '临床案例', status: '已发布', createTime: '2024-04-01 10:00:00' },
  { id: 2, title: '外科手术案例', type: '手术案例', status: '草稿', createTime: '2024-04-02 11:00:00' },
])

const handleAdd = () => {
  ElMessage.success('添加案例')
}

const handleEdit = (row) => {
  ElMessage.info(`编辑: ${row.title}`)
}

const handleDelete = (row) => {
  ElMessage.warning(`删除: ${row.title}`)
}
</script>

<style scoped>
.cases-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 18px;
  font-weight: 500;
}
</style>
