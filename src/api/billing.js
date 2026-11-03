import request from './index'

// ---- 用户侧 ----
export const getBillingConfig = () => request.get('/billing/config')
export const getPlans = () => request.get('/billing/plans')
export const getMySubscription = () => request.get('/billing/me')
export const redeemCode = (code) => request.post('/billing/redeem', { code })
export const createOrder = (data) => request.post('/billing/orders', data)

// ---- 管理侧 ----
export const getAdminPlans = () => request.get('/billing/admin/plans')
export const createPlan = (data) => request.post('/billing/admin/plans', data)
export const updatePlan = (id, data) => request.put(`/billing/admin/plans/${id}`, data)
export const deletePlan = (id) => request.delete(`/billing/admin/plans/${id}`)

export const getOrders = (params) => request.get('/billing/admin/orders', { params })
export const getCodes = (params) => request.get('/billing/admin/codes', { params })
export const generateCodes = (data) => request.post('/billing/admin/codes/generate', data)
export const voidCode = (id) => request.post(`/billing/admin/codes/${id}/void`)
export const adminRedeemCode = (data) => request.post('/billing/admin/codes/redeem-for', data)

// ---- 系统设置里的收费开关 ----
export const getBillingSettings = () => request.get('/settings/billing')
export const saveBillingSettings = (data) => request.post('/settings/billing', data)
