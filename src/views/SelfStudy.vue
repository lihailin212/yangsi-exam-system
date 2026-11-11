<template>
  <div class="study-page">
    <div class="page-header">
      <div class="header-main">
        <h2>考生自学</h2>
        <p class="subtitle">随机练习或按题型/题号选题，做完自动判分，答错的题进入「我的错题本」</p>
      </div>
      <el-button
        type="primary"
        size="large"
        :loading="practiceLoading"
        @click="startQuickRandom"
      >
        <el-icon><Refresh /></el-icon>
        随机学习
      </el-button>
    </div>

    <!-- 学习模式选择 -->
    <el-card v-if="!studying && !practicing" class="mode-card">
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

      <!-- 自主练习（做题模式）：随机学习 / 按题型 / 按题号范围 / 按题目编号 -->
      <div class="practice-panel">
        <div class="practice-panel-head">
          <span class="practice-panel-title">自主练习</span>
          <span class="range-hint">做题 → 提交判分 → 答错的题自动进入「我的错题本」</span>
        </div>

        <el-radio-group v-model="practiceMode" class="practice-mode-group">
          <el-radio-button value="random">随机学习</el-radio-button>
          <el-radio-button value="type">按题型</el-radio-button>
          <el-radio-button value="range">按题号范围</el-radio-button>
          <el-radio-button value="number">按题目编号</el-radio-button>
        </el-radio-group>

        <div class="practice-params">
          <template v-if="practiceMode === 'random'">
            <span class="range-text">随机抽</span>
            <el-input v-model="practiceCount" type="number" min="1" max="200" style="width: 90px" />
            <span class="range-text">道题</span>
          </template>

          <template v-else-if="practiceMode === 'type'">
            <el-select v-model="practiceType" placeholder="选择题型" style="width: 140px">
              <el-option label="单选题" value="single" />
              <el-option label="多选题" value="multiple" />
              <el-option label="判断题" value="judgment" />
              <el-option label="填空题" value="fill" />
            </el-select>
            <span class="range-text">抽</span>
            <el-input v-model="practiceCount" type="number" min="0" max="200" style="width: 90px" />
            <span class="range-text">道题（填 0 表示该题型全要）</span>
          </template>

          <template v-else-if="practiceMode === 'range'">
            <span class="range-text">第</span>
            <el-input v-model="practiceStart" type="number" min="1" :max="total || 1" style="width: 90px" placeholder="起始题号" />
            <span class="range-text">题 到 第</span>
            <el-input v-model="practiceEnd" type="number" min="1" :max="total || 1" style="width: 90px" placeholder="结束题号" />
            <span class="range-text">题</span>
          </template>

          <template v-else>
            <el-input v-model="practiceNumbers" placeholder="题目编号，如 1,5,8-12" clearable style="width: 240px" />
            <span class="range-hint">编号是题号（当前筛选列表里的第几题）</span>
          </template>

          <el-button
            type="primary"
            :loading="practiceLoading"
            @click="startPractice()"
          >
            {{ practiceMode === 'random' ? '随机学习' : '开始练习' }}
          </el-button>
        </div>
      </div>

      <el-divider content-position="left">浏览题目（点题干下方区域看答案和解析）</el-divider>

      <!-- 按题号范围选题 -->
      <div class="range-row">
        <span class="range-label">按题号选题：</span>
        <span class="range-text">第</span>
        <el-input
          v-model="rangeFrom"
          type="number"
          min="1"
          :max="total || 1"
          style="width: 96px"
          placeholder="起始题号"
        />
        <span class="range-text">题 到 第</span>
        <el-input
          v-model="rangeTo"
          type="number"
          min="1"
          :max="total || 1"
          style="width: 96px"
          placeholder="结束题号"
        />
        <span class="range-text">题</span>
        <el-button size="small" @click="selectRange">选这批</el-button>
        <el-button size="small" @click="selectAll">全选（{{ allIds.length }}）</el-button>
        <span class="range-hint">当前筛选共 {{ total }} 道题，题号即下方列表顺序</span>
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

      <el-pagination
        v-if="total > pageSize"
        v-model:current-page="page"
        class="pager"
        background
        layout="prev, pager, next, jumper, total"
        :page-size="pageSize"
        :total="total"
        @current-change="loadQuestions"
      />

      <div class="action-row">
        <el-button @click="selectAll">全选</el-button>
        <el-button @click="selectReverse">反选</el-button>
        <el-button @click="clearSelection">清空</el-button>
        <el-button
          type="primary"
          :disabled="selectedQuestions.length === 0"
          :loading="questionLoading"
          @click="startStudy"
        >
          开始学习 ({{ selectedQuestions.length }})
        </el-button>
      </div>
    </el-card>

    <!-- 自主练习（做题模式） -->
    <el-card v-else-if="practicing" class="practice-card">
      <template #header>
        <div class="study-header">
          <span>自主练习：第 {{ practiceIndex + 1 }} / {{ practiceItems.length }} 题</span>
          <span class="practice-score">
            答对 {{ practiceCorrectCount }} 题 · 答错 {{ practiceWrongCount }} 题
          </span>
        </div>
      </template>

      <div v-if="currentPracticeQuestion" class="question-card">
        <div class="question-type">
          <el-tag :type="getTypeTag(currentPracticeQuestion.type)">
            {{ getTypeName(currentPracticeQuestion.type) }}
          </el-tag>
          <el-tag v-if="currentPracticeQuestion.seq" size="small" type="info">
            第 {{ currentPracticeQuestion.seq }} 题
          </el-tag>
          <el-tag v-if="currentPracticeQuestion.category" size="small" type="info">
            {{ currentPracticeQuestion.category }}
          </el-tag>
        </div>

        <!-- 题干 -->
        <div class="question-stem" v-html="currentPracticeQuestion.content" @click="handleStemImageClick"></div>

        <!-- 填空题 -->
        <div v-if="currentPracticeQuestion.type === 'fill'" class="fill-area">
          <div class="fill-label">我的答案</div>
          <el-input
            v-model="practiceFillAnswer"
            type="textarea"
            :rows="2"
            maxlength="100"
            :disabled="practiceSubmitted"
            placeholder="请填写答案"
          />
        </div>

        <!-- 选择题 -->
        <div v-if="practiceHasOptions" class="options-area">
          <div
            v-for="opt in practiceOptionList"
            :key="opt.key"
            class="option-item"
            :class="{
              chosen: practiceChoiceKeys.includes(opt.key),
              correct: practiceSubmitted && practiceIsCorrectOption(opt.key),
              wrong: practiceSubmitted && practiceChoiceKeys.includes(opt.key) && !practiceIsCorrectOption(opt.key)
            }"
            @click="togglePracticeChoice(opt.key)"
          >
            <span class="option-key">{{ opt.key }}</span>
            <span class="option-val" v-html="opt.label"></span>
            <el-icon v-if="practiceChoiceKeys.includes(opt.key)" class="option-mark"><CircleCheckFilled /></el-icon>
          </div>
          <div v-if="!practiceSubmitted" class="choice-tip">点击选项作答，然后点下方「提交本题」</div>
        </div>

        <!-- 判分结果 -->
        <div v-if="practiceSubmitted && currentPracticeResult" class="answer-section">
          <div
            class="answer-box"
            :class="{ 'answer-correct': currentPracticeResult.correct, 'answer-wrong': !currentPracticeResult.correct }"
          >
            <div class="answer-label">{{ currentPracticeResult.correct ? '回答正确' : '回答错误' }}</div>
            <div class="answer-value">正确答案：{{ currentPracticeResult.correct_answer }}</div>
            <div v-if="!currentPracticeResult.correct" class="answer-value">
              我的答案：{{ practiceMyAnswerText || '（未作答）' }}
            </div>
            <div v-if="!currentPracticeResult.correct" class="answer-label">本题已加入「我的错题本」</div>
          </div>

          <div v-if="currentPracticeResult.analysis" class="analysis-box">
            <div class="analysis-label">答案解析</div>
            <div class="analysis-value" v-html="currentPracticeResult.analysis"></div>
          </div>
        </div>

        <!-- 底部操作栏 -->
        <div class="study-nav">
          <el-button :disabled="practiceIndex === 0" @click="prevPracticeQuestion">
            上一题
          </el-button>
          <el-button
            v-if="!practiceSubmitted"
            type="primary"
            :loading="practiceSubmitting"
            :disabled="!practiceHasAnswer"
            @click="submitPracticeAnswer"
          >
            提交本题
          </el-button>
          <el-button v-else type="primary" @click="nextPracticeQuestion">
            {{ practiceIndex === practiceItems.length - 1 ? '交卷' : '下一题' }}
            <el-icon><ArrowRight /></el-icon>
          </el-button>
          <el-button type="danger" plain @click="exitPractice">
            结束练习
          </el-button>
        </div>
      </div>

      <div class="progress-bar">
        <el-progress :percentage="practiceProgress" :stroke-width="8" :show-text="false" />
      </div>
    </el-card>

    <!-- 学习模式 -->
    <el-card
      v-else
      ref="studyCardRef"
      class="study-card"
      :class="{ dragging: isDragging }"
      @mousedown="onHeaderMouseDown"
    >
      <template #header>
        <div
          class="study-header"
          title="按住标题栏可拖动窗口，双击标题栏复位"
          @dblclick="resetCardPosition"
        >
          <span>学习进度：{{ currentIndex + 1 }} / {{ studyIds.length }}</span>
          <span class="study-drag-tip">按住标题栏可拖动窗口</span>
        </div>
      </template>

      <div class="study-content" v-loading="detailLoading">
        <div v-if="!currentQuestion" class="loading-tip">题目加载中…</div>
        <div v-else class="question-card">
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
          <div class="question-stem" v-html="currentQuestion.content" @click="handleStemImageClick"></div>

          <!-- 填空题：自己先填答案，再对照标准答案 -->
          <div v-if="currentQuestion.type === 'fill'" class="fill-area">
            <div class="fill-label">我的答案</div>
            <el-input
              v-model="fillAnswer"
              type="textarea"
              :rows="2"
              maxlength="100"
              placeholder="请填写图中所示的名称"
            />
            <div v-if="answerRevealed" class="fill-result" :class="fillResultClass">
              <el-icon v-if="fillResultType === 'correct'"><CircleCheckFilled /></el-icon>
              <el-icon v-else-if="fillResultType === 'wrong'"><CircleCloseFilled /></el-icon>
              <span>{{ fillResultText }}</span>
            </div>
            <div v-else class="fill-tip">填好后点击下方「查看答案和解析」对照答案</div>
          </div>

          <!-- 备选答案（可点选作答） -->
          <div v-if="hasOptions" class="options-area">
            <div
              v-for="opt in optionList"
              :key="opt.key"
              class="option-item"
              :class="{
                chosen: isChosen(opt.key),
                correct: answerRevealed && isCorrectOption(opt.key),
                wrong: answerRevealed && isChosen(opt.key) && !isCorrectOption(opt.key)
              }"
              @click="toggleChoice(opt.key)"
            >
              <span class="option-key">{{ opt.key }}</span>
              <span class="option-val" v-html="opt.label"></span>
              <el-icon v-if="isChosen(opt.key)" class="option-mark"><CircleCheckFilled /></el-icon>
            </div>
            <div v-if="!answerRevealed" class="choice-tip">点击选项作答，然后点下方查看答案和解析</div>
            <div
              v-else
              class="choice-result"
              :class="{
                correct: choiceResultType === 'correct',
                wrong: choiceResultType === 'wrong',
                none: choiceResultType === 'none'
              }"
            >
              {{ choiceResultText }}
            </div>
          </div>

          <!-- 学习提示（点击后显示答案和解析） -->
          <div class="options-placeholder" @click="revealAnswer">
            <div class="placeholder-hint">
              <el-icon><QuestionFilled /></el-icon>
              <span>{{ answerRevealed ? '答案和解析已显示' : '点击此处查看答案和解析' }}</span>
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

          <!-- 底部操作栏：上一题 / 下一题（最后一题为提交）/ 退出学习 -->
          <div class="study-nav">
            <el-button :disabled="currentIndex === 0" @click="prevQuestion">
              上一题
            </el-button>
            <el-button type="primary" @click="handleNavNext">
              {{ currentIndex < studyIds.length - 1 ? '下一题' : '提交学习' }}
              <el-icon><ArrowRight /></el-icon>
            </el-button>
            <el-button type="danger" plain @click="exitStudy">
              退出学习
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

    <!-- 图片预览 -->
    <ImagePreview v-model="previewVisible" :src="previewSrc" title="题目图片" />

    <!-- 练习小结 -->
    <!-- 学习完成对话框 -->
    <el-dialog v-model="showPracticeSummary" title="练习完成" width="420px" center>
      <div class="complete-content">
        <div class="practice-summary">
          <div class="summary-item correct">答对 {{ practiceSummary.correct }} 题</div>
          <div class="summary-item wrong">答错 {{ practiceSummary.wrong }} 题</div>
          <div class="summary-item none">未作答 {{ practiceSummary.unanswered }} 题</div>
        </div>
        <p class="summary-tip">
          答错的题目已加入「我的错题本」，可以随时回看并重新练习。
        </p>
      </div>
      <template #footer>
        <el-button type="primary" @click="goWrongBook">查看错题本</el-button>
        <el-button @click="restartPractice">再练一组</el-button>
        <el-button @click="exitPractice">返回选题</el-button>
      </template>
    </el-dialog>

    <!-- 学习完成对话框 -->
    <el-dialog v-model="showCompleteDialog" title="学习完成" width="400px" center>
      <div class="complete-content">
        <el-icon class="complete-icon" color="#67C23A"><CircleCheckFilled /></el-icon>
        <p>恭喜！你已完成 {{ studyIds.length }} 道题目的学习</p>
      </div>
      <template #footer>
        <el-button type="primary" @click="continueStudy">继续学习</el-button>
        <el-button @click="exitStudy">返回选题</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, QuestionFilled, ArrowRight, CircleCheckFilled, CircleCloseFilled, Refresh } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import request from '@/api/index'
