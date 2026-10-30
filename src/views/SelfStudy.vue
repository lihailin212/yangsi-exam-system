<template>
  <div class="study-page">
    <div class="page-header">
      <h2>考生自学</h2>
      <p class="subtitle">选择题目进行自主学习，点击题干下方区域查看答案和解析</p>
    </div>

    <!-- 学习模式选择 -->
    <el-card v-if="!studying" class="mode-card">
      <template #header>
        <span>题目选择</span>
      </template>

      <div class="filter-row">
        <el-select v-model="filterType" placeholder="题目类型" clearable style="width: 150px">
          <el-option label="全部" value="" />
          <el-option label="单选题" value="single" />
          <el-option label="多选题" value="multiple" />
          <el-option label="判断题" value="judgment" />
          <el-option label="填空题" value="fill" />
        </el-select>

        <el-select v-model="filterCategory" placeholder="题目分类" clearable style="width: 200px">
          <el-option label="全部分类" value="" />
          <el-option-group label="形态学">
            <el-option label="全部形态学" value="形态学/" />
            <el-option v-for="cat in morphologyCategories" :key="cat" :label="cat.split('/')[1] || cat" :value="cat" />
          </el-option-group>
          <el-option v-for="cat in otherCategories" :key="cat" :label="cat" :value="cat" />
        </el-select>

        <el-input
          v-model="searchKeyword"
          placeholder="搜索题目内容..."
          clearable
          style="width: 200px"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <el-button type="primary" @click="handleSearch">
          <el-icon><Search /></el-icon>
          查询
        </el-button>
      </div>

      <div class="stats-row">
        <span>共 {{ total }} 道题目</span>
        <span v-if="selectedQuestions.length > 0">已选择 {{ selectedQuestions.length }} 道</span>
      </div>

      <div v-loading="loading" class="question-list">
        <div
          v-for="q in questions"
          :key="q.id"
          class="question-item"
          :class="{ selected: selectedQuestions.includes(q.id) }"
          @click="toggleQuestion(q.id)"
        >
          <el-checkbox
            :model-value="selectedQuestions.includes(q.id)"
            @click.stop
            @change="toggleQuestion(q.id)"
          />
          <div class="question-content">
            <el-tag size="small" :type="getTypeTag(q.type)">{{ getTypeName(q.type) }}</el-tag>
            <span class="question-text" v-html="q.content.replace(/<img[^>]*>/g, '[图片]').replace(/<[^>]+>/g, '')"></span>
          </div>
        </div>

        <div v-if="!loading && questions.length === 0" class="empty-tip">
          暂无符合条件的题目
        </div>
      </div>

      <div class="action-row">
        <el-button @click="selectAll">全选</el-button>
        <el-button @click="selectReverse">反选</el-button>
        <el-button @click="clearSelection">清空</el-button>
        <el-button
          type="primary"
          :disabled="selectedQuestions.length === 0"
          @click="startStudy"
        >
          开始学习 ({{ selectedQuestions.length }})
        </el-button>
      </div>
    </el-card>

    <!-- 学习模式 -->
    <el-card v-else class="study-card">
      <template #header>
        <div class="study-header">
          <span>学习进度：{{ currentIndex + 1 }} / {{ studyQuestions.length }}</span>
          <div class="study-actions">
            <el-button size="small" @click="prevQuestion" :disabled="currentIndex === 0">
              上一题
            </el-button>
            <el-button size="small" @click="nextQuestion" :disabled="currentIndex === studyQuestions.length - 1">
              下一题
            </el-button>
            <el-button size="small" type="danger" @click="exitStudy">
              退出学习
            </el-button>
          </div>
        </div>
      </template>

      <div class="study-content" v-loading="questionLoading">
        <div v-if="currentQuestion" class="question-card">
          <!-- 题目类型 -->
          <div class="question-type">
            <el-tag :type="getTypeTag(currentQuestion.type)">
              {{ getTypeName(currentQuestion.type) }}
            </el-tag>
            <el-tag v-if="currentQuestion.category" size="small" type="info">
              {{ currentQuestion.category }}
            </el-tag>
          </div>

          <!-- 题干 -->
          <div class="question-stem" v-html="currentQuestion.content"></div>

          <!-- 备选答案（学习模式下不显示选项，展示学习提示） -->
          <div class="options-placeholder" @click="revealAnswer">
            <div class="placeholder-hint">
              <el-icon><QuestionFilled /></el-icon>
              <span>点击此处查看答案和解析</span>
            </div>
          </div>

          <!-- 答案和解析（点击后显示） -->
          <div v-if="answerRevealed" class="answer-section">
            <div class="answer-box">
              <div class="answer-label">正确答案</div>
              <div class="answer-value" v-html="formatAnswer(currentQuestion)"></div>
            </div>

            <div v-if="currentQuestion.analysis" class="analysis-box">
              <div class="analysis-label">答案解析</div>
              <div class="analysis-value" v-html="currentQuestion.analysis"></div>
            </div>
          </div>

          <!-- 下一题按钮（显示答案后） -->
          <div v-if="answerRevealed" class="next-hint">
            <el-button type="primary" @click="nextQuestion">
              {{ currentIndex < studyQuestions.length - 1 ? '下一题' : '学习完成' }}
              <el-icon><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>
      </div>

      <!-- 学习进度条 -->
      <div class="progress-bar">
        <el-progress
          :percentage="progressPercentage"
          :stroke-width="8"
          :show-text="false"
        />
      </div>
    </el-card>

    <!-- 学习完成对话框 -->
    <el-dialog v-model="showCompleteDialog" title="学习完成" width="400px" center>
      <div class="complete-content">
        <el-icon class="complete-icon" color="#67C23A"><CircleCheckFilled /></el-icon>
        <p>恭喜！你已完成 {{ studyQuestions.length }} 道题目的学习</p>
      </div>
      <template #footer>
        <el-button type="primary" @click="continueStudy">继续学习</el-button>
        <el-button @click="exitStudy">返回选题</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, QuestionFilled, ArrowRight, CircleCheckFilled } from '@element-plus/icons-vue'
