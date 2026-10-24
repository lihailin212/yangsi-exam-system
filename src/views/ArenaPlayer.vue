<template>
  <div class="arena-player" :style="{ '--team-color': teamColor }" :class="{ 'is-shaking': shaking }">
    <!-- 顶部状态栏 -->
    <div class="status-bar">
      <div class="team-info">
        <div class="team-name">{{ teamName || '选手' }}</div>
        <div class="team-score">分数: {{ score }}</div>
      </div>
      <div class="question-status">
        <span class="round-badge">第 {{ currentRound }} 轮</span>
        <span class="type-badge" :style="{ background: questionTypeColor }">{{ questionTypeLabel }}</span>
        <span v-if="myStatus === 'eliminated'" class="status-badge eliminated">已淘汰</span>
      </div>
    </div>

    <!-- 暂停遮罩 -->
    <div class="paused-overlay" v-if="isPaused">
      <div class="paused-content">
        <h2>比赛暂停中</h2>
        <p>请等待主持人继续...</p>
      </div>
    </div>

    <!-- 淘汰遮罩 -->
    <div class="paused-overlay" v-if="myStatus === 'eliminated' && !isPaused">
      <div class="paused-content">
        <h2>队伍已淘汰</h2>
        <p>可关注复活赛安排</p>
      </div>
    </div>

    <!-- 题目区域 -->
    <div class="question-area" v-if="currentQuestion">
      <div class="question-content" v-html="currentQuestion.content"></div>

      <!-- 选项区域 -->
      <div class="options-area" v-if="showOptions && parsedOptions && Object.keys(parsedOptions).length > 0">
        <div
          v-for="(opt, key) in parsedOptions"
          :key="key"
          class="option-btn"
          :class="{
            'selected': selectedAnswers.includes(key),
            'disabled': !canInteract,
            'eliminated': eliminatedOptions.includes(key)
          }"
          @click="selectAnswer(key)"
        >
          <span class="option-key">{{ key }}</span>
          <span class="option-text" v-html="opt"></span>
        </div>
      </div>

      <!-- 综合分析题答案输入 -->
      <div class="analysis-input" v-if="currentQuestionType === 'analysis'">
        <textarea
          v-model="analysisAnswer"
          placeholder="请输入答案..."
          :disabled="!canInteract"
          rows="6"
        ></textarea>
      </div>

      <!-- 提交按钮 -->
      <div class="submit-area" v-if="showSubmitButton">
        <el-button
          type="primary"
          size="large"
          :disabled="!canSubmit || !canInteract"
          @click="submitAnswer"
          class="submit-btn"
        >
          {{ answerSubmitted ? '已提交，等待判定' : '提交答案' }}
        </el-button>
      </div>
    </div>

    <!-- 无题目时 -->
    <div class="waiting-area" v-else>
      <div class="waiting-content">
        <div class="waiting-icon">
          <el-icon :size="64"><Clock /></el-icon>
        </div>
        <h2>等待题目</h2>
        <p>请等待主持人发布题目</p>
      </div>
    </div>

    <!-- 抢答按钮（仅抢答题阶段显示） -->
    <div class="rush-area" v-if="showRushButton">
      <button
        class="rush-btn"
        :class="{ 'active': rushWon, 'disabled': hasRushed }"
        @click="doRush"
        :disabled="hasRushed || isPaused || myStatus === 'eliminated'"
      >
        <span class="rush-icon">🔴</span>
        <span class="rush-text">{{ rushText }}</span>
      </button>
    </div>

    <!-- 倒计时 -->
    <div class="timer-area" v-if="showTimer">
      <ArenaTimer ref="timerRef" :duration="answerTime" @finish="onTimeUp" @tick="onTimerTick" />
    </div>

    <!-- 求助按钮 -->
    <div class="help-area" v-if="showHelpButton">
      <el-button @click="showHelpDialog = true" :disabled="helpUsed || !canInteract">
        <el-icon><QuestionFilled /></el-icon>
        {{ helpUsed ? '本轮求助已用' : '求助' }}
      </el-button>
    </div>

    <!-- 求助对话框 -->
    <el-dialog v-model="showHelpDialog" title="求助选项" width="400px">
      <div class="help-options">
        <div class="help-option" @click="useHelp('eliminate')">
          <div class="help-icon">❌</div>
          <div class="help-title">删除两个错误答案</div>
          <div class="help-desc">系统会帮你排除两个错误选项</div>
        </div>
        <div class="help-option" @click="useHelp('team_help')">
          <div class="help-icon">👥</div>
          <div class="help-title">队内求助</div>
          <div class="help-desc">获得额外60秒讨论时间</div>
        </div>
      </div>
    </el-dialog>

    <!-- 结果提示 -->
    <div class="result-toast" v-if="showResult" :class="{ 'correct': resultCorrect, 'wrong': !resultCorrect }">
      <div class="result-icon">{{ resultCorrect ? '✓' : '✗' }}</div>
      <div class="result-text">{{ resultText }}</div>
      <div class="result-score" v-if="resultScore !== 0">{{ resultScore > 0 ? '+' : '' }}{{ resultScore }}分</div>
    </div>

    <!-- 排行榜（侧边） -->
    <div class="scoreboard-mini">
      <ArenaScoreboard :teams="teams" />
    </div>

    <ArenaConfetti ref="confettiRef" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getArena, getArenaTeams, getArenaPublicQuestions, playerJoin } from '@/api/arena'
