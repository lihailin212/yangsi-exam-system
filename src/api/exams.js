import request from './index'

export const getExams = (params) => request.get('/exams', { params })
export const getExam = (id) => request.get(`/exams/${id}`)
export const createExam = (data) => request.post('/exams', data)
export const updateExam = (id, data) => request.put(`/exams/${id}`, data)
export const deleteExam = (id) => request.delete(`/exams/${id}`)
export const submitExam = (id, data) => request.post(`/exams/${id}/submit`, data)
export const getExamRecords = (id) => request.get(`/exams/${id}/records`)
export const getRecentRecords = () => request.get('/exam-records/recent')
