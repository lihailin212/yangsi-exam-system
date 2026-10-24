<template>
  <div class="arena-host" :class="{ 'paused': isPaused }">
    <!-- 顶部信息栏 -->
    <div class="top-bar">
      <div class="arena-title">{{ arena?.title || '加载中...' }}</div>
      <div class="round-info">
        <span>第 {{ currentRound }} 轮</span>
        <el-tag :type="getTypeTag(currentQuestionType)">{{ getTypeLabel(currentQuestionType) }}</el-tag>
        <el-tag v-if="standings?.tied" type="warning">并列第一</el-tag>
      </div>
      <div class="control-buttons">
        <el-button v-if="!isPaused" type="warning" @click="pauseGame">暂停</el-button>
        <el-button v-else type="success" @click="resumeGame">继续</el-button>
        <el-button type="info" @click="refreshScores">刷新分数</el-button>
        <el-button type="primary" @click="exportResults">导出结果</el-button>
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 左侧：排行榜 -->
      <div class="sidebar-left">
        <h3>实时排行榜</h3>
        <ArenaScoreboard :teams="teams" />

        <h3 class="section-title">队伍管理</h3>
        <div class="team-manage">
          <div
            v-for="team in teams"
            :key="team.id"
            class="manage-row"
            :class="{ 'eliminated': team.status === 'eliminated' }"
          >
            <span class="dot" :style="{ background: team.color }"></span>
            <span class="name">{{ team.name }}</span>
            <span class="score">{{ team.score }}</span>
            <el-button
              v-if="team.status !== 'eliminated'"
              size="small"
              type="danger"
              link
              @click="eliminateTeam(team)"
            >淘汰</el-button>
            <el-button
              v-else
              size="small"
              type="success"
              link
              @click="resurrect(team)"
            >复活</el-button>
          </div>
        </div>
        <div class="manage-actions">
          <el-button size="small" @click="eliminateBottom" :disabled="teams.length < 2">
            淘汰末位
          </el-button>
          <el-button size="small" @click="startOvertime" :disabled="!standings?.tied">
            进入加赛
          </el-button>
          <el-button size="small" @click="nextRound">下一轮</el-button>
          <el-button size="small" @click="resetHelp">重置求助</el-button>
        </div>
      </div>

      <!-- 中间：题目区 -->
      <div class="center-content">
        <div class="question-display" v-if="currentQuestion">
          <div class="question-type-bar" :style="{ background: getTypeColor(currentQuestionType) }">
            {{ getTypeLabel(currentQuestionType) }}
          </div>
          <div class="question-content" v-html="currentQuestion.content"></div>
          <div class="question-options" v-if="showOptions">
            <div
              v-for="(opt, key) in parsedOptions"
              :key="key"
              class="option-item"
              :class="{ 'correct': isCorrectOption(key), 'eliminated': eliminatedOptions.includes(key) }"
            >
              <span class="option-key">{{ key }}</span>
              <span class="option-text" v-html="opt"></span>
            </div>
          </div>
          <div class="answer-result" v-if="lastAnswer">
            <div class="result-team" :style="{ color: lastAnswer.teamColor }">{{ lastAnswer.teamName }}</div>
            <div class="result-answer">{{ lastAnswer.answer || '（未作答）' }}</div>
            <div class="result-score" :class="{ 'correct': lastAnswer.isCorrect === true, 'wrong': lastAnswer.isCorrect === false }">
              {{ lastAnswer.isCorrect === null ? '待判定' : (lastAnswer.score > 0 ? '+' : '') + lastAnswer.score + '分' }}
            </div>
          </div>
        </div>
        <div class="no-question" v-else>
          <p>请选择题目开始比赛</p>
        </div>
      </div>

      <!-- 右侧：控制面板 -->
      <div class="sidebar-right">
        <h3>题目列表</h3>
        <div class="question-list">
          <div
            v-for="(q, idx) in questions"
            :key="q.id"
            class="question-item"
            :class="{ 'active': currentQuestionIndex === idx, 'type-required': q.q_type === 'required', 'type-rush': q.q_type === 'rush', 'type-analysis': q.q_type === 'analysis', 'type-overtime': q.q_type === 'overtime' }"
            @click="selectQuestion(idx)"
          >
            <span class="q-num">{{ idx + 1 }}</span>
            <span class="q-type">{{ getTypeLabel(q.q_type) }}</span>
            <span class="q-score">{{ q.score }}分</span>
          </div>
        </div>

        <h3>操作控制</h3>
        <div class="progress-section">
          <div class="progress-label">
            <span>本题作答进度</span>
            <span>{{ answeredCount }} / {{ activeTeamCount }}</span>
          </div>
          <el-progress
            :percentage="answerProgress"
            :stroke-width="8"
            :color="answerProgressColor"
            text-inside
          />
        </div>
        <div class="control-panel">
          <el-button type="primary" size="large" @click="showQuestion" :disabled="currentQuestionIndex < 0">
            显示题目
          </el-button>
          <el-button type="danger" size="large" @click="startRush" v-if="isRushType" :disabled="rushStarted">
            开始抢答
          </el-button>
          <div class="timer-section" v-if="showTimer">
            <ArenaTimer ref="timerRef" :duration="answerTime" @finish="onTimerFinish" @tick="onTimerTick" />
            <el-button type="warning" @click="startTimer">开始计时</el-button>
          </div>
          <template v-if="pendingAnswers.length">
            <div class="pending-title">
              <span>待判定（{{ pendingAnswers.length }}）</span>
              <el-button size="small" type="primary" plain @click="autoJudgeAll">
                <el-icon><MagicStick /></el-icon> 全部自动判定
              </el-button>
            </div>
            <div class="analysis-score" v-if="currentQuestionType === 'analysis'">
              <span class="score-label">分析题给分</span>
              <el-input-number
                v-model="analysisScore"
                :min="0"
                :max="currentQuestion?.score || 100"
                size="small"
                controls-position="right"
              />
            </div>
            <div class="pending-list">
              <div
                v-for="item in pendingAnswers"
                :key="item.answer_id"
                class="pending-item"
                :style="{ '--team-color': item.team_color }"
              >
                <span class="p-name">{{ item.team_name }}</span>
                <span class="p-answer">{{ item.answer }}</span>
                <el-button size="small" @click="autoJudgeOne(item)">自动</el-button>
                <el-button size="small" type="success" @click="judge(item, true)">对</el-button>
                <el-button size="small" type="danger" @click="judge(item, false)">错</el-button>
              </div>
            </div>
          </template>
          <el-button type="success" size="large" @click="judge(lastAnswer, true)" v-if="showConfirmButtons">
            答对
          </el-button>
          <el-button type="danger" size="large" @click="judge(lastAnswer, false)" v-if="showConfirmButtons">
            答错
          </el-button>
        </div>
      </div>
    </div>

    <!-- 底部：日志 -->
    <div class="bottom-bar">
      <div class="logs-title">操作日志</div>
      <div class="logs-container">
        <div v-for="(log, idx) in recentLogs" :key="idx" class="log-item">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-action">{{ log.action }}</span>
          <span class="log-detail">{{ log.detail }}</span>
        </div>
      </div>
    </div>

    <ArenaConfetti ref="confettiRef" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getArena, getArenaTeams, getArenaQuestions, getArenaStandings,
  exportArenaExcel, getArenaLogs,
} from '@/api/arena'
import arenaWS from '@/api/arena_ws'
import ArenaScoreboard from '@/components/ArenaScoreboard.vue'
import ArenaTimer from '@/components/ArenaTimer.vue'
import ArenaConfetti from '@/components/ArenaConfetti.vue'
import { playSound } from '@/utils/arenaSounds'

