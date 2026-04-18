<template>
  <div class="courses-page">
    <div class="page-header">
      <h2>课程管理</h2>
      <el-button type="primary" @click="handleAdd">
        <el-icon><Plus /></el-icon>
        添加课程
      </el-button>
    </div>

    <el-card>
      <el-table :data="tableData" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="课程名称" />
        <el-table-column prop="type" label="课程类型" width="120">
          <template #default="{ row }">
            <el-tag>{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="时长" width="100" />
        <el-table-column prop="students" label="学习人数" width="100" />
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
const total = ref(40)

const tableData = ref([
  { id: 1, title: '医学基础理论', type: '视频', duration: '120分钟', students: 45, createTime: '2024-04-01 10:00:00' },
  { id: 2, title: '临床实践指南', type: 'PDF', duration: '60分钟', students: 32, createTime: '2024-04-02 11:00:00' },
  { id: 3, title: '护理操作规范', type: 'Office', duration: '90分钟', students: 28, createTime: '2024-04-03 12:00:00' },
])

const handleAdd = () => {
  ElMessage.success('添加课程')
}

const handleEdit = (row) => {
  ElMessage.info(`编辑: ${row.title}`)
}

const handleDelete = (row) => {
  ElMessage.warning(`删除: ${row.title}`)
}
</script>

<style scoped>
.courses-page {
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