import { getCategories } from '@/api/questions'
import {
  generatePractice,
  submitPracticeAnswer as submitPracticeAnswerApi,
  finishPractice as finishPracticeApi,
} from '@/api/selfStudy'
import ImagePreview from '@/components/ImagePreview.vue'

const loading = ref(false)
const questionLoading = ref(false)
const detailLoading = ref(false)
const questions = ref([])
const total = ref(0)
const categories = ref([])

// 列表分页 + 当前筛选下的全部题目 id（题号即 allIds 的下标+1）
const page = ref(1)
const pageSize = 100
const allIds = ref([])
const rangeFrom = ref('')
const rangeTo = ref('')

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
// 题目详情懒加载：先只拿 id，翻到哪题再取哪题的详情，
// 这样一次选 1000 多道题也能秒开。
const studyIds = ref([])
const studyDetails = reactive({})
const currentIndex = ref(0)
const currentQuestion = computed(() => {
  const id = studyIds.value[currentIndex.value]
  return id ? studyDetails[id] || null : null
})
const answerRevealed = ref(false)
const showCompleteDialog = ref(false)

// 学习窗口拖动
// 用 position: fixed 做真正的浮动窗口：不会被页面滚动容器裁剪，
// 拖到哪儿都能完整显示，标题栏也永远抓得到。
const studyCardRef = ref(null)
const isDragging = ref(false)
const studyPos = ref({ left: 0, top: 0 })
let dragState = null
let pendingPos = null

