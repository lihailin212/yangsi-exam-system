import request from './index'

export const getDistributions = (examId) =>
  request.get('/distributions', { params: { exam_id: examId } })

export const createDistributions = (data) =>
  request.post('/distributions', data)

export const deleteDistribution = (id) =>
  request.delete(`/distributions/${id}`)

export const getInviteInfo = (code) =>
  request.get(`/invite/${code}`)

export const inviteLogin = (data) =>
  request.post('/invite/login', data)

export const getExamLoginUrl = (examId) =>
  request.get('/distributions/frontend-url', { params: { exam_id: examId } })

export const getExamStudents = (examId) =>
  request.get('/distributions/exam-students', { params: { exam_id: examId } })

export const setExamStudents = (examId, userIds) =>
  request.post('/distributions/exam-students', { exam_id: examId, user_ids: userIds })