const route = useRoute()
const arenaId = parseInt(route.params.arenaId)

const arena = ref(null)
const teams = ref([])
const questions = ref([])
const standings = ref(null)
const currentQuestionIndex = ref(-1)
const currentQuestion = computed(() => questions.value[currentQuestionIndex.value]?.question || null)
const currentQuestionType = ref('')
const currentRound = ref(1)
const showOptions = ref(false)
const eliminatedOptions = ref([])
const rushStarted = ref(false)
const lastAnswer = ref(null)
const showTimer = ref(false)
const answerTime = ref(15)
const showConfirmButtons = ref(false)
const isPaused = ref(false)
const recentLogs = ref([])
const timerRef = ref(null)
const confettiRef = ref(null)
const pendingAnswers = ref([])
const analysisScore = ref(0)

const isRushType = computed(() => currentQuestionType.value === 'rush' || currentQuestionType.value === 'overtime')

const activeTeamCount = computed(() => teams.value.filter(t => t.status !== 'eliminated').length)
const answeredTeamIds = ref(new Set())
const answeredCount = computed(() => answeredTeamIds.value.size)
const answerProgress = computed(() => {
  if (!activeTeamCount.value) return 0
  return Math.min(100, Math.round((answeredCount.value / activeTeamCount.value) * 100))
})
const answerProgressColor = computed(() => {
  if (answerProgress.value >= 100) return '#67C23A'
  if (answerProgress.value >= 50) return '#E6A23C'
  return '#409EFF'
})