const getCardEl = () => studyCardRef.value?.$el || studyCardRef.value

// 窗口位置：left/top 是"锚点"，拖动过程用 transform 做位移。
// transform 走合成层，不触发重排，鼠标一动窗口就动，不会拖着一张影。
const setAnchor = (left, top) => {
  const el = getCardEl()
  if (!el) return
  el.style.transform = ''
  el.style.left = `${Math.round(left)}px`
  el.style.top = `${Math.round(top)}px`
  studyPos.value = { left, top }
}

// 把学习窗口夹进屏幕内：高度不超过屏幕、底边不超出可视区
// （否则底部按钮会跑到屏幕外，得滚动页面才够得到）
const clampCardToViewport = () => {
  const el = getCardEl()
  if (!el) return
  const vh = window.innerHeight
  const vw = window.innerWidth
  const maxH = Math.max(240, vh - 24)
  el.style.maxHeight = `${maxH}px`
  const h = el.offsetHeight
  const w = el.offsetWidth
  let top = studyPos.value.top
  let left = studyPos.value.left
  if (top + h > vh - 12) top = Math.max(12, vh - 12 - h)
  if (left + w > vw - 12) left = Math.max(12, vw - 12 - w)
  studyPos.value = { left, top }
  el.style.left = `${Math.round(left)}px`
  el.style.top = `${Math.round(top)}px`
}

// 进入学习模式后：先量出卡片在页面里的位置，再切换成浮动窗口
const initStudyPos = async () => {
  await nextTick()
  const el = getCardEl()
  if (!el) return
  const rect = el.getBoundingClientRect()
  setAnchor(rect.left, rect.top)
  clampCardToViewport()
}

// 双击标题栏：回到主区域居中位置
const resetCardPosition = () => {
  const el = getCardEl()
  if (!el) return
  const main = document.querySelector('.main-content')
  const mainRect = main?.getBoundingClientRect()
  const rect = el.getBoundingClientRect()
  const areaLeft = mainRect ? mainRect.left : 0
  const areaWidth = mainRect ? mainRect.width : window.innerWidth
  const left = Math.max(areaLeft + 8, areaLeft + (areaWidth - rect.width) / 2)
  const top = (mainRect ? mainRect.top : 0) + 16
  setAnchor(left, top)
}

// 按住标题栏拖动窗口
const onHeaderMouseDown = (e) => {
  if (e.button !== 0) return
  // 只有按住卡片顶部标题栏才拖动，题干/选项区域照常点选
  if (!e.target.closest('.el-card__header')) return
  // 标题栏里的按钮不触发拖动
  if (e.target.closest('button')) return
  const el = studyCardRef.value?.$el || studyCardRef.value
  if (!el) return

  isDragging.value = true
  // 清掉上一次拖动残留的位移，保证起手位置就是鼠标位置
  el.style.transform = ''
  const rect = el.getBoundingClientRect()
  // 基准位置取当前实际位置，保证和鼠标完全对齐，不会有累积误差
  setAnchor(rect.left, rect.top)
  dragState = {
    anchorLeft: rect.left,
    anchorTop: rect.top,
    grabX: e.clientX - rect.left,
    grabY: e.clientY - rect.top,
  }
  document.addEventListener('mousemove', onHeaderMouseMove)
  document.addEventListener('mouseup', onHeaderMouseUp)
  e.preventDefault()
}

