import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, register as apiRegister } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userId = ref(Number(localStorage.getItem('userId')) || 0)
  const userName = ref(localStorage.getItem('userName') || '')
  const isAdmin = ref(localStorage.getItem('isAdmin') === 'true')
  const employeeId = ref(localStorage.getItem('employeeId') || '')
  // 初始密码还没改：true 时只能进改密码页
  const mustChangePassword = ref(localStorage.getItem('mustChangePassword') === 'true')
  // 机构相关（付费单位是机构，个人只有试用期）
  const organizationId = ref(Number(localStorage.getItem('organizationId')) || 0)
  const organizationName = ref(localStorage.getItem('organizationName') || '')
  const orgRole = ref(localStorage.getItem('orgRole') || '')
  const trialExpiresAt = ref(localStorage.getItem('trialExpiresAt') || '')
  const entitlementActive = ref(localStorage.getItem('entitlementActive') !== 'false')

  const isOrgAdmin = computed(() => orgRole.value === 'admin' && organizationId.value > 0)

  function applySession(res) {
    token.value = res.access_token
    userId.value = res.user_id
    userName.value = res.name
    isAdmin.value = !!res.is_admin
    employeeId.value = res.employee_id
    mustChangePassword.value = !!res.must_change_password
    organizationId.value = res.organization_id || 0
    organizationName.value = res.organization_name || ''
    orgRole.value = res.org_role || ''
    trialExpiresAt.value = res.trial_expires_at || ''
    entitlementActive.value = res.entitlement_active !== false
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('userId', res.user_id)
    localStorage.setItem('userName', res.name)
    localStorage.setItem('isAdmin', res.is_admin)
    localStorage.setItem('employeeId', res.employee_id)
    localStorage.setItem('mustChangePassword', mustChangePassword.value)
    localStorage.setItem('organizationId', organizationId.value)
    localStorage.setItem('organizationName', organizationName.value)
    localStorage.setItem('orgRole', orgRole.value)
    localStorage.setItem('trialExpiresAt', trialExpiresAt.value)
    localStorage.setItem('entitlementActive', entitlementActive.value)
  }

  async function doLogin(empId, password) {
    const res = await apiLogin({ employee_id: empId, password })
    applySession(res)
    return res
  }

  async function doRegister(payload) {
    const res = await apiRegister(payload)
    applySession(res)
    return res
  }

  // 密码改完，清掉强制改密的标记
  function clearMustChangePassword() {
    mustChangePassword.value = false
    localStorage.removeItem('mustChangePassword')
  }

  // 权益状态变了（比如刚兑换完码），刷新一下本地标记
  function setEntitlement(active, daysLeft) {
    entitlementActive.value = !!active
    localStorage.setItem('entitlementActive', entitlementActive.value)
  }

  function logout() {
    token.value = ''
    userId.value = 0
    userName.value = ''
    isAdmin.value = false
    employeeId.value = ''
    mustChangePassword.value = false
    organizationId.value = 0
    organizationName.value = ''
    orgRole.value = ''
    trialExpiresAt.value = ''
    entitlementActive.value = true
    ;['token', 'userId', 'userName', 'isAdmin', 'employeeId', 'mustChangePassword',
      'organizationId', 'organizationName', 'orgRole', 'trialExpiresAt',
      'entitlementActive'].forEach(k => localStorage.removeItem(k))
  }

  return { token, userId, userName, isAdmin, employeeId, mustChangePassword,
           organizationId, organizationName, orgRole, trialExpiresAt,
           entitlementActive, isOrgAdmin,
           doLogin, doRegister, applySession, logout, clearMustChangePassword, setEntitlement }
})