import request from '@/api/index'
import { getCategories } from '@/api/questions'

const loading = ref(false)
const questionLoading = ref(false)
const questions = ref([])
const total = ref(0)
const categories = ref([])

// 分类分组
const morphologyCategories = computed(() => {
  return categories.value.filter(cat => cat.startsWith('形态学/'))
})

const otherCategories = computed(() => {
  return categories.value.filter(cat => !cat.startsWith('形态学/'))
})

const filterType = ref('')
const filterCategory = ref('')
const searchKeyword = ref('')
const selectedQuestions = ref([])

// 学习相关
const studying = ref(false)
const studyQuestions = ref([])
const currentIndex = ref(0)
const currentQuestion = ref(null)
const answerRevealed = ref(false)
const showCompleteDialog = ref(false)

// 加载题目列表
const loadQuestions = async () => {
  loading.value = true
  try {
    const params = {
      skip: 0,
      limit: 100,
      type: filterType.value,
    }
    // 处理分类筛选：形态学/ 表示筛选所有形态学分类
    if (filterCategory.value === '形态学/') {
      // 形态学父级筛选，由后端处理
      params.category = '形态学/'
    } else if (filterCategory.value) {
      params.category = filterCategory.value
    }
    if (searchKeyword.value) {
      params.search = searchKeyword.value
    }
    const res = await request.get('/questions/study', { params })
    questions.value = res.items || []
    total.value = res.total || questions.value.length
  } catch (e) {
    console.error('加载题目失败', e)
    ElMessage.error('加载题目失败')
  } finally {
    loading.value = false
  }
}

// 加载分类
const loadCategories = async () => {
  try {
    const res = await getCategories()
    // API 返回 [{name: "...", count: n}, ...]，需要提取 name 字段
    if (Array.isArray(res)) {
      categories.value = res.map(item => item.name || item)
    } else if (typeof res === 'object' && res !== null) {
      categories.value = Object.values(res)
    } else {
      categories.value = []
    }
  } catch (e) {
    console.error('加载分类失败', e)
  }
}

// 搜索
const handleSearch = () => {
  selectedQuestions.value = []
  loadQuestions()
}

// 切换题目选中状态
const toggleQuestion = (id) => {
  const index = selectedQuestions.value.indexOf(id)
  if (index > -1) {
    selectedQuestions.value.splice(index, 1)
  } else {
    selectedQuestions.value.push(id)
  }
}

// 全选
const selectAll = () => {
  selectedQuestions.value = questions.value.map(q => q.id)
}

// 反选
const selectReverse = () => {
  selectedQuestions.value = questions.value
    .filter(q => !selectedQuestions.value.includes(q.id))
    .map(q => q.id)
}

// 清空选择
const clearSelection = () => {
  selectedQuestions.value = []
}

// 开始学习
const startStudy = async () => {
  if (selectedQuestions.value.length === 0) {
    ElMessage.warning('请先选择要学习的题目')
    return
  }

  // 获取选中的题目详情
  questionLoading.value = true
  try {
    const res = await Promise.all(
      selectedQuestions.value.map(id => request.get(`/questions/study/${id}`))
    )
    studyQuestions.value = res
    currentIndex.value = 0
    currentQuestion.value = studyQuestions.value[0]
    answerRevealed.value = false
    studying.value = true
  } catch (e) {
    console.error('加载题目详情失败', e)
    ElMessage.error('加载题目详情失败')
  } finally {
    questionLoading.value = false
  }
}

// 点击显示答案
const revealAnswer = () => {
  answerRevealed.value = true
}

// 上一题
const prevQuestion = () => {
  if (currentIndex.value > 0) {
    currentIndex.value--
    currentQuestion.value = studyQuestions.value[currentIndex.value]
    answerRevealed.value = false
  }
}

// 下一题
const nextQuestion = () => {
  if (currentIndex.value < studyQuestions.value.length - 1) {
    currentIndex.value++
    currentQuestion.value = studyQuestions.value[currentIndex.value]
    answerRevealed.value = false
  } else {
    // 学习完成
    showCompleteDialog.value = true
  }
}