const onHeaderMouseMove = (e) => {
  if (!dragState) return
  const el = getCardEl()
  if (!el) return
  // 始终给标题栏留出可抓取的位置，窗口不会被拖到完全抓不到的地方
  const maxLeft = Math.max(0, window.innerWidth - 140)
  const maxTop = Math.max(0, window.innerHeight - 60)
  const left = Math.min(Math.max(e.clientX - dragState.grabX, 0), maxLeft)
  const top = Math.min(Math.max(e.clientY - dragState.grabY, 0), maxTop)
  // 同步写 transform：不等下一帧，鼠标到哪窗口就到哪
  el.style.transform = `translate3d(${Math.round(left - dragState.anchorLeft)}px, ${Math.round(top - dragState.anchorTop)}px, 0)`
  pendingPos = { left, top }
}

const onHeaderMouseUp = () => {
  isDragging.value = false
  dragState = null
  // 松手时把 transform 位移固化到 left/top，下次拖动从新位置开始
  if (pendingPos) {
    setAnchor(pendingPos.left, pendingPos.top)
    pendingPos = null
  }
  document.removeEventListener('mousemove', onHeaderMouseMove)
  document.removeEventListener('mouseup', onHeaderMouseUp)
}

// 图片预览
const previewVisible = ref(false)
const previewSrc = ref('')

// 点击题干里的图片打开预览
const handleStemImageClick = (e) => {
  const img = e.target.closest('img')
  if (!img || !img.src) return
  previewSrc.value = img.src
  previewVisible.value = true
}

// 当前筛选条件（列表和"全部 id"共用，保证题号对得上）
const buildFilterParams = () => {
  const params = { type: filterType.value }
  if (filterCategory.value) params.category = filterCategory.value
  if (searchKeyword.value) params.search = searchKeyword.value
  return params
}

