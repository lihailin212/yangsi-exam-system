import request from './index'

export const getOrganizations = () => request.get('/organizations')
export const createOrganization = (data) => request.post('/organizations', data)
export const updateOrganization = (id, data) => request.put(`/organizations/${id}`, data)
export const grantOrganization = (id, data) => request.post(`/organizations/${id}/grant`, data)
export const rotateInviteCode = (id) => request.post(`/organizations/${id}/invite-code/rotate`)

export const getOrgMembers = (id) => request.get(`/organizations/${id}/members`)
export const addOrgMember = (id, data) => request.post(`/organizations/${id}/members`, data)
export const updateOrgMember = (id, userId, data) =>
  request.put(`/organizations/${id}/members/${userId}`, data)
export const getOrgStats = (id) => request.get(`/organizations/${id}/stats`)
