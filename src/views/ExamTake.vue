<template>
  <div class="exam-take">
    <!-- 顶部信息栏 -->
    <div class="exam-header">
      <div class="exam-title">{{ exam?.title }}</div>
      <div class="exam-timer" :class="{ warning: timeLeft < 300 }">
        <el-icon><Timer /></el-icon>
        <span class="timer-text">{{ formatTime(timeLeft) }}</span>
      </div>
    </div>

    <div class="exam-body" v-if="exam && questions.length">
      <!-- 题目区域 -->
      <div class="question-area">
        <div class="question-header">
          <span class="q-index">第 {{ currentIndex + 1 }} 题 / 共 {{ questions.length }} 题</span>
          <el-tag size="small" :type="typeTagMap[currentQ.type]?.type">{{ typeTagMap[currentQ.type]?.label }}</el-tag>
          <span class="q-score">{{ currentQ.score }}分</span>
        </div>

        <div class="question-content" v-html="currentQContent"></div>

        <!-- 单选题 -->
        <div class="options-area" v-if="currentQ.type === 'single'">
          <div
            v-for="(val, key) in parsedOptions"
            :key="key"
            class="option-item"
            :class="{ selected: answers[currentQ.id] === key }"
            @click="selectAnswer(key)"
          >
            <span class="option-key">{{ key }}</span>
            <span class="option-val">{{ val }}</span>
          </div>
        </div>

        <!-- 多选题 -->
        <div class="options-area" v-else-if="currentQ.type === 'multiple'">
          <div
            v-for="(val, key) in parsedOptions"
            :key="key"
            class="option-item"
            :class="{ selected: (multipleAnswers[currentQ.id] || []).includes(key) }"
            @click="toggleMultiple(key)"
          >
            <span class="option-key">{{ key }}</span>
            <span class="option-val">{{ val }}</span>
          </div>
          <p class="tip">多选题，请选择所有正确答案</p>
        </div>

        <!-- 判断题 -->
        <div class="options-area" v-else-if="currentQ.type === 'judgment'">
          <div
            class="option-item"
            :class="{ selected: answers[currentQ.id] === '正确' }"
            @click="selectAnswer('正确')"
          >
            <span class="option-key">✓</span>
            <span class="option-val">正确</span>
          </div>
          <div
            class="option-item"
            :class="{ selected: answers[currentQ.id] === '错误' }"
            @click="selectAnswer('错误')"
          >
            <span class="option-key">✗</span>
            <span class="option-val">错误</span>
          </div>
        </div>
      </div>

      <!-- 题目导航 - 桌面端右侧 -->
      <div class="question-nav desktop-nav">
        <div class="nav-title">答题进度</div>
        <div class="nav-grid">
          <div
            v-for="(q, i) in questions"
            :key="q.id"
            class="nav-dot"
            :class="{ answered: isAnswered(q), current: i === currentIndex }"
            @click="currentIndex = i"
          >{{ i + 1 }}</div>
        </div>
        <div class="nav-legend">
          <span class="dot answered"></span> 已答
          <span class="dot"></span> 未答
        </div>
      </div>
    </div>

    <!-- 底部导航 - 移动端显示 -->
    <div class="exam-footer" v-if="questions.length">
      <div class="footer-progress">
        <span class="progress-text">已答 {{ answeredCount }}/{{ questions.length }}</span>
        <el-progress
          :percentage="answeredPercent"
          :stroke-width="6"
          :show-text="false"
          color="#67C23A"
        />
      </div>
      <div class="footer-actions">
        <el-button class="nav-btn" @click="prevQ" :disabled="currentIndex === 0">
          <el-icon><ArrowLeft /></el-icon>
          <span class="btn-text">上一题</span>
        </el-button>
        <el-button v-if="currentIndex < questions.length - 1" type="primary" class="nav-btn" @click="nextQ">
          <span class="btn-text">下一题</span>
          <el-icon><ArrowRight /></el-icon>
        </el-button>
        <el-button v-else type="success" class="nav-btn" @click="handleSubmit" :loading="submitting">
          <span class="btn-text">提交答卷</span>
        </el-button>
      </div>
      <!-- 移动端答题进度条 -->
      <div class="mobile-nav">
        <div class="mobile-nav-grid">
          <div
            v-for="(q, i) in questions"
            :key="q.id"
            class="mobile-nav-dot"
            :class="{ answered: isAnswered(q), current: i === currentIndex }"
            @click="currentIndex = i"
          >{{ i + 1 }}</div>
        </div>
      </div>
    </div>

    <div v-if="!exam && !loading" class="loading-tip">
      <el-empty description="考试不存在或已结束" />
    </div>
    <div v-if="loading" class="loading-tip">
      <el-icon class="is-loading"><Loading /></el-icon> 加载中...
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getExam, submitExam } from '@/api/exams'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const examId = Number(route.params.id)