import arenaWS from '@/api/arena_ws'
import ArenaTimer from '@/components/ArenaTimer.vue'
import ArenaScoreboard from '@/components/ArenaScoreboard.vue'
import ArenaConfetti from '@/components/ArenaConfetti.vue'
import { playSound } from '@/utils/arenaSounds'
import { Clock, QuestionFilled } from '@element-plus/icons-vue'

const route = useRoute()
const arenaId = parseInt(route.params.arenaId)
const teamId = parseInt(route.params.teamId)

const teamName = ref('')
const teamColor = ref('#409EFF')
const score = ref(0)
const myStatus = ref('active')
const teams = ref([])
const publicQuestions = ref([])
const currentQuestion = ref(null)
const currentQuestionType = ref('')
const currentRound = ref(1)

const questionTypeLabel = computed(() => {
  const map = { required: '必答题', rush: '抢答题', analysis: '综合分析题', overtime: '加赛题' }
  return map[currentQuestionType.value] || '等待中'
})
const questionTypeColor = computed(() => {
  const map = { required: '#409EFF', rush: '#F56C6C', analysis: '#E6A23C', overtime: '#67C23A' }
  return map[currentQuestionType.value] || '#909399'
})

const selectedAnswers = ref([])
const analysisAnswer = ref('')
const answerSubmitted = ref(false)
const showTimer = ref(false)
const answerTime = ref(15)

const showRushButton = ref(false)
const rushWon = ref(false)
const hasRushed = ref(false)
const rushClosed = ref(false)
const rushText = computed(() => {
  if (rushWon.value) return '抢答成功！请作答'
  if (rushClosed.value) return '抢答已结束'
  if (hasRushed.value) return '已被抢先'
  return '点击抢答'
})

const eliminatedOptions = ref([])
const helpUsed = ref(false)
const showHelpDialog = ref(false)
const isPaused = ref(false)

const showResult = ref(false)
const resultCorrect = ref(false)
const resultText = ref('')
const resultScore = ref(0)
const shaking = ref(false)

const timerRef = ref(null)
const confettiRef = ref(null)
const startedAt = ref(0)
const lastHelpType = ref('')

// 统一题目结构（WebSocket 推送与公开题目列表字段不一致，这里归一化）
const normalizeQuestion = (q) => {
  if (!q) return null
  const inner = q.question || q
  return {
    id: q.id ?? inner.id,
    question_id: q.question_id ?? inner.question_id,
    q_type: q.q_type ?? inner.q_type ?? 'required',
    question_type: q.question_type ?? inner.type ?? '',
    content: inner.content || '',
    options: inner.options || '{}',
    score: q.score ?? inner.score ?? 0,
  }
}

const parsedOptions = computed(() => {
  if (!currentQuestion.value?.options) return {}
  try {
    return JSON.parse(currentQuestion.value.options)
  } catch {
    return {}
  }
})

const isMultiSelect = computed(() => currentQuestion.value?.question_type === 'multiple')

const canInteract = computed(() => {
  if (isPaused.value) return false
  if (myStatus.value === 'eliminated') return false
  if (answerSubmitted.value) return false
  // 抢答题只有抢到答题权的队伍可以作答
  if (['rush', 'overtime'].includes(currentQuestionType.value) && !rushWon.value) return false
  return true
})

const showOptions = computed(() => {
  if (!currentQuestion.value) return false
  if (['rush', 'overtime'].includes(currentQuestionType.value)) return rushWon.value
  return true
})

