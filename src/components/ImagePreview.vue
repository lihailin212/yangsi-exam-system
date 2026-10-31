<template>
  <teleport to="body">
    <div
      v-if="modelValue"
      class="img-preview"
      @wheel.prevent="onWheel"
      @mousedown="onMouseDown"
      @dblclick="reset"
      @contextmenu.prevent
    >
      <div class="img-preview__bar" @mousedown.stop>
        <span class="img-preview__title">{{ title || '图片预览' }}</span>
        <div class="img-preview__actions">
          <el-button-group size="small">
            <el-button @click="zoomOut" title="缩小">－</el-button>
            <el-button @click="zoomIn" title="放大">＋</el-button>
          </el-button-group>
          <el-button size="small" class="img-preview__desktop" @click="fit">适应窗口</el-button>
          <el-button size="small" class="img-preview__desktop" @click="actualSize">原始大小</el-button>
          <el-button size="small" @click="reset">还原</el-button>
          <el-button size="small" type="primary" @click="close">关闭</el-button>
        </div>
        <span class="img-preview__scale">{{ Math.round(scale * 100) }}%</span>
      </div>

      <div
        class="img-preview__stage"
        ref="stageEl"
        @touchstart="onTouchStart"
        @touchmove.prevent="onTouchMove"
        @touchend="onTouchEnd"
        @touchcancel="onTouchEnd"
      >
        <img
          v-if="src"
          ref="imgEl"
          :src="src"
          class="img-preview__img"
          :class="{ dragging }"
          :style="imgStyle"
          @load="onLoad"
          draggable="false"
        />
        <div class="img-preview__loading" v-else>没有图片</div>
      </div>

      <div class="img-preview__hint">双指/滚轮缩放 · 拖动平移 · 双击还原 · Esc 关闭</div>
    </div>
  </teleport>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  src: { type: String, default: '' },
  title: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const scale = ref(1)          // 当前缩放倍数
const offsetX = ref(0)        // 平移偏移
const offsetY = ref(0)
const natWidth = ref(0)       // 图片原始尺寸
const natHeight = ref(0)
const stageEl = ref(null)
const imgEl = ref(null)
const dragging = ref(false)

const MIN_SCALE = 0.1
const MAX_SCALE = 8

const imgStyle = computed(() => ({
  transform: `translate(${offsetX.value}px, ${offsetY.value}px) scale(${scale.value})`,
}))

function clamp(v) {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, v))
}

// 图片载入后先"适应窗口"，一眼能看全
function onLoad() {
  const img = imgEl.value
  if (!img) return
  natWidth.value = img.naturalWidth
  natHeight.value = img.naturalHeight
  fit()
}

function fit() {
  const stage = stageEl.value
  const img = imgEl.value
  if (!stage || !img || !natWidth.value) return
  const pad = 48
  const w = stage.clientWidth - pad
  const h = stage.clientHeight - pad
  const s = Math.min(w / natWidth.value, h / natHeight.value, 1)
  scale.value = clamp(s)
  offsetX.value = 0
  offsetY.value = 0
}

function actualSize() {
  scale.value = 1
  offsetX.value = 0
  offsetY.value = 0
}

function reset() {
  fit()
}

function zoomIn() {
  scale.value = clamp(scale.value * 1.25)
}

function zoomOut() {
  scale.value = clamp(scale.value / 1.25)
}

function onWheel(e) {
  const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15
  scale.value = clamp(scale.value * factor)
}

let startX = 0
let startY = 0
let startOX = 0
let startOY = 0

function onMouseDown(e) {
  if (e.target.closest('.img-preview__bar')) return
  dragging.value = true
  startX = e.clientX
  startY = e.clientY
  startOX = offsetX.value
  startOY = offsetY.value

  const onMove = (ev) => {
    offsetX.value = startOX + (ev.clientX - startX)
    offsetY.value = startOY + (ev.clientY - startY)
  }
  const onUp = () => {
    dragging.value = false
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

let touchStartDistance = 0
let touchStartScale = 1
let lastTouchX = 0
let lastTouchY = 0

function getTouchDistance(touches) {
  const dx = touches[0].clientX - touches[1].clientX
  const dy = touches[0].clientY - touches[1].clientY
  return Math.hypot(dx, dy)
}

function onTouchStart(e) {
  if (e.touches.length === 1) {
    dragging.value = true
    lastTouchX = e.touches[0].clientX
    lastTouchY = e.touches[0].clientY
  } else if (e.touches.length === 2) {
    dragging.value = false
    touchStartDistance = getTouchDistance(e.touches)
    touchStartScale = scale.value
  }
}

function onTouchMove(e) {
  if (e.touches.length === 1) {
    const touch = e.touches[0]
    offsetX.value += touch.clientX - lastTouchX
    offsetY.value += touch.clientY - lastTouchY
    lastTouchX = touch.clientX
    lastTouchY = touch.clientY
  } else if (e.touches.length === 2 && touchStartDistance > 0) {
    scale.value = clamp(touchStartScale * getTouchDistance(e.touches) / touchStartDistance)
  }
}

function onTouchEnd(e) {
  if (e.touches.length === 0) {
    dragging.value = false
    touchStartDistance = 0
  } else if (e.touches.length === 1) {
    dragging.value = true
    lastTouchX = e.touches[0].clientX
    lastTouchY = e.touches[0].clientY
    touchStartDistance = 0
  }
}

function close() {
  emit('update:modelValue', false)
}

function onKey(e) {
  if (!props.modelValue) return
  if (e.key === 'Escape') close()
  if (e.key === '+' || e.key === '=') zoomIn()
  if (e.key === '-') zoomOut()
  if (e.key === '0') fit()
}

watch(() => props.modelValue, (v) => {
  if (v) {
    scale.value = 1
    offsetX.value = 0
    offsetY.value = 0
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
  } else {
    document.removeEventListener('keydown', onKey)
    document.body.style.overflow = ''
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.img-preview {
  position: fixed;
  inset: 0;
  z-index: 3100;
  background: rgba(20, 22, 26, 0.92);
  display: flex;
  flex-direction: column;
  user-select: none;
}

.img-preview__bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: rgba(0, 0, 0, 0.35);
  color: #fff;
  flex-shrink: 0;
}

.img-preview__title {
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 240px;
}

.img-preview__actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.img-preview__scale {
  font-size: 13px;
  min-width: 48px;
  text-align: right;
  opacity: 0.85;
}

.img-preview__stage {
  flex: 1;
  overflow: hidden;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  touch-action: none;
}

.img-preview__img {
  max-width: none;
  transform-origin: center center;
  will-change: transform;
  pointer-events: none;
}

.img-preview__img.dragging {
  cursor: grabbing;
}

.img-preview__loading {
  color: #fff;
  opacity: 0.7;
  font-size: 14px;
}

.img-preview__hint {
  padding: 8px 16px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 12px;
  text-align: center;
  flex-shrink: 0;
}

@media (max-width: 640px) {
  .img-preview__bar {
    gap: 6px;
    padding: 8px 10px;
    flex-wrap: wrap;
  }

  .img-preview__title {
    max-width: 120px;
    font-size: 12px;
  }

  .img-preview__actions {
    gap: 4px;
    margin-left: auto;
  }

  .img-preview__actions :deep(.el-button) {
    padding: 7px 9px;
  }

  .img-preview__desktop,
  .img-preview__scale {
    display: none;
  }

  .img-preview__hint {
    padding: 6px 10px;
    font-size: 11px;
  }
}
</style>
