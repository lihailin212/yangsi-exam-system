import request from './index'

export const getStudents = (params) => request.get('/students', { params })
export const createStudent = (data) => request.post('/students', data)
export const updateStudent = (id, data) => request.put(`/students/${id}`, data)
export const deleteStudent = (id) => request.delete(`/students/${id}`)
export const getStudentRecords = (id) => request.get(`/students/${id}/records`)
