<template>
  <div class="exam-list-page">
    <div class="page-header">
      <h2>我的考试</h2>
    </div>

    <!-- 手机端：表格列太多，横向挤在一起看不清（考试名称被压成两行、
         操作按钮盖住表格）。改成卡片列表，每场考试一张卡，信息竖排。 -->
    <div v-loading="loading" v-if="isMobile" class="exam-cards">
      <el-card v-for="row in tableData" :key="row.id" shadow="never" class="exam-card">
        <div class="exam-card-title">{{ row.title }}</div>
        <div class="exam-card-meta">
          <span>{{ row.duration }} 分钟</span>
          <span>{{ displayQuestionCount(row) }} 题</span>
          <span>满分 {{ row.total_score }} 分</span>
          <span>及格 {{ row.pass_score }} 分</span>
        </div>
        <div class="exam-card-foot">
          <el-tag :type="getStatusType(row)" size="small">{{ getStatus(row) }}</el-tag>
          <el-button
            v-if="canStart(row)"
            type="primary"
            size="small"
            @click="startExam(row)"
          >
            开始考试
          </el-button>
        </div>
      </el-card>
      <el-empty v-if="!loading && tableData.length === 0" description="暂无可参加的考试" />
    </div>

    <el-card v-loading="loading" v-else>
      <el-table :data="tableData" style="width:100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="考试名称" min-width="160" />
        <el-table-column label="时长" width="90">
          <template #default="{ row }">{{ row.duration }}分钟</template>
        </el-table-column>
        <el-table-column label="题目数" width="80">
          <template #default="{ row }">{{ displayQuestionCount(row) }}</template>
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
        <p style="margin-bottom: 12px;">题目数量：<strong>{{ displayQuestionCount(currentExam) }}道</strong></p>
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
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { getExams } from '@/api/exams'
import { getMyScores } from '@/api/examScores'
import { ElMessage } from 'element-plus'

const router = useRouter()
const loading = ref(false)
// 手机端用卡片列表代替表格（表格列多，横向放不下）
const isMobile = ref(false)
const updateMobile = () => { isMobile.value = window.innerWidth <= 768 }
const tableData = ref([])
const examScores = ref({})
const confirmVisible = ref(false)
const currentExam = ref(null)

// 随机卷显示每位考生实际要答的题数，固定卷面显示题目总数
const displayQuestionCount = (exam) => {
  if (!exam) return 0
  if (exam.random_mode) {
    const n = Number(exam.paper_question_count)
    return Number.isFinite(n) && n > 0 ? n : (exam.question_count || 0)
  }
  return exam.question_count || 0
}

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
    const res = await getExams({ skip: 0, limit: 100, kind: 'normal' })
    tableData.value = res.items.filter(e => displayQuestionCount(e) > 0)

    // 成绩一次拿回，不要每场考试再发两次请求。
    // 以前是 59 场考试 × 2 次串行请求，数据库在远端时页面要等好几分钟，
    // loading 遮罩一直不撤，看上去就是一片灰。
    const scores = await getMyScores()
    for (const exam of tableData.value) {
      const score = scores[exam.id]
      if (score !== undefined && score !== null) {
        examScores.value[exam.id] = score
      }
      // 总分列表接口已经给了，不用再拉一次考试详情
      if (!exam.total_score) {
        exam.total_score = displayQuestionCount(exam) * 10
      }
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载失败')
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

onMounted(() => {
  updateMobile()
  window.addEventListener('resize', updateMobile)
  loadData()
})
onUnmounted(() => window.removeEventListener('resize', updateMobile))
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

/* 手机端卡片列表 */
.exam-cards { display: flex; flex-direction: column; gap: 10px; }
.exam-card-title { font-size: 15px; font-weight: 600; line-height: 1.5; margin-bottom: 8px; }
.exam-card-meta {
  display: flex; flex-wrap: wrap; gap: 6px 12px;
  font-size: 12px; color: var(--neutral-500, #909399); margin-bottom: 10px;
}
.exam-card-foot { display: flex; align-items: center; justify-content: space-between; }
</style>