const parsedOptions = computed(() => {
  if (!currentQuestion.value?.options) return {}
  try {
    return JSON.parse(currentQuestion.value.options)
  } catch {
    return {}
  }
})

const isCorrectOption = (key) => {
  if (!currentQuestion.value?.answer) return false
  const answers = String(currentQuestion.value.answer)
    .split(/[,，\s]+/)
    .map(a => a.trim().toUpperCase())
    .filter(Boolean)
  return answers.includes(String(key).trim().toUpperCase())
}

const getTypeLabel = (type) => {
  const map = { required: '必答题', rush: '抢答题', analysis: '综合分析题', overtime: '加赛题' }
  return map[type] || type
}

const getTypeTag = (type) => {
  const map = { required: '', rush: 'danger', analysis: 'warning', overtime: 'success' }
  return map[type] || 'info'
}

const getTypeColor = (type) => {
  const map = { required: '#409EFF', rush: '#F56C6C', analysis: '#E6A23C', overtime: '#67C23A' }
  return map[type] || '#909399'
}

const loadData = async () => {
  try {
    const [arenaRes, teamsRes, questionsRes] = await Promise.all([
      getArena(arenaId),
      getArenaTeams(arenaId),
      getArenaQuestions(arenaId),
    ])
    arena.value = arenaRes
    teams.value = teamsRes || []
    questions.value = questionsRes || []
    currentRound.value = arenaRes?.current_round || 1
    answerTime.value = arenaRes?.settings?.rush_answer_time || 15
    // 题目加载完成后，把 state_sync 早到时记下的当前题补上
    if (pendingCurrentQuestionId.value != null) {
      applyCurrentQuestion(pendingCurrentQuestionId.value)
    }
    loadStandings()
  } catch (e) {
    console.error('加载失败:', e)
    ElMessage.error('加载失败')
  }
}

const loadStandings = async () => {
  try {
    standings.value = await getArenaStandings(arenaId)
  } catch (e) {
    console.error('加载排名失败:', e)
  }
}

const selectQuestion = (idx) => {
  currentQuestionIndex.value = idx
  const q = questions.value[idx]
  currentQuestionType.value = q.q_type
  analysisScore.value = q.score || 0
  showOptions.value = false
  eliminatedOptions.value = []
  rushStarted.value = false
  showConfirmButtons.value = false
  showTimer.value = false
  lastAnswer.value = null
  pendingAnswers.value = []
  answeredTeamIds.value = new Set()
}

// 按 arena_questions.id 定位当前题；题目尚未加载完成时先记住 id
const pendingCurrentQuestionId = ref(null)
const applyCurrentQuestion = (id) => {
  const idx = questions.value.findIndex(q => q.id === id)
  if (idx < 0) {
    pendingCurrentQuestionId.value = id
    return false
  }
  pendingCurrentQuestionId.value = null
  if (idx !== currentQuestionIndex.value) {
    currentQuestionIndex.value = idx
    currentQuestionType.value = questions.value[idx].q_type
    analysisScore.value = questions.value[idx].score || 0
    showOptions.value = true
    showConfirmButtons.value = false
    lastAnswer.value = null
    answeredTeamIds.value = new Set()
  }
  return true
}

const showQuestion = () => {
  if (currentQuestionIndex.value < 0) return
  const q = questions.value[currentQuestionIndex.value]
  showOptions.value = true
  arenaWS.showQuestion(q.id)
}