// 继续学习
const continueStudy = () => {
  showCompleteDialog.value = false
  // 重新开始或继续
  currentIndex.value = 0
  currentQuestion.value = studyQuestions.value[0]
  answerRevealed.value = false
}

// 退出学习
const exitStudy = () => {
  studying.value = false
  showCompleteDialog.value = false
  studyQuestions.value = []
  currentIndex.value = 0
  currentQuestion.value = null
  answerRevealed.value = false
}

// 格式化答案显示
const formatAnswer = (q) => {
  if (!q.answer) return '未设置答案'

  if (q.type === 'single' || q.type === 'judgment') {
    // 单选题或判断题，显示选项内容
    try {
      const options = JSON.parse(q.options || '{}')
      const answerKey = q.answer.trim()
      if (options[answerKey]) {
        return `<strong>${answerKey}.</strong> ${options[answerKey]}`
      }
    } catch (e) {}
    return q.answer
  } else if (q.type === 'multiple') {
    // 多选题
    try {
      const options = JSON.parse(q.options || '{}')
      const answers = q.answer.split(',').map(a => a.trim()).filter(a => a)
      return answers.map(a => {
        const label = options[a] ? `${a}. ${options[a]}` : a
        return `<strong>${label}</strong>`
      }).join(' &nbsp; ')
    } catch (e) {}
    return q.answer
  }
  return q.answer
}

// 获取类型名称
const getTypeName = (type) => {
  const map = { single: '单选题', multiple: '多选题', judgment: '判断题', fill: '填空题' }
  return map[type] || type
}

// 获取类型标签颜色
const getTypeTag = (type) => {
  const map = { single: '', multiple: 'warning', judgment: 'success', fill: 'info' }
  return map[type] || ''
}

// 进度百分比
const progressPercentage = computed(() => {
  if (studyQuestions.value.length === 0) return 0
  return Math.round(((currentIndex.value + 1) / studyQuestions.value.length) * 100)
})

onMounted(() => {
  loadQuestions()
  loadCategories()
})
</script>

<style scoped>
.study-page {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 18px;
  font-weight: 500;
  margin: 0 0 5px 0;
}

.subtitle {
  color: #909399;
  font-size: 14px;
  margin: 0;
}

.mode-card {
  margin-bottom: 20px;
}

.filter-row {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
  flex-wrap: wrap;
}

.stats-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 15px;
  color: #606266;
  font-size: 14px;
}

.question-list {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 10px;
}

.question-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background-color 0.2s;
}

.question-item:last-child {
  border-bottom: none;
}

.question-item:hover {
  background-color: #f5f7fa;
}

.question-item.selected {
  background-color: #ecf5ff;
}

.question-content {
  flex: 1;
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.question-text {
  flex: 1;
  line-height: 1.6;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.empty-tip {
  text-align: center;
  color: #909399;
  padding: 40px 0;
}

.action-row {
  margin-top: 15px;
  display: flex;
  gap: 10px;
}

/* 学习模式样式 */
.study-card {
  max-width: 800px;
  margin: 0 auto;
}

.study-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.study-actions {
  display: flex;
  gap: 10px;
}

.study-content {
  padding: 20px 0;
}

.question-card {
  min-height: 300px;
}

.question-type {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
}

.question-stem {
  font-size: 16px;
  line-height: 1.8;
  color: #303133;
  margin-bottom: 20px;
  padding: 15px;
  background-color: #f5f7fa;
  border-radius: 8px;
}

.question-stem :deep(img) {
  max-width: 100%;
  height: auto;
  margin: 10px 0;
}

.options-placeholder {
  padding: 40px 20px;
  text-align: center;
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  margin-bottom: 20px;
}

.options-placeholder:hover {
  border-color: #409eff;
  background-color: #f0f9ff;
}

.placeholder-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  color: #909399;
  font-size: 14px;
}

.placeholder-hint .el-icon {
  font-size: 32px;
  color: #409eff;
}

.answer-section {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.answer-box,
.analysis-box {
  padding: 15px;
  border-radius: 8px;
  margin-bottom: 15px;
}

.answer-box {
  background-color: #f0f9ff;
  border: 1px solid #409eff;
}

.answer-label,
.analysis-label {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}

.answer-label {
  color: #409eff;
}

.answer-value {
  font-size: 16px;
  color: #303133;
  line-height: 1.6;
}

.analysis-box {
  background-color: #fdf6ec;
  border: 1px solid #e6a23c;
}

.analysis-label {
  color: #e6a23c;
}

.analysis-value {
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
}

.analysis-value :deep(img) {
  max-width: 100%;
  height: auto;
  margin: 10px 0;
}

.next-hint {
  text-align: center;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #ebeef5;
}

.progress-bar {
  margin-top: 20px;
  padding-top: 20px;
}

/* 学习完成对话框 */
.complete-content {
  text-align: center;
  padding: 20px 0;
}

.complete-icon {
  font-size: 60px;
  margin-bottom: 15px;
}

.complete-content p {
  font-size: 16px;
  color: #606266;
  margin: 0;
}
</style>
