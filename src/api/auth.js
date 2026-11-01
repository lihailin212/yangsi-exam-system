import request from './index'

export const login = (data) => request.post('/auth/login', data)
export const changePassword = (data) => request.post('/auth/change-password', data)
