<template>
  <div class="exam-take">
    <!-- 顶部信息栏 -->
    <div class="exam-header">
      <div class="exam-title">{{ exam?.title }}</div>
      <div class="exam-timer" :class="{ warning: timeLeftReady && timeLeft < 300 }">
        <el-icon><Timer /></el-icon>
        <span class="timer-text">{{ timeLeftReady ? formatTime(timeLeft) : '--:--' }}</span>
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

        <div class="question-content" v-html="currentQContent" @click="handleQuestionImageClick"></div>

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

        <!-- 填空题 -->
        <div class="options-area" v-else-if="currentQ.type === 'fill'">
          <el-input
            v-model="answers[currentQ.id]"
            type="textarea"
            :rows="2"
            placeholder="请填写图中所示的名称"
            maxlength="100"
          />
          <p class="tip">填空题，按图中所示形态填写名称</p>
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
      <!--
        移动端答题卡：默认收起。
        50 道题把题号全部铺开，底部这一大块会把上方的题干和选项挤出屏幕，
        手机上根本看不全选项，所以改成点一下才展开。
      -->
      <div class="mobile-nav-wrap">
        <button type="button" class="mobile-nav-toggle" @click="toggleMobileNav">
          <el-icon><component :is="showMobileNav ? 'ArrowDown' : 'ArrowUp'" /></el-icon>
          <span>答题卡 · 已答 {{ answeredCount }}/{{ questions.length }}</span>
        </button>
        <div class="mobile-nav" v-show="showMobileNav">
          <div class="mobile-nav-grid">
            <div
              v-for="(q, i) in questions"
              :key="q.id"
              class="mobile-nav-dot"
              :class="{ answered: isAnswered(q), current: i === currentIndex }"
              @click="goToQuestion(i)"
            >{{ i + 1 }}</div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="!exam && !loading" class="loading-tip">
      <el-empty description="考试不存在或已结束" />
    </div>
    <div v-if="loading" class="loading-tip">
      <el-icon class="is-loading"><Loading /></el-icon> 加载中...
    </div>

    <ImagePreview v-model="previewVisible" :src="previewSrc" title="题目图片" />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getExam, submitExam, startExam, saveExamDraft } from '@/api/exams'
import { ArrowLeft, ArrowRight, ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import ImagePreview from '@/components/ImagePreview.vue'

const route = useRoute()
const router = useRouter()
const examId = Number(route.params.id)

const loading = ref(true)
const submitting = ref(false)
// 移动端答题卡是否展开（默认收起，避免题号列表占掉大半屏幕）
const showMobileNav = ref(false)
const previewVisible = ref(false)
const previewSrc = ref('')
const exam = ref(null)
const questions = ref([])
const currentIndex = ref(0)
const answers = ref({})       // { questionId: 'A' }
const multipleAnswers = ref({}) // { questionId: ['A','B'] }
// null 表示倒计时还没拿到服务端截止时间。
// 这段等待期必须显示 "--:--" 而不是 00:00，
// 否则考生一进页面看到 00:00 会以为考试已经结束。
const timeLeft = ref(null)
const timeLeftReady = ref(false)
const deadline = ref(0)        // 考试截止时间戳（毫秒），刷新后据此恢复剩余时间
let clockOffset = 0           // 服务端与本机的时钟差（毫秒），倒计时以服务端为准
let timer = null
let draftTimer = null

// 作答草稿：手机端切后台被系统回收、误触刷新都会丢答案，
// 考试中掉一次作答就可能整场报废，所以把答案和截止时间落到 localStorage。
const DRAFT_KEY = `exam_draft_${examId}`

const loadDraft = () => {
  try {
    return JSON.parse(localStorage.getItem(DRAFT_KEY) || 'null')
  } catch {
    return null
  }
}

const saveDraft = () => {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({
      userId: localStorage.getItem('userId'),
      answers: { ...answers.value },
      multipleAnswers: JSON.parse(JSON.stringify(multipleAnswers.value)),
      deadline: deadline.value,
    }))
  } catch {
    // 存储失败不影响答题，静默忽略
  }
}

const clearDraft = () => localStorage.removeItem(DRAFT_KEY)

// 草稿同步到服务端：手机切后台被回收时，本地缓存可能一起丢，
// 服务端留一份，超时就能自动交卷，不至于整场报废。
let draftSyncTimer = null
const syncDraft = async () => {
  clearTimeout(draftSyncTimer)
  draftSyncTimer = setTimeout(async () => {
    try {
      await saveExamDraft(examId, buildAnswers())
    } catch {
      // 同步失败不影响答题，下次作答或提交时会再试
    }
  }, 800)
}

// 立即同步（提交前用，不做防抖）
const syncDraftNow = async () => {
  try {
    await saveExamDraft(examId, buildAnswers())
  } catch {
    // 同步失败不影响答题
  }
}

