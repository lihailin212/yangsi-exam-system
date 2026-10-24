import request from './index'

// 统一解包：后端拦截器已返回 res.data，这里兼容 axios 原始响应
const unwrap = (res) => (res && res.data !== undefined ? res.data : res)

export function getArenas(params = {}) {
  return request.get('/arenas/', { params }).then(unwrap)
}

export function getArena(arenaId) {
  return request.get(`/arenas/${arenaId}`).then(unwrap)
}

export function createArena(data) {
  return request.post('/arenas/', data).then(unwrap)
}

export function updateArena(arenaId, data) {
  return request.put(`/arenas/${arenaId}`, data).then(unwrap)
}

export function deleteArena(arenaId) {
  return request.delete(`/arenas/${arenaId}`).then(unwrap)
}

export function getArenaByInvite(code) {
  return request.get(`/arenas/invite/${code}`).then(unwrap)
}

export function refreshArenaInvite(arenaId) {
  return request.post(`/arenas/${arenaId}/refresh-invite`).then(unwrap)
}

// 队伍管理
export function getArenaTeams(arenaId) {
  return request.get(`/arenas/${arenaId}/teams`).then(unwrap)
}

export function addTeam(arenaId, data) {
  return request.post(`/arenas/${arenaId}/teams`, data).then(unwrap)
}

export function updateTeam(teamId, data) {
  return request.put(`/arenas/teams/${teamId}`, data).then(unwrap)
}

export function deleteTeam(teamId) {
  return request.delete(`/arenas/teams/${teamId}`).then(unwrap)
}

// 题目管理
export function getArenaQuestions(arenaId) {
  return request.get(`/arenas/${arenaId}/questions`).then(unwrap)
}

// 选手可见题目（不含答案，防作弊）
export function getArenaPublicQuestions(arenaId) {
  return request.get(`/arenas/${arenaId}/questions/public`).then(unwrap)
}

export function addArenaQuestions(arenaId, questions) {
  return request.post(`/arenas/${arenaId}/questions`, questions).then(unwrap)
}

export function deleteArenaQuestion(questionId) {
  return request.delete(`/arenas/questions/${questionId}`).then(unwrap)
}

// 答案管理
export function submitAnswer(data) {
  return request.post('/arenas/answers', data).then(unwrap)
}

export function getTeamAnswers(teamId) {
  return request.get(`/arenas/teams/${teamId}/answers`).then(unwrap)
}

// 主持人判定（is_correct 传 null 时服务端自动比对客观题）
export function judgeAnswer(answerId, isCorrect, score) {
  return request
    .put(`/arenas/answers/${answerId}`, null, {
      params: { is_correct: isCorrect, score: score ?? 0 },
    })
    .then(unwrap)
}

// 选手管理
export function playerJoin(data) {
  return request.post('/arenas/players/join', data).then(unwrap)
}

export function getTeamPlayers(teamId) {
  return request.get(`/arenas/teams/${teamId}/players`).then(unwrap)
}

// 轮次管理
export function getArenaRounds(arenaId) {
  return request.get(`/arenas/${arenaId}/rounds`).then(unwrap)
}

export function createArenaRound(arenaId, data) {
  return request.post(`/arenas/${arenaId}/rounds`, data).then(unwrap)
}

export function advanceArenaRound(arenaId, roundId) {
  return request.post(`/arenas/${arenaId}/rounds/${roundId}/advance`).then(unwrap)
}

// 排名与平局
export function getArenaStandings(arenaId) {
  return request.get(`/arenas/${arenaId}/standings`).then(unwrap)
}

// 淘汰 / 复活
export function eliminateTeams(arenaId, teamIds) {
  return request.post(`/arenas/${arenaId}/eliminate`, { team_ids: teamIds }).then(unwrap)
}

export function eliminateBottomTeams(arenaId, count) {
  return request
    .post(`/arenas/${arenaId}/eliminate-bottom`, null, { params: { count } })
    .then(unwrap)
}

export function resurrectTeam(arenaId, teamId) {
  return request.post(`/arenas/${arenaId}/resurrect`, { team_id: teamId }).then(unwrap)
}

// 日志
export function getArenaLogs(arenaId, limit = 100) {
  return request.get(`/arenas/${arenaId}/logs`, { params: { limit } }).then(unwrap)
}

// 导出（Excel 文件流）
export async function exportArenaExcel(arenaId) {
  const token = localStorage.getItem('token')
  const response = await fetch(`/api/arenas/${arenaId}/export`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    throw new Error('导出失败')
  }
  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') || ''
  let filename = `擂台赛_${arenaId}.xlsx`
  const match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (match) {
    filename = decodeURIComponent(match[1])
  }
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  return filename
}

export function exportArenaAnswers(arenaId) {
  return request.get(`/arenas/${arenaId}/export/json`).then(unwrap)
}

// 重置求助状态
export function resetTeamHelp(arenaId) {
  return request.post(`/arenas/${arenaId}/reset-help`).then(unwrap)
}