const showSubmitButton = computed(() => {
  if (!currentQuestion.value) return false
  if (['rush', 'overtime'].includes(currentQuestionType.value)) return rushWon.value
  return true
})

const canSubmit = computed(() => {
  if (currentQuestionType.value === 'analysis') {
    return analysisAnswer.value.trim().length > 0
  }
  return selectedAnswers.value.length > 0
})

const showHelpButton = computed(() => {
  if (!currentQuestion.value) return false
  if (currentQuestionType.value === 'analysis') return false
  if (helpUsed.value) return false
  if (answerSubmitted.value) return false
  return true
})

// ===== 选手令牌 =====
const playerToken = ref('')
const tokenStorageKey = `arena_player_token_${arenaId}_${teamId}`

const ensureJoined = async () => {
  // 优先使用加入时下发的选手令牌（刷新页面后可复用）
  const stored = localStorage.getItem(tokenStorageKey)
  if (stored) {
    playerToken.value = stored
    return true
  }
  const deviceId = localStorage.getItem('arena_device_id') || 'device_' + Math.random().toString(36).substr(2, 9)
  localStorage.setItem('arena_device_id', deviceId)
  const playerName = localStorage.getItem('arena_player_name') || '选手'
  const res = await playerJoin({
    team_id: teamId,
    device_id: deviceId,
    player_name: playerName,
  })
  const token = res?.token
  if (!token) {
    throw new Error('加入失败')
  }
  playerToken.value = token
  localStorage.setItem(tokenStorageKey, token)
  return true
}

const loadData = async () => {
  try {
    const [arenaRes, teamsRes, questionsRes] = await Promise.all([
      getArena(arenaId),
      getArenaTeams(arenaId),
      getArenaPublicQuestions(arenaId),
    ])
    publicQuestions.value = (questionsRes || []).map(normalizeQuestion)
    currentRound.value = arenaRes?.current_round || 1
    answerTime.value = arenaRes?.settings?.rush_answer_time || 15
    applyTeams(teamsRes || [])
  } catch (e) {
    console.error('加载失败:', e)
    ElMessage.error('加载失败')
  }
}

const applyTeams = (list) => {
  teams.value = list || []
  const me = teams.value.find(t => t.id === teamId)
  if (me) {
    teamName.value = me.name
    teamColor.value = me.color || '#409EFF'
    score.value = me.score || 0
    myStatus.value = me.status || 'active'
    helpUsed.value = !!me.help_used_this_round
  }
}

const selectAnswer = (key) => {
  if (!canInteract.value) return
  if (eliminatedOptions.value.includes(key)) return
  if (isMultiSelect.value) {
    selectedAnswers.value = selectedAnswers.value.includes(key)
      ? selectedAnswers.value.filter(k => k !== key)
      : [...selectedAnswers.value, key]
  } else {
    selectedAnswers.value = [key]
  }
  playSound('click')
}

const elapsedSeconds = () => {
  if (!startedAt.value) return 0
  return Math.max(0, Math.round((Date.now() - startedAt.value) / 1000))
}

const submitAnswer = () => {
  if (answerSubmitted.value || !currentQuestion.value) return
  const answer = currentQuestionType.value === 'analysis'
    ? analysisAnswer.value.trim()
    : (isMultiSelect.value ? selectedAnswers.value.join(',') : selectedAnswers.value[0])
  if (!answer) return

  answerSubmitted.value = true
  // 提交的是擂台赛题目ID（arena_questions.id）
  arenaWS.submitAnswer(currentQuestion.value.id, answer, elapsedSeconds(), lastHelpType.value)
}

const doRush = () => {
  if (hasRushed.value || !currentQuestion.value) return
  hasRushed.value = true
  playSound('click')
  arenaWS.rushAnswer(currentQuestion.value.id)
}

const onTimeUp = () => {
  if (answerSubmitted.value || !currentQuestion.value) return
  if (currentQuestionType.value === 'analysis') {
    // 综合分析题超时：截断已输入内容并提交
    if (analysisAnswer.value.trim()) {
      submitAnswer()
      ElMessage.warning('时间到！已提交当前作答内容')
    } else {
      answerSubmitted.value = true
      arenaWS.submitAnswer(currentQuestion.value.id, '', elapsedSeconds(), lastHelpType.value, true)
      ElMessage.warning('时间到！未作答')
    }
    return
  }
  // 必答题/抢答题超时：自动判错
  answerSubmitted.value = true
  arenaWS.submitAnswer(currentQuestion.value.id, '', elapsedSeconds(), lastHelpType.value, true)
  ElMessage.warning('时间到！')
}

