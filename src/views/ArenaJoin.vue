<template>
  <div class="arena-join">
    <div class="join-container">
      <!-- Logo区 -->
      <div class="logo-section">
        <div class="logo-icon">
          <svg viewBox="0 0 100 100" class="logo-svg">
            <defs>
              <linearGradient id="arenaGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#14FFEC"/>
                <stop offset="100%" style="stop-color:#0D7377"/>
              </linearGradient>
            </defs>
            <circle cx="50" cy="50" r="45" fill="url(#arenaGradient)"/>
            <path d="M50 25 L50 75 M30 50 L70 50" stroke="white" stroke-width="6" stroke-linecap="round"/>
          </svg>
        </div>
        <h1>专业擂台赛</h1>
        <p>选手入口</p>
      </div>

      <!-- 输入区 -->
      <div class="input-section">
        <el-form :model="form" class="join-form">
          <el-form-item>
            <el-input
              v-model="form.inviteCode"
              placeholder="请输入6位邀请码"
              maxlength="6"
              size="large"
              @input="form.inviteCode = form.inviteCode.replace(/\D/g, '')"
              @keyup.enter="joinArena"
            >
              <template #prefix>
                <el-icon><Key /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item>
            <el-input
              v-model="form.playerName"
              placeholder="请输入你的名字"
              size="large"
              @keyup.enter="joinArena"
            >
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>
            <el-button type="primary" size="large" class="join-btn" @click="joinArena" :loading="loading">
            加入比赛
          </el-button>
        </el-form>
      </div>

      <!-- 擂台赛信息（已找到时） -->
      <div class="arena-info-section" v-if="arena">
        <div class="arena-card">
          <h2>{{ arena.title }}</h2>
          <div class="arena-status">
            <el-tag :type="getStatusType(arena.status)">{{ getStatusLabel(arena.status) }}</el-tag>
            <span class="team-count">{{ teams.length }}支队伍</span>
            <span v-if="inviteExpireText" class="team-count">{{ inviteExpireText }}</span>
          </div>
          <div class="teams-list">
            <div
              v-for="team in teams"
              :key="team.id"
              class="team-option"
              :style="{ '--team-color': team.color }"
              :class="{ 'is-selected': selectedTeam && selectedTeam.id === team.id }"
              @click="selectTeam(team)"
            >
              <div class="team-color-bar"></div>
              <div class="team-name">{{ team.name }}</div>
              <div class="team-players">{{ team.player_count || 0 }}人</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 进入比赛（已选择队伍） -->
      <div class="confirm-section" v-if="selectedTeam">
        <div class="selected-team">
          <div class="team-badge" :style="{ background: selectedTeam.color }">
            {{ selectedTeam.name }}
          </div>
          <p>确认以「{{ form.playerName || '选手' }}」的身份加入此队伍？</p>
          <div class="confirm-buttons">
            <el-button @click="selectedTeam = null" :disabled="entering">重新选择</el-button>
            <el-button type="primary" size="large" :loading="entering" @click="enterArena">
              进入比赛
            </el-button>
          </div>
        </div>
      </div>

      <!-- 错误提示 -->
      <div class="error-tip" v-if="error">
        <el-icon><Warning /></el-icon>
        {{ error }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getArenaByInvite, getArenaTeams, playerJoin } from '@/api/arena'
import { Key, User, Warning } from '@element-plus/icons-vue'

const route = useRoute()

const form = ref({
  inviteCode: '',
  playerName: '',
})

const loading = ref(false)
const entering = ref(false)
const arena = ref(null)
const teams = ref([])
const selectedTeam = ref(null)
const error = ref('')

// 邀请码有效期提示
const inviteExpireText = computed(() => {
  const exp = arena.value?.invite_expire
  if (!exp) return ''
  // 后端返回的是 UTC 无时区时间字符串，需按 UTC 解析
  const expTime = new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(exp) ? exp : exp + 'Z').getTime()
  const minutes = Math.max(0, Math.round((expTime - Date.now()) / 60000))
  return `邀请码 ${minutes} 分钟后失效`
})

const getStatusType = (status) => {
  const map = { pending: 'info', active: 'success', paused: 'warning', finished: '' }
  return map[status] || 'info'
}

const getStatusLabel = (status) => {
  const map = { pending: '待开始', active: '进行中', paused: '已暂停', finished: '已结束' }
  return map[status] || status
}

