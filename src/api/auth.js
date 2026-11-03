import request from './index'

export const login = (data) =>
  request.post('/auth/login', data, { skipAuthRedirect: true, silent: true })
export const register = (data) =>
  request.post('/auth/register', data, { skipAuthRedirect: true, silent: true })
export const getCapabilities = () => request.get('/auth/capabilities')
export const changePassword = (data) =>
  request.post('/auth/change-password', data, { silent: true })
export const sendSmsCode = (phone) =>
  request.post('/auth/sms/send', { phone }, { skipAuthRedirect: true, silent: true })
export const smsLogin = (data) =>
  request.post('/auth/sms/login', data, { skipAuthRedirect: true, silent: true })
