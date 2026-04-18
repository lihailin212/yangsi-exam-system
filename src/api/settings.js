import request from './index'

export const getSettings = () => request.get('/settings')
export const getPublicSettings = () => request.get('/settings/public')
export const updateSettings = (data) => request.post('/settings', data)