const startRush = () => {
  if (currentQuestionIndex.value < 0) return
  const q = questions.value[currentQuestionIndex.value]
  rushStarted.value = true
  showTimer.value = true
  playSound('rushStart')
  arenaWS.startRushQuestion(q.id)
}

const startTimer = () => {
  playSound('timerStart')
  arenaWS.startTimer(answerTime.value)
  timerRef.value?.start()
}

const onTimerTick = (remaining) => {
  const sec = Math.ceil(remaining)
  if (sec <= 3 && sec > 0) playSound('countdownWarning')
}

const onTimerFinish = () => {
  ElMessage.warning('时间到！')
  arenaWS.stopTimer()
}

const judge = (item, isCorrect) => {
  if (!item) return
  // 待判定列表用 answer_id（下划线），最近作答用 answerId（驼峰），此处统一兼容
  const answerId = item.answer_id ?? item.answerId
  if (!answerId) return
  // 综合分析题由主持人给分；客观题由服务端按题型规则结算
  const score = currentQuestionType.value === 'analysis' && isCorrect
    ? analysisScore.value
    : null
  arenaWS.judgeAnswer(answerId, isCorrect, score)
  if (isCorrect) {
    playSound('correct')
    confettiRef.value?.start()
  } else {
    playSound('wrong')
  }
  showConfirmButtons.value = false
  pendingAnswers.value = pendingAnswers.value.filter(a => (a.answer_id ?? a.answerId) !== answerId)
  loadStandings()
}

// 自动判定：客观题按标准答案比对，主观题/无标准答案会提示需人工评分
const currentArenaQuestionId = computed(() => questions.value[currentQuestionIndex.value]?.id ?? null)

const autoJudgeOne = (item) => {
  const answerId = item?.answer_id ?? item?.answerId
  if (!answerId) return
  arenaWS.autoJudgeAnswer(answerId)
}

const autoJudgeAll = () => {
  const questionId = currentArenaQuestionId.value
  if (!questionId) {
    ElMessage.warning('请先选择题目')
    return
  }
  arenaWS.autoJudgeAll(questionId)
}

const pauseGame = () => {
  isPaused.value = true
  arenaWS.pauseGame()
}

const resumeGame = () => {
  isPaused.value = false
  arenaWS.resumeGame()
}

const refreshScores = async () => {
  try {
    teams.value = (await getArenaTeams(arenaId)) || []
    arenaWS.refreshScores()
    loadStandings()
  } catch (e) {
    console.error('刷新失败', e)
  }
}

const exportResults = async () => {
  try {
    const filename = await exportArenaExcel(arenaId)
    ElMessage.success(`已导出 ${filename}`)
  } catch (e) {
    console.error('导出失败:', e)
    ElMessage.error('导出失败')
  }
}

const eliminateTeam = (team) => {
  arenaWS.eliminateTeams([team.id])
  ElMessage.info(`已淘汰 ${team.name}`)
  loadStandings()
}

const eliminateBottom = () => {
  arenaWS.eliminateTeams([...teams.value]
    .filter(t => t.status !== 'eliminated')
    .sort((a, b) => b.score - a.score)
    .slice(-1)
    .map(t => t.id))
  loadStandings()
}

const resurrect = (team) => {
  arenaWS.resurrectTeam(team.id)
  ElMessage.success(`${team.name} 已复活`)
  loadStandings()
}

const startOvertime = () => {
  arenaWS.startOvertime()
  currentQuestionType.value = 'overtime'
  ElMessage.info('已进入加赛环节')
}

const nextRound = () => {
  arenaWS.nextRound()
  currentRound.value += 1
  pendingAnswers.value = []
}

const resetHelp = () => {
  arenaWS.resetHelp()
  ElMessage.info('求助次数已重置')
}

const loadLogs = async () => {
  try {
    const res = await getArenaLogs(arenaId, 20)
    recentLogs.value = (res || []).slice(0, 10).map(log => ({
      time: new Date(log.timestamp).toLocaleTimeString('zh-CN'),
      action: log.action,
      detail: log.detail || '',
    }))
  } catch (e) {
    console.error('加载日志失败:', e)
  }
}

