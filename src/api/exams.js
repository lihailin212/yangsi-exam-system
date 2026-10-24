import request from './index'

export const getExams = (params) => request.get('/exams', { params })
export const getExam = (id) => request.get(`/exams/${id}`)
export const createExam = (data) => request.post('/exams', data)
export const updateExam = (id, data) => request.put(`/exams/${id}`, data)
export const deleteExam = (id) => request.delete(`/exams/${id}`)
export const submitExam = (id, data) => request.post(`/exams/${id}/submit`, data)
// 进入考试：开启/复用作答会话，取服务端权威的截止时间
export const startExam = (id) => request.post(`/exams/${id}/start`)
// 作答草稿同步到服务端，超时可据此自动交卷
export const saveExamDraft = (id, answers) => request.post(`/exams/${id}/draft`, { answers })
export const getExamRecords = (id) => request.get(`/exams/${id}/records`)
export const getRecentRecords = () => request.get('/exam-records/recent')

// 导出普通考试成绩 Excel（总成绩表 / 答题明细 / 统计表）
export async function exportExamExcel(examId) {
  const token = localStorage.getItem('token')
  const response = await fetch(`/api/exams/${examId}/export`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    throw new Error('导出失败')
  }
  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') || ''
  let filename = `考试_${examId}_成绩表.xlsx`
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