const handleQuestionImageClick = (event) => {
  const img = event.target?.closest?.('img')
  if (!img) return
  previewSrc.value = img.currentSrc || img.src
  previewVisible.value = true
}

const typeTagMap = {
  single: { label: '单选', type: 'primary' },
  multiple: { label: '多选', type: 'warning' },
  judgment: { label: '判断', type: 'success' },
  fill: { label: '填空', type: 'info' },
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

const currentQ = computed(() => questions.value[currentIndex.value] || {})
const currentQContent = computed(() => {
  const content = currentQ.value.content || ''
  if (!content) return ''
  // 将所有 /uploads 开头的图片路径替换为完整的后端URL
  return content.replace(/src=["'](\/uploads\/[^"']+)["']/g, (match, url) => {
    if (url.startsWith('http://') || url.startsWith('https://')) {
      return match
    }
    const baseUrl = API_BASE.replace(/\/api$/, '')
    return `src="${baseUrl}${url}"`
  })
})

const parsedOptions = computed(() => {
  try { return JSON.parse(currentQ.value.options || '{}') } catch { return {} }
})

const formatTime = (s) => {
  if (s == null) return '--:--'
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

// 展开/收起移动端答题卡
const toggleMobileNav = () => {
  showMobileNav.value = !showMobileNav.value
}

// 点题号跳题：跳完顺手收起答题卡，把屏幕让给题目
const goToQuestion = (i) => {
  currentIndex.value = i
  showMobileNav.value = false
}

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
    // 到点自动提交时不再弹确认框，直接交卷
      if (timeLeft.value > 0) {
      await ElMessageBox.confirm(`还有 ${unanswered} 道题未作答，确定提交？`, '提示', { type: 'warning' })
    }
  }
  submitting.value = true
  try {
    await syncDraftNow()
    const record = await submitExam(examId, { exam_id: examId, answers: JSON.stringify(buildAnswers()) })
    clearInterval(timer)
    clearInterval(draftTimer)
    clearDraft()
    // 通知 Layout 刷新最近动态
    window.dispatchEvent(new Event('exam-submitted'))
    router.push({ path: `/exam-result/${examId}`, query: { recordId: record.id } })
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    // 先向服务端开启/复用作答会话，取权威的截止时间。
    // 随机卷在这一步就把这一轮要考的题目定下来，所以要先开考再取卷面。
    let serverDeadline = 0
    try {
      const start = await startExam(examId)
      serverDeadline = start.deadline_ms || 0
      // 记录服务端与本机的时钟差，本地倒计时才不会因为手机时间不准而漂移
      clockOffset = (start.server_now_ms || Date.now()) - Date.now()
    } catch (e) {
      // 开考接口失败（例如已超时）时，仍然进入页面，由服务端在提交时把关
      console.warn('start exam failed', e)
    }
    const data = await getExam(examId)
    exam.value = data
    questions.value = data.questions || []
    // 恢复草稿：同一考生才复用，避免共用手机时串卷
    const draft = loadDraft()
    const currentUserId = localStorage.getItem('userId')
    const isSameUser = !!draft && !!currentUserId && draft.userId === currentUserId
    if (isSameUser) {
      answers.value = draft.answers || {}
      multipleAnswers.value = draft.multipleAnswers || {}
    }
    deadline.value = serverDeadline || (Date.now() + data.duration * 60 * 1000)
    const tick = () => {
      const now = Date.now() + clockOffset
      timeLeft.value = Math.max(0, Math.round((deadline.value - now) / 1000))
      if (timeLeft.value <= 0) {
        clearInterval(timer)
        ElMessage.warning('考试时间到，自动提交')
        handleSubmit()
      }
    }
    tick()
    timeLeftReady.value = true
    timer = setInterval(() => {
      tick()
    }, 1000)
    // 定期把草稿同步到服务端
    draftTimer = setInterval(syncDraft, 10000)
  } finally {
    loading.value = false
  }
})

// 每次作答都落盘，刷新或切后台都不丢答案
watch([answers, multipleAnswers], () => {
  saveDraft()
  syncDraft()
}, { deep: true })

onUnmounted(() => {
  clearInterval(timer)
  clearInterval(draftTimer)
  clearTimeout(draftSyncTimer)
})
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

.question-content :deep(img) { max-width: 100%; border-radius: 4px; cursor: zoom-in; touch-action: manipulation; }
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

/* 移动端答题卡容器：桌面端不显示 */
.mobile-nav-wrap {
  display: none;
}

.mobile-nav-toggle {
  width: 100%;
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 13px;
  color: #606266;
  background: #f7f9fb;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.mobile-nav-toggle:active {
  background: #ecf5ff;
  border-color: #409eff;
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

  .mobile-nav-wrap {
    display: block;
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