const onTimerTick = (remaining) => {
  const sec = Math.ceil(remaining)
  if (sec <= 3 && sec > 0) playSound('countdownWarning')
}

const useHelp = (helpType) => {
  if (!currentQuestion.value) return
  showHelpDialog.value = false
  lastHelpType.value = helpType
  helpUsed.value = true
  arenaWS.requestHelp(helpType, currentQuestion.value.id)
}

const resetQuestionState = () => {
  selectedAnswers.value = []
  analysisAnswer.value = ''
  answerSubmitted.value = false
  eliminatedOptions.value = []
  showResult.value = false
  rushWon.value = false
  hasRushed.value = false
  rushClosed.value = false
  startedAt.value = Date.now()
}

// 断线重连后恢复到断线前的现场（题目 / 作答状态 / 计时器 / 抢答权）
const restoreFromState = (data) => {
  if (!data) return

  // 1. 恢复当前题目
  const q = data?.current_question ? normalizeQuestion(data.current_question) : null
  if (q) {
    const changed = currentQuestion.value?.id !== q.id
    currentQuestion.value = q
    currentQuestionType.value = q.q_type
    if (changed) resetQuestionState()
    showRushButton.value = ['rush', 'overtime'].includes(q.q_type)
    showTimer.value = false
  }

  // 2. 恢复本队作答状态（已提交 / 已判定）
  const st = data?.my_answer_state
  if (st && st.question_id === currentQuestion.value?.id) {
    answerSubmitted.value = true
    if (st.is_correct !== null && st.is_correct !== undefined) {
      resultCorrect.value = st.is_correct === true
      resultScore.value = st.score || 0
      resultText.value = st.is_correct ? '回答正确！' : '回答错误'
      showResult.value = true
      setTimeout(() => { showResult.value = false }, 3000)
    }
  }

  // 3. 恢复抢答权
  if (data?.rush_winner_team_id !== undefined && data?.rush_winner_team_id !== null) {
    rushWon.value = data.rush_winner_team_id === teamId
    hasRushed.value = true
    rushClosed.value = !rushWon.value
    showRushButton.value = false
  }

  // 4. 恢复计时器剩余时间
  const timer = data?.timer
  if (timer && typeof timer.remaining === 'number' && timer.remaining > 0) {
    answerTime.value = timer.duration || answerTime.value
    showTimer.value = true
    setTimeout(() => {
      timerRef.value?.reset(timer.remaining)
      timerRef.value?.start()
    }, 200)
  }
}

