// 擂台赛 WebSocket 客户端
//
// 主持人：connect(arenaId, { role: 'host', token: 管理员令牌 })
// 选手：  connect(arenaId, { role: 'player', token: 加入时下发的选手令牌 })

class ArenaWebSocket {
  constructor() {
    this.ws = null
    this.arenaId = null
    this.role = 'player'
    this.token = ''
    this.teamId = null
    this.listeners = new Map()
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.reconnectDelay = 1000
    this.manualClose = false
  }

  connect(arenaId, options = {}) {
    this.arenaId = arenaId
    this.role = options.role || 'player'
    this.token = options.token || ''
    this.teamId = options.teamId ?? null
    this.manualClose = false

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const params = new URLSearchParams({ role: this.role })
    if (this.token) params.set('token', this.token)
    const wsUrl = `${protocol}//${host}/ws/arenas/${arenaId}?${params.toString()}`

    try {
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        this.reconnectAttempts = 0
        this.emit('connected', {})
        this.send('sync_state', {})
      }

      this.ws.onclose = (event) => {
        this.emit('disconnected', { code: event.code })
        if (!this.manualClose && this.reconnectAttempts < this.maxReconnectAttempts) {
          setTimeout(() => {
            this.reconnectAttempts++
            this.connect(this.arenaId, {
              role: this.role,
              token: this.token,
              teamId: this.teamId,
            })
          }, this.reconnectDelay * this.reconnectAttempts)
        }
      }

      this.ws.onerror = (error) => {
        this.emit('error', error)
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          this.emit(data.type, data.payload)
        } catch (e) {
          console.error('Failed to parse message:', e)
        }
      }
    } catch (e) {
      console.error('Failed to connect WebSocket:', e)
    }
  }

  disconnect() {
    this.manualClose = true
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  send(type, payload = {}) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, payload }))
    }
  }

  // 事件监听
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, [])
    }
    this.listeners.get(event).push(callback)
  }

  off(event, callback) {
    if (this.listeners.has(event)) {
      const callbacks = this.listeners.get(event)
      const index = callbacks.indexOf(callback)
      if (index > -1) {
        callbacks.splice(index, 1)
      }
    }
  }

  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(callback => {
        try {
          callback(data)
        } catch (e) {
          console.error('Event callback error:', e)
        }
      })
    }
  }

  // ---- 选手操作 ----

  startRush(questionId) {
    this.send('start_rush', { question_id: questionId })
  }

  rushAnswer(questionId) {
    this.send('rush_answer', {
      question_id: questionId,
      device_id: this.getDeviceId(),
    })
  }

  submitAnswer(questionId, answer, timeUsed, helpUsed = '', timeout = false) {
    this.send('answer_submit', {
      question_id: questionId,
      answer,
      time_used: timeUsed,
      help_used: helpUsed,
      timeout,
    })
  }

  requestHelp(helpType, questionId) {
    this.send('help_request', {
      help_type: helpType,
      question_id: questionId,
    })
  }

  // ---- 主持人控制 ----

  hostControl(action, payload = {}) {
    this.send('host_control', { action, ...payload })
  }

  showQuestion(questionId) {
    this.hostControl('show_question', { question_id: questionId })
  }

  startRushQuestion(questionId) {
    this.hostControl('start_rush', { question_id: questionId })
  }

  startTimer(duration = 15) {
    this.hostControl('start_timer', { duration })
  }

  stopTimer() {
    this.hostControl('stop_timer', {})
  }

  pauseGame() {
    this.hostControl('pause', {})
  }

  resumeGame() {
    this.hostControl('resume', {})
  }

  startGame() {
    this.hostControl('start', {})
  }

  finishGame() {
    this.hostControl('finish', {})
  }

  refreshScores() {
    this.hostControl('score_update', {})
  }

  judgeAnswer(answerId, isCorrect, score) {
    this.hostControl('judge_answer', {
      answer_id: answerId,
      is_correct: isCorrect,
      score,
    })
  }

  // 自动判定单条作答（客观题按标准答案比对；主观题/无标准答案保持待判定）
  autoJudgeAnswer(answerId) {
    this.hostControl('auto_judge_answer', {
      answer_id: answerId,
    })
  }

  // 一键自动判定某题下所有待判定的作答
  autoJudgeAll(questionId) {
    this.hostControl('auto_judge_all', {
      question_id: questionId,
    })
  }

  eliminateTeams(teamIds) {
    this.hostControl('eliminate', { team_ids: teamIds })
  }

  resurrectTeam(teamId) {
    this.hostControl('resurrect', { team_id: teamId })
  }

  resetHelp() {
    this.hostControl('reset_help', {})
  }

  nextRound() {
    this.hostControl('next_round', {})
  }

  startOvertime() {
    this.hostControl('overtime', {})
  }

  // 获取设备ID（用于标识唯一设备）
  getDeviceId() {
    let deviceId = localStorage.getItem('arena_device_id')
    if (!deviceId) {
      deviceId = 'device_' + Math.random().toString(36).substr(2, 9)
      localStorage.setItem('arena_device_id', deviceId)
    }
    return deviceId
  }
}

// 导出单例
const arenaWS = new ArenaWebSocket()

export default arenaWS

// 导出类以便需要多个实例时使用
export { ArenaWebSocket }
