<template>
  <div class="scoreboard">
    <transition-group name="rank" tag="div" class="team-list">
      <div
        v-for="(team, index) in sortedTeams"
        :key="team.id"
        class="team-item"
        :class="{
          'team-first': index === 0,
          'team-eliminated': team.status === 'eliminated',
          'team-rising': isRising(team.id)
        }"
        :style="{ '--team-color': team.color }"
      >
        <div class="rank-badge" :class="getRankClass(index)">
          {{ getRankLabel(index) }}
        </div>
        <div class="team-info">
          <div class="team-name" :style="{ color: team.color }">{{ team.name }}</div>
          <div class="team-status" v-if="team.status !== 'active'">
            {{ team.status === 'eliminated' ? '已淘汰' : '复活' }}
          </div>
        </div>
        <div class="team-score" :class="{ 'score-up': isRising(team.id), 'score-down': isFalling(team.id) }">
          <span class="score-value">{{ team.score }}</span>
          <span class="score-delta" v-if="getDelta(team.id) !== 0">
            {{ getDelta(team.id) > 0 ? '+' : '' }}{{ getDelta(team.id) }}
          </span>
        </div>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  teams: {
    type: Array,
    default: () => []
  }
})

const prevScores = ref({})
const scoreChanges = ref({})

const sortedTeams = computed(() => {
  return [...props.teams].sort((a, b) => {
    if (a.status === 'eliminated' && b.status !== 'eliminated') return 1
    if (b.status === 'eliminated' && a.status !== 'eliminated') return -1
    return b.score - a.score
  })
})

watch(() => props.teams, (newTeams, oldTeams) => {
  newTeams.forEach(team => {
    const prev = prevScores.value[team.id]
    if (prev !== undefined && prev !== team.score) {
      scoreChanges.value[team.id] = team.score - prev
      setTimeout(() => {
        delete scoreChanges.value[team.id]
      }, 2000)
    }
    prevScores.value[team.id] = team.score
  })
}, { deep: true })

const getRankLabel = (index) => {
  const labels = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩']
  return labels[index] || (index + 1)
}

const getRankClass = (index) => {
  if (index === 0) return 'rank-gold'
  if (index === 1) return 'rank-silver'
  if (index === 2) return 'rank-bronze'
  return ''
}

const getDelta = (teamId) => {
  return scoreChanges.value[teamId] || 0
}

const isRising = (teamId) => {
  return getDelta(teamId) > 0
}

const isFalling = (teamId) => {
  return getDelta(teamId) < 0
}
</script>

<style scoped>
.scoreboard {
  background: linear-gradient(135deg, rgba(20, 27, 34, 0.95), rgba(10, 15, 20, 0.98));
  border-radius: 16px;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.team-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.team-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.team-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: var(--team-color);
  opacity: 0.8;
}

.team-item:hover {
  background: rgba(255, 255, 255, 0.06);
  transform: translateX(4px);
}

.team-first {
  background: linear-gradient(135deg, rgba(255, 215, 0, 0.1), rgba(255, 165, 0, 0.05));
  border: 1px solid rgba(255, 215, 0, 0.3);
}

.team-first::before {
  background: linear-gradient(180deg, #FFD700, #FFA500);
  box-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
}

.team-eliminated {
  opacity: 0.5;
  filter: grayscale(0.5);
}

.rank-badge {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: bold;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  flex-shrink: 0;
}

.rank-gold {
  background: linear-gradient(135deg, #FFD700, #FFA500);
  color: #1a1a1a;
  box-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
}

.rank-silver {
  background: linear-gradient(135deg, #C0C0C0, #A8A8A8);
  color: #1a1a1a;
}

.rank-bronze {
  background: linear-gradient(135deg, #CD7F32, #B87333);
  color: #fff;
}

.team-info {
  flex: 1;
  min-width: 0;
}

.team-name {
  font-size: 18px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.team-status {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.team-score {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  min-width: 80px;
}

.score-value {
  font-size: 28px;
  font-weight: bold;
  font-family: var(--font-number, monospace);
  color: #fff;
}

.score-delta {
  font-size: 14px;
  color: #67C23A;
  font-weight: 600;
}

.score-up .score-value {
  animation: scorePulse 0.5s ease;
  color: #67C23A;
}

.score-down .score-value {
  animation: scoreShake 0.5s ease;
  color: #F56C6C;
}

@keyframes scorePulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.2); }
}

@keyframes scoreShake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-5px); }
  75% { transform: translateX(5px); }
}

/* 排名动画 */
.rank-enter-active {
  transition: all 0.5s ease;
}

.rank-leave-active {
  transition: all 0.3s ease;
  position: absolute;
}

.rank-enter-from {
  opacity: 0;
  transform: translateX(-30px);
}

.rank-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

.rank-move {
  transition: transform 0.5s ease;
}
</style>