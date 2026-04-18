import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as apiLogin } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userId = ref(Number(localStorage.getItem('userId')) || 0)
  const userName = ref(localStorage.getItem('userName') || '')
  const isAdmin = ref(localStorage.getItem('isAdmin') === 'true')
  const employeeId = ref(localStorage.getItem('employeeId') || '')

  async function doLogin(empId, password) {
    const res = await apiLogin({ employee_id: empId, password })
    token.value = res.access_token
    userId.value = res.user_id
    userName.value = res.name
    isAdmin.value = res.is_admin
    employeeId.value = res.employee_id
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('userId', res.user_id)
    localStorage.setItem('userName', res.name)
    localStorage.setItem('isAdmin', res.is_admin)
    localStorage.setItem('employeeId', res.employee_id)
    return res
  }

  function logout() {
    token.value = ''
    userId.value = 0
    userName.value = ''
    isAdmin.value = false
    employeeId.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('userId')
    localStorage.removeItem('userName')
    localStorage.removeItem('isAdmin')
    localStorage.removeItem('employeeId')
  }

  return { token, userId, userName, isAdmin, employeeId, doLogin, logout }
})
