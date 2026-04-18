<template>
  <div class="exam-list-page">
    <div class="page-header">
      <h2>我的考试</h2>
    </div>

    <el-card v-loading="loading">
      <el-table :data="tableData" style="width:100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="考试名称" min-width="160" />
        <el-table-column label="时长" width="90">
          <template #default="{ row }">{{ row.duration }}分钟</template>
        </el-table-column>
        <el-table-column label="题目数" width="80">
          <template #default="{ row }">{{ row.question_count }}</template>
        </el-table-column>
        <el-table-column label="总分" width="80">
          <template #default="{ row }">{{ row.total_score }}分</template>
        </el-table-column>
        <el-table-column label="及格分" width="80">
          <template #default="{ row }">{{ row.pass_score }}分</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row)">{{ getStatus(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button 
              v-if="canStart(row)" 
              type="primary" 
              size="small" 
              @click="startExam(row)"
            >
              开始考试
            </el-button>
            <el-tag v-else-if="getStatus(row) === '已完成'" type="success" size="small">
              已完成
            </el-tag>
            <el-tag v-else type="info" size="small">
              {{ getStatus(row) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="confirmVisible" title="开始考试" width="400px">
      <div style="padding: 16px 0;">
        <p style="margin-bottom: 12px;">考试名称：<strong>{{ currentExam?.title }}</strong></p>
        <p style="margin-bottom: 12px;">考试时长：<strong>{{ currentExam?.duration }}分钟</strong></p>
        <p style="margin-bottom: 12px;">题目数量：<strong>{{ currentExam?.question_count }}道</strong></p>
        <p style="color: #E6A23C; font-size: 13px;">考试开始后需在规定时间内完成，请确保网络稳定。</p>
      </div>
      <template #footer>
        <el-button @click="confirmVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmStart">确认开始</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getExams, getExam } from '@/api/exams'
import request from '@/api'

const router = useRouter()
const loading = ref(false)
const tableData = ref([])
const examScores = ref({})
const confirmVisible = ref(false)
const currentExam = ref(null)

const getStatus = (exam) => {
  const score = examScores.value[exam.id]
  if (score !== undefined) return '已完成'
  
  const now = new Date()
  if (exam.start_time && new Date(exam.start_time) > now) return '未开始'
  if (exam.end_time && new Date(exam.end_time) < now) return '已结束'
  if (exam.start_time || exam.end_time) return '进行中'
  return '可参加'
}

const getStatusType = (exam) => {
  const s = getStatus(exam)
  return { '进行中': 'success', '未开始': 'info', '已结束': 'danger', '可参加': 'warning', '已完成': 'success' }[s]
}

const canStart = (exam) => {
  const s = getStatus(exam)
  return s === '进行中' || s === '可参加'
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getExams({ skip: 0, limit: 100 })
    tableData.value = res.items.filter(e => e.question_count > 0)
    
    const token = localStorage.getItem('token')
    const userId = JSON.parse(atob(token.split('.')[1])).sub
    
    for (const exam of tableData.value) {
      try {
        const detail = await getExam(exam.id)
        const totalScore = detail.questions?.reduce((sum, q) => sum + (q.score || 10), 0) || 0
        exam.total_score = totalScore
        
        const recordRes = await request.get(`/exam-records/user/${userId}/exam/${exam.id}`)
        if (recordRes && recordRes.score !== undefined) {
          examScores.value[exam.id] = recordRes.score
        }
      } catch {
        exam.total_score = exam.question_count * 10
      }
    }
  } finally {
    loading.value = false
  }
}

const startExam = (exam) => {
  currentExam.value = exam
  confirmVisible.value = true
}

const confirmStart = () => {
  confirmVisible.value = false
  router.push({ path: `/exam-take/${currentExam.value.id}` })
}

onMounted(loadData)
</script>

<style scoped>
.exam-list-page { padding: 20px; }
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 { font-size: 18px; font-weight: 500; }
</style>