const loading = ref(true)
const submitting = ref(false)
const exam = ref(null)
const questions = ref([])
const currentIndex = ref(0)
const answers = ref({})       // { questionId: 'A' }
const multipleAnswers = ref({}) // { questionId: ['A','B'] }
const timeLeft = ref(0)
let timer = null

const typeTagMap = {
  single: { label: '单选', type: 'primary' },
  multiple: { label: '多选', type: 'warning' },
  judgment: { label: '判断', type: 'success' },
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'https://yangsi-exam-system-production-6700.up.railway.app'

const currentQ = computed(() => questions.value[currentIndex.value] || {})
const currentQContent = computed(() => currentQ.value.content?.replace(/\/uploads\//g, `${API_BASE}/uploads/`) || '')

const parsedOptions = computed(() => {
  try { return JSON.parse(currentQ.value.options || '{}') } catch { return {} }
})

const formatTime = (s) => {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

const isAnswered = (q) => {
  if (q.type === 'multiple') return (multipleAnswers.value[q.id] || []).length > 0
  return !!answers.value[q.id]
}

const answeredCount = computed(() => {
  return questions.value.filter(q => isAnswered(q)).length
})

const answeredPercent = computed(() => {
  if (questions.value.length === 0) return 0
  return Math.round((answeredCount.value / questions.value.length) * 100)
})

const selectAnswer = (key) => {
  answers.value[currentQ.value.id] = key
}

const toggleMultiple = (key) => {
  const id = currentQ.value.id
  if (!multipleAnswers.value[id]) multipleAnswers.value[id] = []
  const idx = multipleAnswers.value[id].indexOf(key)
  if (idx === -1) multipleAnswers.value[id].push(key)
  else multipleAnswers.value[id].splice(idx, 1)
}

const prevQ = () => { if (currentIndex.value > 0) currentIndex.value-- }
const nextQ = () => { if (currentIndex.value < questions.value.length - 1) currentIndex.value++ }

const buildAnswers = () => {
  const result = { ...answers.value }
  for (const [id, arr] of Object.entries(multipleAnswers.value)) {
    result[id] = arr.sort().join(',')
  }
  return result
}

const handleSubmit = async () => {
  const unanswered = questions.value.filter(q => !isAnswered(q)).length
  if (unanswered > 0) {
    await ElMessageBox.confirm(`还有 ${unanswered} 道题未作答，确定提交？`, '提示', { type: 'warning' })
  }
  submitting.value = true
  try {
    const record = await submitExam(examId, { exam_id: examId, answers: JSON.stringify(buildAnswers()) })
    clearInterval(timer)
    // 通知 Layout 刷新最近动态
    window.dispatchEvent(new Event('exam-submitted'))
    router.push({ path: `/exam-result/${examId}`, query: { recordId: record.id } })
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    const data = await getExam(examId)
    exam.value = data
    questions.value = data.questions || []
    timeLeft.value = data.duration * 60
    timer = setInterval(() => {
      if (timeLeft.value > 0) {
        timeLeft.value--
      } else {
        clearInterval(timer)
        ElMessage.warning('考试时间到，自动提交')
        handleSubmit()
      }
    }, 1000)
  } finally {
    loading.value = false
  }
})

onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.exam-take {
  min-height: 100vh;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
}

.exam-header {
  background: #304156;
  color: #fff;
  padding: 14px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 10;
}

.exam-title {
  font-size: 16px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 60%;
}

.exam-timer {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 18px;
  font-weight: bold;
  font-variant-numeric: tabular-nums;
}

.exam-timer.warning { color: #F56C6C; }

.exam-body {
  flex: 1;
  display: flex;
  gap: 16px;
  padding: 16px;
  max-width: 1000px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

.question-area {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.question-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.q-index { font-size: 14px; color: #606266; }
.q-score { font-size: 13px; color: #909399; margin-left: auto; }

.question-content {
  font-size: 16px;
  line-height: 1.8;
  margin-bottom: 24px;
  color: #303133;
  word-wrap: break-word;
}

.question-content :deep(img) { max-width: 100%; border-radius: 4px; }
.question-content :deep(p) { margin: 0 0 12px; }
.question-content :deep(p:last-child) { margin-bottom: 0; }

.options-area { display: flex; flex-direction: column; gap: 12px; }

.option-item {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px;
  border: 2px solid #e4e7ed;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  min-height: 48px;
  -webkit-tap-highlight-color: transparent;
}

.option-item:hover { border-color: #409EFF; background: #f0f7ff; }
.option-item.selected { border-color: #409EFF; background: #ecf5ff; }

.option-key {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: bold;
  flex-shrink: 0;
}

.option-item.selected .option-key { background: #409EFF; color: #fff; }
.option-val { font-size: 15px; line-height: 1.6; word-break: break-word; }
.tip { font-size: 12px; color: #909399; margin-top: 4px; }

.question-nav.desktop-nav {
  width: 200px;
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  align-self: flex-start;
  position: sticky;
  top: 70px;
}

.nav-title { font-size: 14px; font-weight: 500; margin-bottom: 12px; color: #303133; }

.nav-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 6px;
  margin-bottom: 12px;
}

.nav-dot {
  width: 30px;
  height: 30px;
  border-radius: 4px;
  background: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.nav-dot.answered { background: #409EFF; color: #fff; }
.nav-dot.current { outline: 2px solid #409EFF; }

.nav-legend {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #909399;
}

.dot {
  width: 12px;
  height: 12px;
  border-radius: 2px;
  background: #f0f2f5;
  display: inline-block;
}

.dot.answered { background: #409EFF; }

.exam-footer {
  background: #fff;
  padding: 16px 20px;
  box-shadow: 0 -2px 8px rgba(0,0,0,0.06);
  position: sticky;
  bottom: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.footer-progress {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.progress-text {
  font-size: 13px;
  color: #606266;
}

.footer-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}

.nav-btn {
  flex: 1;
  max-width: 160px;
  min-height: 44px;
  -webkit-tap-highlight-color: transparent;
}

.nav-btn .el-icon {
  margin: 0 4px;
}

.mobile-nav {
  display: none;
  padding-top: 8px;
  border-top: 1px solid #eee;
}

.mobile-nav-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
}

.mobile-nav-dot {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  -webkit-tap-highlight-color: transparent;
}

.mobile-nav-dot.answered { background: #409EFF; color: #fff; }
.mobile-nav-dot.current { outline: 2px solid #409EFF; }

.loading-tip {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: #909399;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .exam-header {
    padding: 12px 16px;
  }

  .exam-title {
    font-size: 14px;
    max-width: 50%;
  }

  .timer-text {
    display: inline;
  }

  .exam-timer {
    font-size: 16px;
  }

  .exam-body {
    flex-direction: column;
    padding: 12px;
    gap: 12px;
  }

  .desktop-nav {
    display: none;
  }

  .question-area {
    padding: 16px;
    border-radius: 8px;
  }

  .question-content {
    font-size: 15px;
  }

  .question-header {
    gap: 8px;
  }

  .q-index {
    font-size: 13px;
  }

  .option-item {
    padding: 14px;
    gap: 12px;
  }

  .option-key {
    width: 28px;
    height: 28px;
    font-size: 13px;
  }

  .option-val {
    font-size: 14px;
  }

  .exam-footer {
    padding: 12px 16px;
    gap: 10px;
  }

  .footer-actions {
    gap: 10px;
  }

  .nav-btn {
    max-width: none;
    min-height: 46px;
    font-size: 14px;
  }

  .btn-text {
    display: inline;
  }

  .mobile-nav {
    display: block;
  }

  .mobile-nav-grid {
    gap: 8px;
  }

  .mobile-nav-dot {
    width: 36px;
    height: 36px;
    font-size: 13px;
  }
}

/* 更小屏幕 */
@media (max-width: 480px) {
  .exam-title {
    max-width: 40%;
    font-size: 13px;
  }

  .exam-timer {
    font-size: 14px;
  }

  .question-area {
    padding: 12px;
  }

  .option-item {
    padding: 12px;
  }
}
</style>
