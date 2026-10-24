<template>
  <canvas ref="canvasRef" class="confetti-canvas"></canvas>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  active: {
    type: Boolean,
    default: false,
  },
  duration: {
    type: Number,
    default: 2200,
  },
  count: {
    type: Number,
    default: 120,
  },
})

const emit = defineEmits(['done'])

const canvasRef = ref(null)
let particles = []
let rafId = null
let stopTimer = null

const COLORS = ['#14FFEC', '#FFD700', '#FF6B6B', '#67C23A', '#409EFF', '#E6A23C', '#FF9FF3']

const resize = () => {
  const canvas = canvasRef.value
  if (!canvas) return
  canvas.width = window.innerWidth
  canvas.height = window.innerHeight
}

const spawn = () => {
  const canvas = canvasRef.value
  if (!canvas) return
  particles = []
  for (let i = 0; i < props.count; i++) {
    particles.push({
      x: Math.random() * canvas.width,
      y: -20 - Math.random() * canvas.height * 0.4,
      w: 6 + Math.random() * 8,
      h: 8 + Math.random() * 10,
      color: COLORS[Math.floor(Math.random() * COLORS.length)],
      vx: (Math.random() - 0.5) * 2.4,
      vy: 2 + Math.random() * 3.4,
      rotation: Math.random() * Math.PI * 2,
      vr: (Math.random() - 0.5) * 0.22,
    })
  }
}

const draw = () => {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  for (const p of particles) {
    p.x += p.vx
    p.y += p.vy
    p.vy += 0.045
    p.rotation += p.vr
    ctx.save()
    ctx.translate(p.x, p.y)
    ctx.rotate(p.rotation)
    ctx.fillStyle = p.color
    ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h)
    ctx.restore()
  }
  // 移除落出屏幕的粒子
  particles = particles.filter(p => p.y < canvas.height + 40)
  if (particles.length > 0) {
    rafId = requestAnimationFrame(draw)
  } else {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    rafId = null
  }
}

const start = () => {
  resize()
  spawn()
  if (rafId) cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(draw)
  if (stopTimer) clearTimeout(stopTimer)
  stopTimer = setTimeout(() => {
    particles = []
    if (rafId) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    const canvas = canvasRef.value
    if (canvas) {
      const ctx = canvas.getContext('2d')
      ctx.clearRect(0, 0, canvas.width, canvas.height)
    }
    emit('done')
  }, props.duration)
}

const stop = () => {
  particles = []
  if (rafId) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
  if (stopTimer) {
    clearTimeout(stopTimer)
    stopTimer = null
  }
}

defineExpose({ start, stop })

onMounted(() => {
  resize()
  window.addEventListener('resize', resize)
  if (props.active) start()
})

onUnmounted(() => {
  window.removeEventListener('resize', resize)
  stop()
})
</script>

<style scoped>
.confetti-canvas {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 999;
}
</style>
