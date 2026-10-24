<template>
  <div class="timer-container" :class="{ 'timer-warning': isWarning, 'timer-danger': isDanger }">
    <svg class="timer-ring" viewBox="0 0 100 100">
      <circle
        class="timer-bg"
        cx="50"
        cy="50"
        r="45"
      />
      <circle
        class="timer-progress"
        cx="50"
        cy="50"
        r="45"
        :style="{ strokeDashoffset: progressOffset }"
      />
    </svg>
    <div class="timer-display">
      <span class="timer-value">{{ displayTime }}</span>
      <span class="timer-label" v-if="label">{{ label }}</span>
    </div>
    <div class="timer-pulse" v-if="isRunning"></div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'

const props = defineProps({
  duration: {
    type: Number,
    default: 15
  },
  autoStart: {
    type: Boolean,
    default: false
  },
  label: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['tick', 'finish', 'start', 'stop'])

const remaining = ref(props.duration)
const isRunning = ref(false)
let intervalId = null

const displayTime = computed(() => {
  return Math.ceil(remaining.value)
})

const progressOffset = computed(() => {
  const circumference = 2 * Math.PI * 45
  const progress = remaining.value / props.duration
  return circumference * (1 - progress)
})

const isWarning = computed(() => {
  return remaining.value <= 5 && remaining.value > 3
})

const isDanger = computed(() => {
  return remaining.value <= 3
})

const start = () => {
  if (isRunning.value) return
  isRunning.value = true
  emit('start')
  intervalId = setInterval(() => {
    remaining.value -= 0.1
    emit('tick', remaining.value)
    if (remaining.value <= 0) {
      stop()
      emit('finish')
    }
  }, 100)
}

const stop = () => {
  isRunning.value = false
  if (intervalId) {
    clearInterval(intervalId)
    intervalId = null
  }
  emit('stop')
}

const reset = (newDuration = null) => {
  stop()
  remaining.value = newDuration !== null ? newDuration : props.duration
}

// 追加时间（队内求助 +60秒）
const addTime = (seconds) => {
  remaining.value = Math.max(0, remaining.value + seconds)
}

watch(() => props.duration, (newVal) => {
  if (!isRunning.value) {
    remaining.value = newVal
  }
})

onUnmounted(() => {
  stop()
})

defineExpose({ start, stop, reset, addTime, remaining })
</script>

<style scoped>
.timer-container {
  position: relative;
  width: 160px;
  height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
}

.timer-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.timer-bg {
  fill: none;
  stroke: rgba(255, 255, 255, 0.1);
  stroke-width: 8;
}

.timer-progress {
  fill: none;
  stroke: var(--accent-500, #14FFEC);
  stroke-width: 8;
  stroke-linecap: round;
  stroke-dasharray: 283;
  transition: stroke-dashoffset 0.1s linear, stroke 0.3s ease;
}

.timer-warning .timer-progress {
  stroke: #E6A23C;
}

.timer-danger .timer-progress {
  stroke: #F56C6C;
  animation: dangerPulse 0.5s ease infinite;
}

.timer-display {
  display: flex;
  flex-direction: column;
  align-items: center;
  z-index: 1;
}

.timer-value {
  font-size: 48px;
  font-weight: bold;
  font-family: var(--font-number, monospace);
  color: #fff;
  text-shadow: 0 0 20px rgba(20, 255, 236, 0.5);
}

.timer-warning .timer-value {
  color: #E6A23C;
  text-shadow: 0 0 20px rgba(230, 162, 60, 0.5);
}

.timer-danger .timer-value {
  color: #F56C6C;
  text-shadow: 0 0 20px rgba(245, 108, 108, 0.5);
  animation: dangerFlash 0.5s ease infinite;
}

.timer-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 4px;
}

.timer-pulse {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 2px solid var(--accent-500, #14FFEC);
  animation: timerPulse 1.5s ease-out infinite;
  pointer-events: none;
}

.timer-warning .timer-pulse {
  border-color: #E6A23C;
}

.timer-danger .timer-pulse {
  border-color: #F56C6C;
}

@keyframes dangerPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

@keyframes dangerFlash {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.8; transform: scale(1.05); }
}

@keyframes timerPulse {
  0% {
    transform: scale(1);
    opacity: 0.8;
  }
  100% {
    transform: scale(1.3);
    opacity: 0;
  }
}
</style>
