// 擂台赛音效（Web Audio API 合成，无需任何外部音频素材，完全免费）

let ctx = null

function getContext() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext
    if (!AC) return null
    ctx = new AC()
  }
  // 浏览器策略：首次交互后 resume
  if (ctx.state === 'suspended') {
    ctx.resume().catch(() => {})
  }
  return ctx
}

// 播放单个音符
function tone({ freq = 440, start = 0, duration = 0.2, type = 'sine', volume = 0.3, glideTo = null }) {
  const audio = getContext()
  if (!audio) return
  const t0 = audio.currentTime + start
  const osc = audio.createOscillator()
  const gain = audio.createGain()
  osc.type = type
  osc.frequency.setValueAtTime(freq, t0)
  if (glideTo) {
    osc.frequency.exponentialRampToValueAtTime(glideTo, t0 + duration)
  }
  gain.gain.setValueAtTime(0.0001, t0)
  gain.gain.exponentialRampToValueAtTime(volume, t0 + 0.02)
  gain.gain.exponentialRampToValueAtTime(0.0001, t0 + duration)
  osc.connect(gain).connect(audio.destination)
  osc.start(t0)
  osc.stop(t0 + duration + 0.05)
}

// 噪声（用于错误音的"砰"感）
function noise({ start = 0, duration = 0.25, volume = 0.25 }) {
  const audio = getContext()
  if (!audio) return
  const t0 = audio.currentTime + start
  const frames = Math.floor(audio.sampleRate * duration)
  const buffer = audio.createBuffer(1, frames, audio.sampleRate)
  const data = buffer.getChannelData(0)
  for (let i = 0; i < frames; i++) {
    data[i] = (Math.random() * 2 - 1) * (1 - i / frames)
  }
  const src = audio.createBufferSource()
  src.buffer = buffer
  const filter = audio.createBiquadFilter()
  filter.type = 'lowpass'
  filter.frequency.value = 900
  const gain = audio.createGain()
  gain.gain.setValueAtTime(volume, t0)
  gain.gain.exponentialRampToValueAtTime(0.0001, t0 + duration)
  src.connect(filter).connect(gain).connect(audio.destination)
  src.start(t0)
}

const sounds = {
  // 点击"开始抢答" —— 提示音（双短音）
  rushStart() {
    tone({ freq: 660, duration: 0.12, type: 'square', volume: 0.18 })
    tone({ freq: 880, start: 0.15, duration: 0.14, type: 'square', volume: 0.18 })
  },

  // 抢到答题权 —— 抢答成功音（上行三音）
  rushSuccess() {
    tone({ freq: 523, duration: 0.12, type: 'triangle', volume: 0.28 })
    tone({ freq: 659, start: 0.11, duration: 0.12, type: 'triangle', volume: 0.28 })
    tone({ freq: 784, start: 0.22, duration: 0.24, type: 'triangle', volume: 0.32 })
  },

  // 点击"开始计时" —— 计时开始音
  timerStart() {
    tone({ freq: 440, duration: 0.14, type: 'sine', volume: 0.24 })
    tone({ freq: 587, start: 0.13, duration: 0.2, type: 'sine', volume: 0.24 })
  },

  // 倒计时最后3秒 —— 警告音（每次调用一声）
  countdownWarning() {
    tone({ freq: 1000, duration: 0.08, type: 'square', volume: 0.2 })
  },

  // 答对 —— 正确音（明亮大三和弦）
  correct() {
    tone({ freq: 523, duration: 0.16, type: 'sine', volume: 0.28 })
    tone({ freq: 659, start: 0.08, duration: 0.16, type: 'sine', volume: 0.28 })
    tone({ freq: 784, start: 0.16, duration: 0.34, type: 'sine', volume: 0.32 })
  },

  // 答错 —— 错误音（下行两音 + 低频噪声）
  wrong() {
    tone({ freq: 330, duration: 0.2, type: 'sawtooth', volume: 0.2, glideTo: 220 })
    tone({ freq: 220, start: 0.18, duration: 0.34, type: 'sawtooth', volume: 0.18, glideTo: 140 })
    noise({ start: 0.02, duration: 0.22, volume: 0.16 })
  },

  // 比赛开始 —— 开始音（号角式上行）
  gameStart() {
    tone({ freq: 392, duration: 0.2, type: 'sawtooth', volume: 0.2 })
    tone({ freq: 523, start: 0.18, duration: 0.2, type: 'sawtooth', volume: 0.2 })
    tone({ freq: 659, start: 0.36, duration: 0.5, type: 'sawtooth', volume: 0.24 })
  },

  // 比赛结束 / 公布排名 —— 颁奖音（华丽和弦）
  award() {
    const notes = [523, 659, 784, 1047]
    notes.forEach((f, i) => {
      tone({ freq: f, start: i * 0.13, duration: 0.5, type: 'triangle', volume: 0.22 })
    })
    tone({ freq: 261, start: 0.4, duration: 0.9, type: 'sine', volume: 0.18 })
  },

  // 点击反馈
  click() {
    tone({ freq: 1200, duration: 0.04, type: 'sine', volume: 0.12 })
  },
}

export function playSound(name) {
  try {
    if (sounds[name]) sounds[name]()
  } catch (e) {
    console.warn('播放音效失败:', name, e)
  }
}

export default sounds
