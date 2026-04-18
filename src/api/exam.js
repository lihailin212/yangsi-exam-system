import request from './index'

/**
 * 获取考试信息（无需认证）
 */
export const getExamInfo = (examId) => request.get(`/exam-login/${examId}`)

/**
 * 考生登录（无需认证）
 */
export const examLogin = (data) => request.post('/exam-login', data)
