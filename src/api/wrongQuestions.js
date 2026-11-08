import request from './index'

// 题干带富文本和图片，从远端库取一趟比较慢，超时给宽一点
const SLOW_TIMEOUT = 60000

export const getWrongQuestions = (params) =>
  request.get('/wrong-questions', { params, timeout: SLOW_TIMEOUT })
export const getWrongQuestionStats = () =>
  request.get('/wrong-questions/stats', { timeout: SLOW_TIMEOUT })
export const deleteWrongQuestion = (id) =>
  request.delete(`/wrong-questions/${id}`)
// 用错题生成一张练习卷，返回可直接开考的考试 id
export const generateExamFromWrong = (data) =>
  request.post('/wrong-questions/generate-exam', data, { timeout: SLOW_TIMEOUT })
export const getPracticeExams = () =>
  request.get('/wrong-questions/practice-exams', { timeout: SLOW_TIMEOUT })

// 导出错题记录 Excel
export const exportWrongQuestions = async (params = {}) => {
  const token = localStorage.getItem('token')
  const query = new URLSearchParams(params).toString()
  const url = `/api/wrong-questions/export${query ? '?' + query : ''}`

  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    // 把后端给的原因带出来，别只说一句"导出失败"：
    // 常见的是"没有可导出的错题记录"（当前筛选下一条都没有）。
    let detail = ''
    try {
      const body = await response.json()
      detail = body && body.detail ? String(body.detail) : ''
    } catch (e) { /* 不是 JSON 就用兜底文案 */ }
    throw new Error(detail || '导出失败')
  }
  const blob = await response.blob()
  const contentDisposition = response.headers.get('Content-Disposition')
  let filename = '错题记录.xlsx'
  if (contentDisposition) {
    const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
    if (match) filename = match[1].replace(/['"]/g, '')
  }
  const downloadUrl = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = downloadUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(downloadUrl)
}