// ===== WebSocket 事件处理 =====
const setupWSListeners = () => {
  arenaWS.on('connected', (data) => {
    if (data?.team_id) {
      console.log('已连接，队伍ID:', data.team_id)
    }
  })

  arenaWS.on('state_sync', (data) => {
    if (data?.teams) applyTeams(data.teams)
    if (data?.current_round) currentRound.value = data.current_round
    if (data?.settings?.rush_answer_time) answerTime.value = data.settings.rush_answer_time
    if (data?.arena_status === 'paused') isPaused.value = true
    if (data?.arena_status === 'active') isPaused.value = false
    restoreFromState(data)
  })

  arenaWS.on('question_shown', (data) => {
    const q = normalizeQuestion(data?.question) || publicQuestions.value.find(x => x.id === data?.question_id)
    if (!q) return
    currentQuestion.value = q
    currentQuestionType.value = q.q_type
    resetQuestionState()
    showRushButton.value = false
    showTimer.value = false
  })

  arenaWS.on('rush_started', () => {
    showRushButton.value = true
    rushWon.value = false
    hasRushed.value = false
    rushClosed.value = false
    answerSubmitted.value = false
    selectedAnswers.value = []
    showTimer.value = false
    startedAt.value = Date.now()
  })

  arenaWS.on('rush_success', (data) => {
    if (data?.team_id === teamId) {
      rushWon.value = true
      hasRushed.value = true
      showRushButton.value = false
      playSound('rushSuccess')
      ElMessage.success('你抢到了答题权！')
    } else {
      hasRushed.value = true
      rushClosed.value = true
    }
  })

  arenaWS.on('rush_lost', () => {
    hasRushed.value = true
    rushClosed.value = true
    ElMessage.info('已被其他队伍抢先')
  })

  arenaWS.on('rush_already', () => {
    hasRushed.value = true
    ElMessage.info('本轮已抢答过')
  })

  arenaWS.on('rush_closed', () => {
    hasRushed.value = true
    rushClosed.value = true
  })

  arenaWS.on('timer_started', (data) => {
    answerTime.value = data?.duration || 15
    showTimer.value = true
    playSound('timerStart')
    setTimeout(() => {
      timerRef.value?.reset(answerTime.value)
      timerRef.value?.start()
    }, 200)
  })

  arenaWS.on('timer_stopped', () => {
    timerRef.value?.stop()
  })

  arenaWS.on('answer_received', () => {
    // 服务端已收到，最终结果由 judge_result 确认
  })

  arenaWS.on('judge_result', (data) => {
    if (data?.question_id && currentQuestion.value && data.question_id !== currentQuestion.value.id) return
    answerSubmitted.value = true
    resultCorrect.value = data?.is_correct === true
    resultScore.value = data?.score || 0
    resultText.value = data?.is_correct ? '回答正确！' : '回答错误'
    showResult.value = true
    if (typeof data?.team_score === 'number') {
      score.value = data.team_score
    }
    if (resultCorrect.value) {
      playSound('correct')
      confettiRef.value?.start()
    } else {
      playSound('wrong')
      triggerShake()
    }
    setTimeout(() => {
      showResult.value = false
    }, 3000)
  })

  arenaWS.on('help_result', (data) => {
    if (!data?.success) {
      helpUsed.value = false
      ElMessage.warning(data?.message || '求助失败')
      return
    }
    if (data.help_type === 'eliminate') {
      // 排除项由服务端计算，前端不自行推导答案
      eliminatedOptions.value = data.excluded_options || []
      ElMessage.success('系统帮你排除了两个错误答案')
    } else if (data.help_type === 'team_help') {
      const extra = data.extra_time || 60
      timerRef.value?.addTime(extra)
      answerTime.value += extra
      ElMessage.success(`队内求助成功，获得额外${extra}秒`)
    }
  })

  arenaWS.on('help_reset', () => {
    helpUsed.value = false
  })

  arenaWS.on('scores_updated', (data) => {
    applyTeams(data?.teams || [])
  })

  arenaWS.on('teams_updated', (data) => {
    applyTeams(data?.teams || [])
  })

  arenaWS.on('game_paused', () => {
    isPaused.value = true
  })

  arenaWS.on('host_disconnected', (data) => {
    isPaused.value = true
    ElMessage.warning(data?.message || '主持人已断开，比赛自动暂停')
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
    currentRound.value = data?.current_round || currentRound.value
    helpUsed.value = false
  })

  arenaWS.on('overtime_started', () => {
    ElMessage.info('进入加赛环节')
  })

  arenaWS.on('disconnected', () => {
    ElMessage.warning('连接断开，正在重连...')
  })

  arenaWS.on('error', (data) => {
    ElMessage.error(data?.message || '操作失败')
  })
}

const triggerShake = () => {
  shaking.value = true
  setTimeout(() => {
    shaking.value = false
  }, 600)
}

onMounted(async () => {
  setupWSListeners()
  try {
    await ensureJoined()
  } catch (e) {
    console.error('加入失败:', e)
    ElMessage.error('加入比赛失败，请通过邀请码重新进入')
    return
  }
  loadData()
  arenaWS.connect(arenaId, { role: 'player', token: playerToken.value, teamId })
})

onUnmounted(() => {
  arenaWS.disconnect()
})
</script>

<style scoped>
.arena-player {
  min-height: 100vh;
  background: linear-gradient(135deg, #141B22 0%, #0A0F14 100%);
  color: #fff;
  padding: 20px;
  position: relative;
}

.arena-player.is-shaking {
  animation: shakeX 0.5s ease;
}

@keyframes shakeX {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-12px); }
  40% { transform: translateX(10px); }
  60% { transform: translateX(-6px); }
  80% { transform: translateX(4px); }
}

.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  margin-bottom: 20px;
}

.team-info {
  display: flex;
  align-items: center;
  gap: 20px;
}

.team-name {
  font-size: 24px;
  font-weight: 600;
  color: var(--team-color);
}

.team-score {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.7);
}

.question-status {
  display: flex;
  align-items: center;
  gap: 12px;
}

.round-badge {
  padding: 6px 16px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.1);
  font-size: 14px;
}

.status-badge.eliminated {
  padding: 6px 16px;
  border-radius: 20px;
  background: rgba(245, 108, 108, 0.25);
  color: #F56C6C;
  font-size: 14px;
}