const joinArena = async () => {
  if (!form.value.inviteCode || form.value.inviteCode.length !== 6) {
    error.value = '请输入6位邀请码'
    return
  }

  loading.value = true
  error.value = ''

  try {
    const res = await getArenaByInvite(form.value.inviteCode)
    arena.value = res

    // 获取队伍列表
    const teamsRes = await getArenaTeams(arena.value.id)
    teams.value = teamsRes || []
    selectedTeam.value = null
    if (!teams.value.length) {
      error.value = '该擂台赛尚未设置队伍'
    }
  } catch (e) {
    error.value = e?.response?.data?.detail || '邀请码无效或已过期'
    arena.value = null
  } finally {
    loading.value = false
  }
}

const selectTeam = (team) => {
  selectedTeam.value = team
}

const getDeviceId = () => {
  let deviceId = localStorage.getItem('arena_device_id')
  if (!deviceId) {
    deviceId = 'device_' + Math.random().toString(36).slice(2, 11)
    localStorage.setItem('arena_device_id', deviceId)
  }
  return deviceId
}

const enterArena = async () => {
  if (!selectedTeam.value) return

  if (!form.value.playerName.trim()) {
    error.value = '请输入你的名字'
    return
  }

  entering.value = true
  error.value = ''

  try {
    // 在邀请码有效期内完成加入，直接领取选手令牌
    const res = await playerJoin({
      team_id: selectedTeam.value.id,
      device_id: getDeviceId(),
      player_name: form.value.playerName.trim(),
    })

    if (!res?.token) {
      throw new Error('未获取到选手令牌')
    }

    // 保存队伍信息与令牌到本地
    localStorage.setItem('arena_team_id', String(selectedTeam.value.id))
    localStorage.setItem('arena_player_name', form.value.playerName.trim())
    localStorage.setItem(
      `arena_player_token_${arena.value.id}_${selectedTeam.value.id}`,
      res.token
    )

    // 跳转到选手界面
    window.location.hash = `#/arena-player/${arena.value.id}/${selectedTeam.value.id}`
  } catch (e) {
    console.error('加入失败:', e)
    error.value = e?.response?.data?.detail || '加入失败，队伍可能已满或邀请码已失效'
  } finally {
    entering.value = false
  }
}

onMounted(() => {
  // 支持扫码进入时携带邀请码：#/arena-join?code=123456
  const hash = window.location.hash || ''
  const hashMatch = hash.match(/[?&]code=([^&]+)/)
  const code = (route.query?.code || hashMatch?.[1] || '').toString().replace(/\D/g, '')
  if (code.length === 6) {
    form.value.inviteCode = code
    joinArena()
  }
})
</script>

<style scoped>
.arena-join {
  min-height: 100vh;
  background: linear-gradient(135deg, #141B22 0%, #0A0F14 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.join-container {
  width: 100%;
  max-width: 500px;
}

.logo-section {
  text-align: center;
  margin-bottom: 40px;
}

.logo-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 20px;
}

.logo-svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 0 20px rgba(20, 255, 236, 0.5));
}

.logo-section h1 {
  font-size: 32px;
  font-weight: 600;
  color: #fff;
  margin: 0 0 8px 0;
}

.logo-section p {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
}

.input-section {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 16px;
  padding: 32px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.join-form {
  width: 100%;
}

.join-btn {
  width: 100%;
  height: 48px;
  font-size: 18px;
  border-radius: 24px;
  margin-top: 16px;
}

.arena-info-section {
  margin-top: 20px;
}

.arena-card {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 16px;
  padding: 24px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.arena-card h2 {
  font-size: 20px;
  color: #fff;
  margin: 0 0 12px 0;
  text-align: center;
}

.arena-status {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-bottom: 24px;
}

.team-count {
  color: rgba(255, 255, 255, 0.6);
}

.teams-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.team-option {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  overflow: hidden;
}

.team-option:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: translateY(-2px);
}

.team-option.is-selected {
  background: rgba(255, 255, 255, 0.14);
  box-shadow: inset 0 0 0 2px var(--team-color);
}

.team-color-bar {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: var(--team-color);
}

.team-name {
  font-size: 18px;
  font-weight: 600;
  color: var(--team-color);
}

.team-players {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 4px;
}

.confirm-section {
  margin-top: 20px;
}

.selected-team {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 16px;
  padding: 32px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  text-align: center;
}

.team-badge {
  display: inline-block;
  padding: 12px 32px;
  border-radius: 24px;
  font-size: 20px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 16px;
}

.confirm-buttons {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-top: 24px;
}

.error-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 20px;
  background: rgba(245, 108, 108, 0.2);
  border-radius: 8px;
  color: #F56C6C;
  margin-top: 20px;
}
</style>