// WebSocket 事件处理
const setupWSListeners = () => {
  arenaWS.on('state_sync', (data) => {
    // 主持人断线重连：恢复到断线前的现场
    if (data?.teams) teams.value = data.teams
    if (data?.current_round) currentRound.value = data.current_round
    if (data?.arena_status === 'paused') isPaused.value = true
    if (data?.arena_status === 'active') isPaused.value = false

    const cq = data?.current_question
    if (cq?.id) {
      applyCurrentQuestion(cq.id)
    }

    // 恢复待判定列表
    if (Array.isArray(data?.pending_answers)) {
      pendingAnswers.value = data.pending_answers
      answeredTeamIds.value = new Set(data.pending_answers.map(a => a.team_id))
      if (data.pending_answers.length > 0) {
        showConfirmButtons.value = true
        const last = data.pending_answers[data.pending_answers.length - 1]
        lastAnswer.value = {
          answerId: last.answer_id,
          teamId: last.team_id,
          teamName: last.team_name,
          teamColor: last.team_color,
          answer: last.answer,
          isCorrect: null,
          score: 0,
        }
      }
    }
  })

  arenaWS.on('rush_success', (data) => {
    const team = teams.value.find(t => t.id === data.team_id)
    playSound('rushSuccess')
    ElMessage.success(`队伍 ${data.team_name || team?.name || ''} 抢答成功！`)
    showTimer.value = true
    showConfirmButtons.value = true
  })

  arenaWS.on('answer_submitted', (data) => {
    answeredTeamIds.value = new Set([...answeredTeamIds.value, data.team_id])
    pendingAnswers.value = [...pendingAnswers.value, data]
    lastAnswer.value = {
      answerId: data.answer_id,
      teamId: data.team_id,
      teamName: data.team_name,
      teamColor: data.team_color,
      answer: data.answer,
      isCorrect: null,
      score: 0,
    }
    showConfirmButtons.value = true
  })

  arenaWS.on('answer_judged', (data) => {
    const idx = pendingAnswers.value.findIndex(a => a.answer_id === data.answer_id)
    if (idx >= 0) {
      pendingAnswers.value.splice(idx, 1)
    }
    if (lastAnswer.value?.answerId === data.answer_id) {
      lastAnswer.value = { ...lastAnswer.value, isCorrect: data.is_correct, score: data.score }
    }
    loadStandings()
  })

  arenaWS.on('auto_judge_skipped', (data) => {
    ElMessage.warning(data?.message || '该题无法自动判定，请人工评分')
  })

  arenaWS.on('auto_judge_done', (data) => {
    const judged = data?.judged_count ?? 0
    const skipped = data?.skipped || []
    if (judged > 0) {
      playSound('correct')
    }
    if (skipped.length > 0) {
      const names = skipped.map(s => s.team_name).filter(Boolean).join('、')
      ElMessage.warning(`已自动判定 ${judged} 条；${skipped.length} 条需人工评分${names ? `（${names}）` : ''}`)
    } else {
      ElMessage.success(`已自动判定 ${judged} 条`)
    }
    loadStandings()
  })

  arenaWS.on('scores_updated', (data) => {
    teams.value = data.teams
  })

  arenaWS.on('teams_updated', (data) => {
    teams.value = data.teams
    loadStandings()
  })

  arenaWS.on('game_paused', () => {
    isPaused.value = true
  })

  arenaWS.on('game_resumed', () => {
    isPaused.value = false
  })

  arenaWS.on('game_started', () => {
    playSound('gameStart')
    ElMessage.success('比赛开始')
  })

  arenaWS.on('game_finished', () => {
    playSound('award')
    confettiRef.value?.start()
    ElMessage.success('比赛结束，排名已公布')
  })

  arenaWS.on('round_changed', (data) => {
    currentRound.value = data.current_round
  })

  arenaWS.on('help_used', (data) => {
    ElMessage.info(`${data.team_name} 使用了求助`)
  })

  arenaWS.on('disconnected', () => {
    ElMessage.warning('连接断开，正在重连...')
  })
}

let logInterval = null

onMounted(() => {
  loadData()
  loadLogs()
  const token = localStorage.getItem('token')
  arenaWS.connect(arenaId, { role: 'host', token })
  setupWSListeners()
  logInterval = setInterval(loadLogs, 5000)
})

onUnmounted(() => {
  if (logInterval) clearInterval(logInterval)
  arenaWS.disconnect()
})
</script>