.type-badge {
  padding: 8px 20px;
  border-radius: 20px;
  font-weight: 600;
}

.paused-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.paused-content {
  text-align: center;
}

.paused-content h2 {
  font-size: 32px;
  margin-bottom: 12px;
}

.paused-content p {
  color: rgba(255, 255, 255, 0.6);
}

.question-area {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 16px;
}

.question-content {
  font-size: 28px;
  line-height: 1.6;
  text-align: center;
  padding: 40px 20px;
  margin-bottom: 32px;
}

.options-area {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.option-btn {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  background: rgba(255, 255, 255, 0.08);
  border: 2px solid transparent;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.option-btn:hover:not(.disabled):not(.eliminated) {
  background: rgba(255, 255, 255, 0.15);
  border-color: var(--team-color);
  transform: scale(1.02);
}

.option-btn.selected {
  background: rgba(64, 158, 255, 0.2);
  border-color: #409EFF;
}

.option-btn.disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.option-btn.eliminated {
  opacity: 0.3;
  text-decoration: line-through;
}

.option-key {
  width: 44px;
  height: 44px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 18px;
  flex-shrink: 0;
}

.option-text {
  flex: 1;
  font-size: 18px;
}

.analysis-input textarea {
  width: 100%;
  padding: 16px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  color: #fff;
  font-size: 18px;
  resize: none;
}

.analysis-input textarea:focus {
  outline: none;
  border-color: var(--team-color);
}

.submit-area {
  display: flex;
  justify-content: center;
}

.submit-btn {
  padding: 16px 80px;
  font-size: 20px;
  border-radius: 30px;
}

.waiting-area {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}

.waiting-content {
  text-align: center;
}

.waiting-icon {
  margin-bottom: 24px;
  color: rgba(255, 255, 255, 0.4);
  animation: pulse 2s ease infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.4; transform: scale(1); }
  50% { opacity: 0.8; transform: scale(1.1); }
}

.waiting-content h2 {
  font-size: 28px;
  margin-bottom: 12px;
}

.waiting-content p {
  color: rgba(255, 255, 255, 0.5);
}

.rush-area {
  position: fixed;
  bottom: 100px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 20;
}

.rush-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 80px;
  background: linear-gradient(135deg, #F56C6C, #E04040);
  border: none;
  border-radius: 50%;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 0 40px rgba(245, 108, 108, 0.4);
}

.rush-btn:hover:not(.disabled) {
  transform: scale(1.1);
  box-shadow: 0 0 60px rgba(245, 108, 108, 0.6);
}

.rush-btn.active {
  background: linear-gradient(135deg, #67C23A, #5BAF25);
  box-shadow: 0 0 60px rgba(103, 194, 58, 0.6);
}

.rush-btn.disabled {
  background: linear-gradient(135deg, #909399, #666);
  box-shadow: none;
  cursor: not-allowed;
}

.rush-icon {
  font-size: 48px;
}

.rush-text {
  font-size: 20px;
  font-weight: bold;
  color: #fff;
}

.timer-area {
  position: fixed;
  bottom: 40px;
  right: 40px;
  z-index: 20;
}

.help-area {
  position: fixed;
  bottom: 40px;
  left: 40px;
  z-index: 20;
}

.help-options {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.help-option {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.help-option:hover {
  background: rgba(255, 255, 255, 0.1);
}

.help-icon {
  font-size: 32px;
}

.help-title {
  font-size: 18px;
  font-weight: 600;
}

.help-desc {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
}

.result-toast {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  padding: 40px 60px;
  background: rgba(0, 0, 0, 0.9);
  border-radius: 20px;
  text-align: center;
  animation: toastIn 0.3s ease;
  z-index: 200;
}

.result-toast.correct {
  border: 3px solid #67C23A;
}

.result-toast.wrong {
  border: 3px solid #F56C6C;
}

@keyframes toastIn {
  from { transform: translate(-50%, -50%) scale(0.5); opacity: 0; }
  to { transform: translate(-50%, -50%) scale(1); opacity: 1; }
}

.result-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.result-text {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 8px;
}

.result-score {
  font-size: 32px;
  font-weight: bold;
}

.result-toast.correct .result-score { color: #67C23A; }
.result-toast.wrong .result-score { color: #F56C6C; }

.scoreboard-mini {
  position: fixed;
  top: 100px;
  right: 20px;
  width: 250px;
  opacity: 0.85;
}
</style>
