<template>
  <div class="knowledge-page">
    <div class="page-header">
      <h2>知识管理</h2>
      <el-button type="primary" @click="handleAdd">
        <el-icon><Plus /></el-icon>
        添加知识点
      </el-button>
    </div>

    <el-card>
      <el-table :data="tableData" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="标题" />
        <el-table-column prop="category" label="分类" width="120" />
        <el-table-column prop="difficulty" label="难度" width="100">
          <template #default="{ row }">
            <el-tag :type="getDifficultyType(row.difficulty)">{{ row.difficulty }}</el-tag>
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
const total = ref(50)

const tableData = ref([
  { id: 1, title: '基础医学知识', category: '医学基础', difficulty: '简单', createTime: '2024-04-01 10:00:00' },
  { id: 2, title: '临床诊断技巧', category: '临床医学', difficulty: '中等', createTime: '2024-04-02 11:00:00' },
  { id: 3, title: '急救处理流程', category: '急救医学', difficulty: '困难', createTime: '2024-04-03 12:00:00' },
])

const getDifficultyType = (difficulty) => {
  const map = { '简单': 'success', '中等': 'warning', '困难': 'danger' }
  return map[difficulty] || ''
}

const handleAdd = () => {
  ElMessage.success('添加功能')
}

const handleEdit = (row) => {
  ElMessage.info(`编辑: ${row.title}`)
}

const handleDelete = (row) => {
  ElMessage.warning(`删除: ${row.title}`)
}
</script>

<style scoped>
.knowledge-page {
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
