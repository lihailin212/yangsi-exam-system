import request from './index'

// 题库在远端，生成题目要回库取题干和图片，往返比较慢，超时给宽一点
const SLOW_TIMEOUT = 60000

// 按所选方式生成一组练习题（不含答案）
export const generatePractice = (data) =>
  request.post('/self-study/generate', data, { timeout: SLOW_TIMEOUT })

// 提交一道题的作答：返回对错、正确答案和解析；答错自动进错题本
export const submitPracticeAnswer = (data) =>
  request.post('/self-study/answer', data, { timeout: SLOW_TIMEOUT })

// 交卷：未作答的题按做错处理，记进错题本
export const finishPractice = (data) =>
  request.post('/self-study/finish', data, { timeout: SLOW_TIMEOUT })