// 加载题目列表（分页）
const loadQuestions = async () => {
  loading.value = true
  try {
    const params = {
      ...buildFilterParams(),
      skip: (page.value - 1) * pageSize,
      limit: pageSize,
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

// 加载当前筛选条件下的全部题目 id（顺序与列表一致）
const loadAllIds = async () => {
  try {
    const res = await request.get('/questions/study/ids', { params: buildFilterParams() })
    allIds.value = res.ids || []
  } catch (e) {
    console.error('加载题目编号失败', e)
    allIds.value = []
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
  page.value = 1
  rangeFrom.value = ''
  rangeTo.value = ''
  loadQuestions()
  loadAllIds()
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

// 全选（选中当前筛选下的全部题目，不只是当前这一页）
const selectAll = () => {
  if (!allIds.value.length) {
    ElMessage.warning('没有可选择的题目')
    return
  }
  selectedQuestions.value = [...allIds.value]
}

// 反选（对当前筛选下的全部题目取反）
const selectReverse = () => {
  if (!allIds.value.length) {
    ElMessage.warning('没有可选择的题目')
    return
  }
  const selected = new Set(selectedQuestions.value)
  selectedQuestions.value = allIds.value.filter(id => !selected.has(id))
}

// 按题号范围选题：第 N 题 到 第 M 题（题号即列表顺序）
const selectRange = () => {
  const totalCount = allIds.value.length
  if (!totalCount) {
    ElMessage.warning('没有可选择的题目')
    return
  }
  let from = parseInt(rangeFrom.value, 10)
  let to = parseInt(rangeTo.value, 10)
  if (!from && !to) {
    ElMessage.warning('请填写起止题号')
    return
  }
  if (!from) from = 1
  if (!to) to = from
  if (from > to) [from, to] = [to, from]
  if (from < 1) from = 1
  if (to > totalCount) to = totalCount
  selectedQuestions.value = allIds.value.slice(from - 1, to)
  ElMessage.success(`已选中第 ${from} - ${to} 题，共 ${selectedQuestions.value.length} 道`)
}

// 清空选择
const clearSelection = () => {
  selectedQuestions.value = []
}

// 批量取题目详情：优先一次请求搞定，后端不支持时退化为小批量并发
const fetchStudyDetails = async (ids) => {
  try {
    const res = await request.post('/questions/study/batch', { ids }, { silent: true })
    if (Array.isArray(res)) return res
  } catch (e) {
    console.warn('批量获取题目详情失败，改用逐题获取', e)
  }
  // 退路：每批 5 个并发，避免把后端打爆
  const out = []
  const size = 5
  for (let i = 0; i < ids.length; i += size) {
    const part = await Promise.all(
      ids.slice(i, i + size).map(id => request.get(`/questions/study/${id}`, { silent: true }))
    )
    out.push(...part)
  }
  return out
}

// 按列表顺序排一下选中的题目，保证学习顺序和题号一致
const sortSelectedByListOrder = (ids) => {
  const pos = new Map(allIds.value.map((id, i) => [id, i]))
  return [...ids].sort((a, b) => {
    const pa = pos.has(a) ? pos.get(a) : Number.MAX_SAFE_INTEGER
    const pb = pos.has(b) ? pos.get(b) : Number.MAX_SAFE_INTEGER
    return pa - pb
  })
}

// 确保第 index 题（及后面几题）的详情已加载
const ensureDetail = async (index, lookAhead = 8) => {
  const need = []
  const end = Math.min(index + lookAhead, studyIds.value.length)
  for (let i = index; i < end; i++) {
    const id = studyIds.value[i]
    if (id && !studyDetails[id]) need.push(id)
  }
  if (!need.length) return
  detailLoading.value = true
  try {
    const list = await fetchStudyDetails(need)
    list.forEach((d) => { studyDetails[d.id] = d })
    await nextTick()
    clampCardToViewport()
  } catch (e) {
    console.error('加载题目详情失败', e)
    ElMessage.error('加载题目详情失败，请稍后重试')
  } finally {
    detailLoading.value = false
  }
}

// 开始学习
const startStudy = async () => {
  if (selectedQuestions.value.length === 0) {
    ElMessage.warning('请先选择要学习的题目')
    return
  }

  questionLoading.value = true
  detailLoading.value = true
  try {
    studyIds.value = sortSelectedByListOrder(selectedQuestions.value)
    Object.keys(studyDetails).forEach((k) => { delete studyDetails[k] })
    currentIndex.value = 0
    answerRevealed.value = false
    studying.value = true
    await nextTick()
    // 只加载首屏几题的详情，翻到哪题再取哪题
    await ensureDetail(0, 8)
    await initStudyPos()
  } catch (e) {
    console.error('加载题目详情失败', e)
    ElMessage.error('加载题目详情失败，请稍后重试')
  } finally {
    questionLoading.value = false
    detailLoading.value = false
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
    answerRevealed.value = false
    ensureDetail(currentIndex.value)
  }
}

// 底部主按钮：不是最后一题就下一题，最后一题直接提交（不用先看解析）
const handleNavNext = () => {
  if (currentIndex.value < studyIds.value.length - 1) {
    nextQuestion()
  } else {
    showCompleteDialog.value = true
  }
}

// 下一题
const nextQuestion = () => {
  if (currentIndex.value < studyIds.value.length - 1) {
    currentIndex.value++
    answerRevealed.value = false
    ensureDetail(currentIndex.value)
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
  answerRevealed.value = false
  ensureDetail(0, 8)
}

// 退出学习
const exitStudy = () => {
  studying.value = false
  studyPos.value = { left: 0, top: 0 }
  isDragging.value = false
  pendingPos = null
  showCompleteDialog.value = false
  studyIds.value = []
  Object.keys(studyDetails).forEach((k) => { delete studyDetails[k] })
  currentIndex.value = 0
  answerRevealed.value = false
}

// 格式化答案显示
const formatAnswer = (q) => {
  if (!q.answer) return '本题暂不显示标准答案'

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

// 当前题目的选项
const parsedOptions = computed(() => {
  try {
    const obj = JSON.parse(currentQuestion.value?.options || '{}')
    return obj && typeof obj === 'object' ? obj : {}
  } catch (e) {
    return {}
  }
})

// 要展示的选项列表
// 判断题在题库里存的是空选项 + 「正确/错误」文本，这里转成两个可看的选项
const optionList = computed(() => {
  const q = currentQuestion.value
  if (!q) return []
  const entries = Object.entries(parsedOptions.value)
  if (!entries.length) return []
  const allBlank = entries.every(([, v]) => !String(v ?? '').trim())
  if (q.type === 'judgment' && allBlank) {
    return [
      { key: 'A', label: '正确' },
      { key: 'B', label: '错误' },
    ]
  }
  return entries.map(([key, val]) => ({ key, label: val }))
})

// 是否有可展示的选项
const hasOptions = computed(() => optionList.value.length > 0)

// 选择题的作答（按题目 id 存，切题不丢）
const studentChoices = reactive({})

// 当前题目的选择
const choiceKeys = computed(() => {
  const id = currentQuestion.value?.id
  return id && studentChoices[id] ? studentChoices[id] : []
})

// 该选项是否被选中
const isChosen = (key) => choiceKeys.value.includes(String(key))

// 点选选项：单选/判断题单选，多选题可多选；再点一次取消
const toggleChoice = (key) => {
  const q = currentQuestion.value
  if (!q) return
  const id = q.id
  const keyStr = String(key)
  const cur = studentChoices[id] || []
  if (q.type === 'multiple') {
    studentChoices[id] = cur.includes(keyStr) ? cur.filter((k) => k !== keyStr) : [...cur, keyStr]
  } else {
    studentChoices[id] = cur.includes(keyStr) ? [] : [keyStr]
  }
}

// 本题是否有标准答案（考试中的题，后端会对考生隐藏答案）
const hasStandardAnswer = computed(() =>
  !!String(currentQuestion.value?.answer || '').trim()
)

// 作答结果：答对 / 答错 / 未作答
const choiceResultType = computed(() => {
  if (!answerRevealed.value) return ''
  const chosen = choiceKeys.value
  if (!chosen.length) return 'none'
  if (!hasStandardAnswer.value) return 'none'
  const q = currentQuestion.value
  if (q?.type === 'multiple') {
    const right = answerKeys.value
    if (!right.length) return 'none'
    // 多选：全部选对且没有多选才算对
    const hit = chosen.length === right.length && chosen.every((k) => right.includes(String(k)))
    return hit ? 'correct' : 'wrong'
  }
  // 单选/判断题：判断题的标准答案是「正确/错误」文本，用 isCorrectOption 判断
  return isCorrectOption(chosen[0]) ? 'correct' : 'wrong'
})

const choiceResultText = computed(() => {
  const chosen = choiceKeys.value.map((k) => {
    const opt = optionList.value.find((o) => o.key === k)
    return opt ? `${k}. ${String(opt.label).replace(/<[^>]+>/g, '')}` : k
  }).join('、')
  if (choiceResultType.value === 'correct') return `你的选择：${chosen}　✔ 回答正确`
  if (choiceResultType.value === 'wrong') return `你的选择：${chosen}　✘ 回答不正确`
  if (chosen && !hasStandardAnswer.value) {
    return `你的选择：${chosen}　（本题正在考试中，暂不显示标准答案）`
  }
  return chosen ? `你的选择：${chosen}` : '未作答，正确答案见下方'
})

// 填空题：考生自己填的答案（按题目 id 存，切题不丢）
const studentAnswers = ref({})
const fillAnswer = computed({
  get: () => (currentQuestion.value ? studentAnswers.value[currentQuestion.value.id] || '' : ''),
  set: (v) => {
    if (currentQuestion.value) {
      studentAnswers.value[currentQuestion.value.id] = v
    }
  },
})

// 文本归一化：去掉空格和常见标点，方便比对
const normalizeText = (str) =>
  String(str ?? '')
    .trim()
    .replace(/\s+/g, '')
    .replace(/[（）()【】\[\]，,。.、；;：:！!？?·\-—_"'"]/g, '')
    .toLowerCase()

// 填空题作答是否正确
const isFillCorrect = computed(() => {
  const q = currentQuestion.value
  if (!q || q.type !== 'fill') return false
  const user = normalizeText(fillAnswer.value)
  if (!user) return false
  const stdList = String(q.answer || '')
    .split(/[|｜\/、;；]/)
    .map(normalizeText)
    .filter(Boolean)
  if (!stdList.length) return false
  return stdList.some((a) => a === user || (user.length >= 2 && a.includes(user)))
})

// 填空题批改结果
const fillResultType = computed(() => {
  if (!answerRevealed.value) return ''
  if (!normalizeText(fillAnswer.value)) return 'none'
  // 题目正在考试中时后端会清空标准答案，这时只记录作答，不判对错
  if (!String(currentQuestion.value?.answer || '').trim()) return 'submitted'
  return isFillCorrect.value ? 'correct' : 'wrong'
})

const fillResultText = computed(() => {
  if (fillResultType.value === 'correct') return '回答正确'
  if (fillResultType.value === 'wrong') return '回答不正确，正确答案见下方'
  if (fillResultType.value === 'submitted') return '已作答，本题正在考试中，暂不显示标准答案'
  return '未作答，正确答案见下方'
})

const fillResultClass = computed(() => ({
  correct: fillResultType.value === 'correct',
  wrong: fillResultType.value === 'wrong',
  submitted: fillResultType.value === 'submitted',
}))

// 正确答案集合
const answerKeys = computed(() => {
  const ans = currentQuestion.value?.answer
  if (!ans) return []
  return String(ans).split(',').map(a => a.trim()).filter(a => a)
})

// 该选项是否为正确答案
const isCorrectOption = (key) => {
  const q = currentQuestion.value
  if (!q) return false
  if (q.type === 'judgment') {
    // 判断题的标准答案是「正确/错误」文本，和选项文字比对
    const label = optionList.value.find((o) => o.key === key)?.label
    if (!label) return false
    const ans = normalizeText(q.answer)
    const lb = normalizeText(label)
    if (ans === lb) return true
    // 兼容「对/错」「T/F」这类写法
    const truthy = ['正确', '对', 't', 'true', '是', 'y', 'yes']
    const falsy = ['错误', '错', 'f', 'false', '否', 'n', 'no']
    if (truthy.includes(lb)) return truthy.includes(ans)
    if (falsy.includes(lb)) return falsy.includes(ans)
    return false
  }
  return answerKeys.value.includes(String(key))
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
  if (studyIds.value.length === 0) return 0
  return Math.round(((currentIndex.value + 1) / studyIds.value.length) * 100)
})

// ===== 自主练习（做题模式）=====
const router = useRouter()

const practicing = ref(false)
const practiceLoading = ref(false)
const practiceSubmitting = ref(false)
// 选题方式：random 随机学习 / type 按题型 / range 按题号范围 / number 按题目编号
const practiceMode = ref('random')
const practiceType = ref('')
const practiceCount = ref(10)
const practiceStart = ref('')
const practiceEnd = ref('')
const practiceNumbers = ref('')
const practiceItems = ref([])
const practiceIndex = ref(0)
// 考生作答：{题目id: 作答内容}（多选题存逗号分隔的选项键）
const practiceAnswers = ref({})
// 判分结果：{题目id: 后端返回的对错/正确答案/解析}
const practiceResults = ref({})
const showPracticeSummary = ref(false)
const practiceSummary = ref({ total: 0, answered: 0, correct: 0, wrong: 0, unanswered: 0 })

const currentPracticeQuestion = computed(() => practiceItems.value[practiceIndex.value] || null)
const currentPracticeResult = computed(() => {
  const id = currentPracticeQuestion.value?.id
  return id ? practiceResults.value[id] || null : null
})
// 本题是否已经提交判过分
const practiceSubmitted = computed(() => !!currentPracticeResult.value)

// 当前题的选项（判断题在题库里选项是空的，这里补上「正确/错误」）
const practiceOptionList = computed(() => {
  const q = currentPracticeQuestion.value
  if (!q) return []
  let obj = {}
  try {
    const parsed = JSON.parse(q.options || '{}')
    obj = parsed && typeof parsed === 'object' ? parsed : {}
  } catch (e) {
    obj = {}
  }
  const entries = Object.entries(obj)
  if (!entries.length) return []
  const allBlank = entries.every(([, v]) => !String(v ?? '').trim())
  if (q.type === 'judgment' && allBlank) {
    return [
      { key: 'A', label: '正确' },
      { key: 'B', label: '错误' },
    ]
  }
  return entries.map(([key, val]) => ({ key, label: val }))
})
const practiceHasOptions = computed(() => practiceOptionList.value.length > 0)

// 当前题选中的选项
const practiceChoiceKeys = computed(() => {
  const id = currentPracticeQuestion.value?.id
  if (!id) return []
  const raw = practiceAnswers.value[id]
  if (!raw) return []
  return String(raw).split(',').map(s => s.trim()).filter(Boolean)
})

// 填空题作答
const practiceFillAnswer = computed({
  get: () => {
    const id = currentPracticeQuestion.value?.id
    return id ? practiceAnswers.value[id] || '' : ''
  },
  set: (v) => {
    const id = currentPracticeQuestion.value?.id
    if (id) practiceAnswers.value = { ...practiceAnswers.value, [id]: v }
  },
})

// 提交给后端的作答内容
const practiceAnswerValue = computed(() => {
  const q = currentPracticeQuestion.value
  if (!q) return ''
  if (q.type === 'multiple') return practiceChoiceKeys.value.join(',')
  if (q.type === 'fill') return practiceFillAnswer.value
  return practiceChoiceKeys.value[0] || ''
})

// 本题是否已作答（决定「提交本题」能不能点）
const practiceHasAnswer = computed(() => {
  const q = currentPracticeQuestion.value
  if (!q) return false
  if (q.type === 'fill') return !!String(practiceFillAnswer.value).trim()
  return practiceChoiceKeys.value.length > 0
})

// 我的作答文字（答错时回显）
const practiceMyAnswerText = computed(() => {
  const q = currentPracticeQuestion.value
  if (!q) return ''
  if (q.type === 'fill') return practiceFillAnswer.value
  return practiceChoiceKeys.value.join('、')
})

// 正确答案的选项键（判分后高亮正确项）
const practiceCorrectKeys = computed(() => {
  const res = currentPracticeResult.value
  return Array.isArray(res?.correct_keys) ? res.correct_keys.map(String) : []
})
const practiceIsCorrectOption = (key) => practiceCorrectKeys.value.includes(String(key))

const practiceProgress = computed(() => {
  if (!practiceItems.value.length) return 0
  return Math.round(((practiceIndex.value + 1) / practiceItems.value.length) * 100)
})
const practiceCorrectCount = computed(
  () => Object.values(practiceResults.value).filter(r => r.correct).length
)
const practiceWrongCount = computed(
  () => Object.values(practiceResults.value).filter(r => !r.correct).length
)

// 点选选项：单选/判断题单选，多选题可多选；已提交的题不能再改
const togglePracticeChoice = (key) => {
  const q = currentPracticeQuestion.value
  if (!q || practiceSubmitted.value) return
  const id = q.id
  const keyStr = String(key)
  const cur = practiceChoiceKeys.value
  if (q.type === 'multiple') {
    const next = cur.includes(keyStr) ? cur.filter(k => k !== keyStr) : [...cur, keyStr]
    practiceAnswers.value = { ...practiceAnswers.value, [id]: next.join(',') }
  } else {
    practiceAnswers.value = { ...practiceAnswers.value, [id]: keyStr }
  }
}

// 生成一组练习题
const startPractice = async (mode) => {
  const useMode = mode || practiceMode.value
  const qType = useMode === 'type' ? practiceType.value : filterType.value
  if (useMode === 'type' && !qType) {
    ElMessage.warning('请选择题型')
    return
  }
  practiceLoading.value = true
  // 开始练习时先退出「看答案」的学习模式：两个模式共用这一页，不能同时开
  studying.value = false
  try {
    const res = await generatePractice({
      mode: useMode,
      count: Number(practiceCount.value) || 0,
      q_type: qType,
      category: filterCategory.value,
      search: searchKeyword.value,
      start: Number(practiceStart.value) || 0,
      end: Number(practiceEnd.value) || 0,
      numbers: practiceNumbers.value,
    })
    if (!res || !Array.isArray(res.items) || !res.items.length) {
      ElMessage.warning('没有符合条件的题目')
      return
    }
    practiceMode.value = useMode
    practiceItems.value = res.items
    practiceAnswers.value = {}
    practiceResults.value = {}
    practiceIndex.value = 0
    practicing.value = true
    ElMessage.success(`已生成 ${res.items.length} 道练习题`)
  } catch (e) {
    console.error('生成练习题失败', e)
    ElMessage.error('生成练习题失败，请稍后重试')
  } finally {
    practiceLoading.value = false
  }
}

// 页头的「随机学习」：一键随机抽题
const startQuickRandom = () => startPractice('random')

// 提交本题：后端判分，答错的自动进错题本
const submitPracticeAnswer = async () => {
  const q = currentPracticeQuestion.value
  if (!q || practiceSubmitting.value) return
  practiceSubmitting.value = true
  try {
    const res = await submitPracticeAnswerApi({
      question_id: q.id,
      answer: practiceAnswerValue.value,
    })
    practiceResults.value = { ...practiceResults.value, [q.id]: res }
  } catch (e) {
    console.error('判分失败', e)
    ElMessage.error('判分失败，请稍后重试')
  } finally {
    practiceSubmitting.value = false
  }
}

const prevPracticeQuestion = () => {
  if (practiceIndex.value > 0) {
    practiceIndex.value--
  }
}

const nextPracticeQuestion = async () => {
  if (practiceIndex.value < practiceItems.value.length - 1) {
    practiceIndex.value++
  } else {
    await finishPractice()
  }
}

// 交卷：没做的题按做错处理，记进错题本
const finishPractice = async () => {
  const unanswered = practiceItems.value
    .filter(item => !practiceResults.value[item.id])
    .map(item => item.id)
  try {
    if (unanswered.length) {
      await finishPracticeApi({ unanswered_ids: unanswered })
    }
  } catch (e) {
    console.error('交卷失败', e)
  }
  const answered = Object.keys(practiceResults.value).length
  const correct = practiceCorrectCount.value
  practiceSummary.value = {
    total: practiceItems.value.length,
    answered,
    correct,
    wrong: answered - correct,
    unanswered: unanswered.length,
  }
  showPracticeSummary.value = true
}

// 退出练习
const exitPractice = () => {
  practicing.value = false
  showPracticeSummary.value = false
  practiceItems.value = []
  practiceAnswers.value = {}
  practiceResults.value = {}
  practiceIndex.value = 0
}

// 再练一组：同样的选题方式重新抽题
const restartPractice = async () => {
  showPracticeSummary.value = false
  await startPractice(practiceMode.value)
}

// 去「我的错题本」
const goWrongBook = () => {
  showPracticeSummary.value = false
  router.push('/wrong-questions')
}

onMounted(() => {
  loadQuestions()
  loadAllIds()
  loadCategories()
  window.addEventListener('resize', clampCardToViewport)
})

onUnmounted(() => {
  window.removeEventListener('resize', clampCardToViewport)
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

/* 题号范围行 */
.range-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
  font-size: 14px;
  color: #606266;
}

.range-label {
  font-weight: 600;
  color: #303133;
}

.range-text {
  white-space: nowrap;
}

.range-hint {
  color: #909399;
  font-size: 13px;
}

.pager {
  margin-top: 12px;
  justify-content: flex-end;
}

.loading-tip {
  padding: 40px 0;
  text-align: center;
  color: #909399;
  font-size: 14px;
}

/* 选项样式 */
.options-area {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 20px;
}

.option-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 15px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background-color: #ffffff;
  transition: all 0.3s;
  cursor: pointer;
  user-select: none;
}

.option-item:hover {
  border-color: #409eff;
  background-color: #f0f9ff;
}

.option-item.chosen {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.option-item.correct {
  border-color: #67c23a;
  background-color: #f0f9eb;
}

.option-item.wrong {
  border-color: #f56c6c;
  background-color: #fef0f0;
}

.option-mark {
  margin-left: auto;
  color: #409eff;
  font-size: 18px;
}

.option-item.correct .option-mark {
  color: #67c23a;
}

.option-item.wrong .option-mark {
  color: #f56c6c;
}

.choice-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.choice-result {
  font-size: 14px;
  font-weight: 600;
  margin-top: 4px;
}

.choice-result.correct {
  color: #67c23a;
}

.choice-result.wrong {
  color: #f56c6c;
}

.choice-result.none {
  color: #909399;
  font-weight: 400;
}

.option-item.correct {
  border-color: #67c23a;
  background-color: #f0f9eb;
}

.option-item.wrong {
  border-color: #f56c6c;
  background-color: #fef0f0;
}

.option-key {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  line-height: 26px;
  text-align: center;
  border-radius: 50%;
  background-color: #f0f2f5;
  color: #606266;
  font-size: 13px;
  font-weight: 600;
}

.option-item.correct .option-key {
  background-color: #67c23a;
  color: #fff;
}

.option-item.wrong .option-key {
  background-color: #f56c6c;
  color: #fff;
}

.option-val {
  flex: 1;
  font-size: 15px;
  line-height: 1.6;
  color: #303133;
  word-break: break-word;
}

.option-val :deep(img) {
  max-width: 100%;
  height: auto;
}

/* 填空题作答区 */
.fill-area {
  margin-bottom: 20px;
}

.fill-label {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.fill-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}

.fill-result {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  font-size: 14px;
  font-weight: 600;
}

.fill-result.correct {
  color: #67c23a;
}

.fill-result.wrong {
  color: #f56c6c;
}

.fill-result.submitted {
  color: #909399;
}

.fill-result .el-icon {
  font-size: 18px;
}

/* 学习模式样式 */
.study-card {
  position: fixed;
  margin: 0;
  z-index: 1500;
  width: 800px;
  max-width: calc(100vw - 24px);
  display: flex;
  flex-direction: column;
  will-change: transform;
  backface-visibility: hidden;
}

.study-card :deep(.el-card__header) {
  flex-shrink: 0;
}

.study-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.study-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: move;
  user-select: none;
}

.study-card :deep(.el-card__header) {
  cursor: move;
  user-select: none;
}

.study-card.dragging {
  z-index: 1501;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.18);
  cursor: grabbing;
  user-select: none;
}

.study-card.dragging .study-header {
  cursor: grabbing;
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
  /* 图片再大也不超过这个高度，保证选项和底部按钮一屏放得下 */
  max-height: 32vh;
  height: auto;
  object-fit: contain;
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

.study-nav {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  /* 吸在窗口底部：题目再长再高，不用滚动就能点到按钮 */
  position: sticky;
  bottom: 0;
  z-index: 5;
  margin-top: 20px;
  padding: 12px 0;
  background-color: #ffffff;
  border-top: 1px solid #ebeef5;
}

.study-drag-tip {
  font-size: 12px;
  color: #909399;
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
/* ===== 自主练习（做题模式）===== */
.header-main {
  flex: 1;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
}

.practice-panel {
  background: #f7f9fc;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 14px 16px;
  margin-bottom: 8px;
}

.practice-panel-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
}

.practice-panel-title {
  font-weight: 600;
  color: #303133;
  font-size: 15px;
}

.practice-mode-group {
  margin-bottom: 12px;
}

.practice-params {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 14px;
  color: #606266;
}

.practice-card .study-header {
  display: flex;
  align-items: center;
  gap: 16px;
}

.practice-score {
  color: #606266;
  font-size: 13px;
}

.answer-correct {
  border-left: 4px solid #67c23a;
}

.answer-wrong {
  border-left: 4px solid #f56c6c;
}

.practice-summary {
  display: flex;
  justify-content: center;
  gap: 24px;
  margin: 10px 0 14px;
  font-size: 15px;
}

.summary-item.correct {
  color: #67c23a;
}

.summary-item.wrong {
  color: #f56c6c;
}

.summary-item.none {
  color: #909399;
}

.summary-tip {
  margin: 0;
  color: #909399;
  font-size: 13px;
  text-align: center;
}

/* ===== 手机端 =====
   页头并排会把说明文字挤成一条细缝，筛选行的固定宽度下拉框
   （150/200/200px）加起来超过屏宽，选项按钮组也会折行错位。
   手机上全部改成竖排 + 满宽。 */
@media (max-width: 768px) {
  .study-page { padding: 12px; }

  .page-header {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
    margin-bottom: 14px;
  }
  .page-header .el-button { width: 100%; margin-left: 0; }

  .subtitle { font-size: 13px; }

  .filter-row {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
  /* 下拉框和搜索框改成满宽：原来的固定宽度在手机上会超出卡片 */
  .filter-row .el-select,
  .filter-row .el-input { width: 100% !important; }
  .filter-row .el-button { width: 100%; margin-left: 0; }

  .practice-panel { padding: 12px; }
  .practice-panel-head {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
    margin-bottom: 10px;
  }

  /* 四个选项按钮在手机上折行时会被 el-radio-button 的边框切掉，
     改成整组换行、按钮之间留缝 */
  .practice-mode-group {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 12px;
  }
  .practice-mode-group :deep(.el-radio-button) { margin-right: 0; }
  .practice-mode-group :deep(.el-radio-button__inner) {
    border-radius: 4px;
    border-left: 1px solid var(--el-border-color);
    width: 100%;
  }

  .practice-params {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
  .practice-params .el-select,
  .practice-params .el-input { width: 100% !important; }
  .practice-params .el-button { width: 100%; margin-left: 0; }
  .practice-params .range-text,
  .practice-params .range-hint { text-align: left; }

  .range-row { flex-wrap: wrap; gap: 8px; }
  .range-row .el-input { width: 100% !important; }
  .range-row .el-button { flex: 1; margin-left: 0; }

  .stats-row { flex-wrap: wrap; gap: 8px; }

  .action-row { flex-wrap: wrap; }
  .action-row .el-button { flex: 1 1 45%; margin-left: 0; }

  .question-list { max-height: 320px; padding: 6px; }
  .question-item { padding: 8px; }
}
</style>
