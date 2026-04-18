<template>
  <div class="result-page">
    <div class="result-card" v-if="record">
      <div class="result-icon" :class="passed ? 'pass' : 'fail'">
        <el-icon><CircleCheck v-if="passed" /><CircleClose v-else /></el-icon>
      </div>
      <h2 class="result-title">{{ passed ? '恭喜，考试通过！' : '很遗憾，未通过' }}</h2>

      <div class="score-display">
        <span class="score-val">{{ percent }}</span>
        <span class="score-unit">%</span>
      </div>

      <div class="score-detail">
        正确率：{{ percent }}% &nbsp;({{ record.score }} / {{ record.total_score }})
      </div>

      <el-divider />

      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">考试名称</span>
          <span class="info-val">{{ exam?.title }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">及格分数</span>
          <span class="info-val">{{ exam?.pass_score }} 分</span>
        </div>
        <div class="info-item">
          <span class="info-label">提交时间</span>
          <span class="info-val">{{ formatDate(record.submitted_at) }}</span>
        </div>
      </div>

      <div class="result-actions">
        <el-button type="primary" @click="handleLogout">退出</el-button>
        <el-button @click="reviewVisible = true" v-if="exam">查看解析</el-button>
      </div>
    </div>

    <div v-if="!record && !loading" class="loading-tip">
      <el-empty description="记录不存在" />
    </div>

    <!-- 答案解析弹窗 -->
    <el-dialog v-model="reviewVisible" title="答案解析" width="700px" top="5vh">
      <div v-for="(q, i) in exam?.questions || []" :key="q.id" class="review-item">
        <div class="review-header">
          <span class="review-index">第 {{ i + 1 }} 题</span>
          <el-tag size="small" :type="typeTagMap[q.type]?.type">{{ typeTagMap[q.type]?.label }}</el-tag>
          <el-tag size="small" :type="isCorrect(q) ? 'success' : 'danger'">
            {{ isCorrect(q) ? '✓ 正确' : '✗ 错误' }}
          </el-tag>
          <span style="margin-left:auto;font-size:13px;color:#909399">{{ q.score }}分</span>
        </div>
        <div class="review-content" v-html="q.content"></div>
        <div class="review-answers">
          <div class="my-answer">
            <span class="answer-label">我的答案：</span>
            <span :class="isCorrect(q) ? 'correct' : 'wrong'">{{ submittedAnswers[q.id] || '未作答' }}</span>
          </div>
          <div class="correct-answer">
            <span class="answer-label">正确答案：</span>
            <span class="correct">{{ q.answer }}</span>
          </div>
        </div>
        <div class="review-analysis" v-if="q.analysis">
          <span class="answer-label">解析：</span>{{ q.analysis }}
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getExam } from '@/api/exams'
import { useAuthStore } from '@/stores/auth'
import request from '@/api/index'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const examId = Number(route.params.id)
const recordId = Number(route.query.recordId)

const loading = ref(true)
const record = ref(null)
const exam = ref(null)
const reviewVisible = ref(false)
const submittedAnswers = ref({})

const typeTagMap = {
  single: { label: '单选', type: 'primary' },
  multiple: { label: '多选', type: 'warning' },
  judgment: { label: '判断', type: 'success' },
}

const percent = computed(() => {
  if (!record.value || !record.value.total_score) return 0
  return Math.round(record.value.score / record.value.total_score * 100)
})

const passed = computed(() => {
  return exam.value ? percent.value >= exam.value.pass_score : false
})

const isCorrect = (q) => {
  const myAns = submittedAnswers.value[q.id] || ''
  if (q.type === 'multiple') {
    return myAns.split(',').sort().join(',') === q.answer.split(',').sort().join(',')
  }
  return myAns === q.answer
}

const formatDate = (dt) => {
  if (!dt) return '-'
  // 服务器返回UTC时间，解析后加8小时转为中国本地时间
  const [datePart, timePart] = dt.split('T')
  const [year, month, day] = datePart.split('-').map(Number)
  const [hour, minute, second] = timePart.split(':').map(Number)
  const d = new Date(year, month - 1, day, hour + 8, minute, second)
  return d.toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-')
}

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}

onMounted(async () => {
  try {
    const [examData, recordData] = await Promise.all([
      getExam(examId),
      request.get(`/exam-records/${recordId}`).catch(() => null),
    ])
    exam.value = examData
    // record 从 exam records 中找
    if (!recordData) {
      const records = await request.get(`/exams/${examId}/records`).catch(() => [])
      record.value = Array.isArray(records) ? records.find(r => r.id === recordId) : null
    } else {
      record.value = recordData
    }
    // 解析提交的答案
    if (record.value?.answers) {
      try { submittedAnswers.value = JSON.parse(record.value.answers) } catch {}
    }
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.result-page {
  min-height: 100vh;
  background: #f5f7fa;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.result-card {
  background: #fff;
  border-radius: 16px;
  padding: 48px 40px;
  width: 100%;
  max-width: 500px;
  text-align: center;
  box-shadow: 0 4px 24px rgba(0,0,0,0.1);
}

.result-icon {
  font-size: 72px;
  margin-bottom: 16px;
}

.result-icon.pass { color: #67C23A; }
.result-icon.fail { color: #F56C6C; }

.result-title { font-size: 22px; color: #303133; margin-bottom: 24px; }

.score-display {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 4px;
}

.score-val { font-size: 72px; font-weight: bold; color: #303133; line-height: 1; }
.score-unit { font-size: 24px; color: #909399; }

.score-detail { font-size: 15px; color: #909399; margin-top: 8px; }

.info-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  text-align: left;
  margin-bottom: 24px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}

.info-label { color: #909399; }
.info-val { color: #303133; font-weight: 500; }

.result-actions { display: flex; justify-content: center; gap: 12px; }

.review-item {
  border-bottom: 1px solid #f0f2f5;
  padding: 16px 0;
}

.review-item:last-child { border-bottom: none; }

.review-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.review-index { font-size: 14px; color: #606266; font-weight: 500; }

.review-content {
  font-size: 15px;
  line-height: 1.7;
  margin-bottom: 12px;
  color: #303133;
}

.review-content :deep(img) { max-width: 100%; }

.review-answers { display: flex; gap: 24px; font-size: 14px; margin-bottom: 8px; }
.answer-label { color: #909399; }
.correct { color: #67C23A; font-weight: 500; }
.wrong { color: #F56C6C; font-weight: 500; }

.review-analysis {
  font-size: 13px;
  color: #606266;
  background: #f5f7fa;
  padding: 8px 12px;
  border-radius: 4px;
  line-height: 1.6;
}

.loading-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 50vh;
}

@media (max-width: 480px) {
  .result-card { padding: 32px 24px; }
  .score-val { font-size: 56px; }
}
</style>