<style scoped>
.arena-host {
  min-height: 100vh;
  background: linear-gradient(135deg, #141B22 0%, #0A0F14 100%);
  color: #fff;
  display: flex;
  flex-direction: column;
}

.arena-host.paused {
  border: 4px solid #E6A23C;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.arena-title {
  font-size: 24px;
  font-weight: 600;
}

.round-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.control-buttons {
  display: flex;
  gap: 12px;
}

.main-content {
  flex: 1;
  display: flex;
  gap: 20px;
  padding: 20px;
}

.sidebar-left {
  width: 300px;
  flex-shrink: 0;
}

.sidebar-left h3, .sidebar-right h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  color: rgba(255, 255, 255, 0.7);
}

.section-title {
  margin-top: 24px !important;
}

.team-manage {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.manage-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 6px;
  font-size: 14px;
}

.manage-row.eliminated {
  opacity: 0.45;
  text-decoration: line-through;
}

.manage-row .dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.manage-row .name {
  flex: 1;
}

.manage-row .score {
  font-family: var(--font-number, monospace);
  color: rgba(255, 255, 255, 0.7);
}

.manage-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.center-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.question-display {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 16px;
  padding: 24px;
  flex: 1;
}

.question-type-bar {
  display: inline-block;
  padding: 8px 24px;
  border-radius: 20px;
  font-weight: 600;
  margin-bottom: 24px;
}

.question-content {
  font-size: 24px;
  line-height: 1.6;
  margin-bottom: 24px;
}

.question-options {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.option-item {
  background: rgba(255, 255, 255, 0.05);
  padding: 16px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  transition: all 0.3s ease;
}

.option-item.correct {
  background: rgba(103, 194, 58, 0.2);
  border: 2px solid #67C23A;
}

.option-item.eliminated {
  opacity: 0.3;
  text-decoration: line-through;
}

.option-key {
  width: 36px;
  height: 36px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  flex-shrink: 0;
}

.option-text {
  flex: 1;
}

.no-question {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.5);
}

.answer-result {
  margin-top: 24px;
  padding: 20px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 20px;
}

.result-team {
  font-size: 20px;
  font-weight: 600;
}

.result-answer {
  flex: 1;
}

.result-score {
  font-size: 28px;
  font-weight: bold;
}

.result-score.correct { color: #67C23A; }
.result-score.wrong { color: #F56C6C; }

.sidebar-right {
  width: 320px;
  flex-shrink: 0;
}

.question-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 24px;
  max-height: 260px;
  overflow-y: auto;
}

.question-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.question-item:hover {
  background: rgba(255, 255, 255, 0.1);
}

.question-item.active {
  background: rgba(20, 255, 236, 0.2);
  border: 1px solid var(--accent-500);
}

.question-item.type-required { border-left: 3px solid #409EFF; }
.question-item.type-rush { border-left: 3px solid #F56C6C; }
.question-item.type-analysis { border-left: 3px solid #E6A23C; }
.question-item.type-overtime { border-left: 3px solid #67C23A; }

.q-num {
  font-weight: bold;
}

.q-type {
  flex: 1;
  font-size: 12px;
}

.q-score {
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
}

.control-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.timer-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 20px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
}

.pending-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
}

.analysis-score {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.analysis-score .score-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

.progress-section {
  margin-bottom: 12px;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 6px;
}

.pending-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}

.pending-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.05);
  border-left: 3px solid var(--team-color, #409EFF);
  border-radius: 6px;
  font-size: 13px;
}

.pending-item .p-name {
  font-weight: 600;
  white-space: nowrap;
}

.pending-item .p-answer {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: rgba(255, 255, 255, 0.75);
}

.bottom-bar {
  background: rgba(0, 0, 0, 0.3);
  padding: 12px 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.logs-title {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 8px;
}

.logs-container {
  display: flex;
  gap: 20px;
  overflow-x: auto;
}

.log-item {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.log-time {
  color: rgba(255, 255, 255, 0.4);
  font-size: 12px;
}

.log-action {
  color: var(--accent-500);
  font-size: 12px;
}

.log-detail {
  color: rgba(255, 255, 255, 0.6);
  font-size: 12px;
}
</style>
