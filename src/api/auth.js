import request from './index'

export const login = (data) => request.post('/auth/login', data)
