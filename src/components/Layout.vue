<template>
  <el-container class="layout-container">
    <!-- Sidebar -->
    <el-aside 
      :width="sidebarWidth" 
      class="sidebar" 
      :class="{ 'sidebar-mobile': isMobile, 'sidebar-open': sidebarOpen }"
    >
      <!-- Logo -->
      <div class="sidebar-header">
        <div class="logo">
          <div class="logo-icon">
            <img v-if="settingsStore.logoUrl" :src="settingsStore.logoUrl" class="logo-img" />
            <svg v-else viewBox="0 0 100 100" class="logo-svg">
              <defs>
                <linearGradient id="sidebarLogoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" style="stop-color:#14FFEC"/>
                  <stop offset="100%" style="stop-color:#0D7377"/>
                </linearGradient>
              </defs>
              <circle cx="50" cy="50" r="45" fill="url(#sidebarLogoGradient)"/>
              <path d="M50 25 L50 75 M30 50 L70 50" stroke="white" stroke-width="6" stroke-linecap="round"/>
            </svg>
          </div>
          <transition name="fade">
            <span v-if="!isMobile || sidebarOpen" class="logo-text">{{ settingsStore.systemName || '杨思学' }}</span>
          </transition>
        </div>
      </div>

      <!-- Navigation -->
      <el-menu
        :default-active="activeMenu"
        class="sidebar-menu"
        @select="handleMenuSelect"
        :collapse="isMobile && !sidebarOpen"
        :collapse-transition="false"
      >
        <el-menu-item 
          v-for="(item, index) in menuItems" 
          :key="item.path"
          :index="item.path"
          class="menu-item"
          :style="{ animationDelay: `${index * 50}ms` }"
        >
          <el-icon class="menu-icon"><component :is="item.icon" /></el-icon>
          <template #title>
            <span class="menu-title">{{ item.title }}</span>
          </template>
        </el-menu-item>
      </el-menu>

      <!-- User Section -->
      <div class="sidebar-footer" v-if="!isMobile || sidebarOpen">
        <div class="user-card">
          <div class="user-avatar">
            <span>{{ userInitials }}</span>
          </div>
          <transition name="fade">
            <div v-if="!isMobile" class="user-info">
              <span class="user-name">{{ userName }}</span>
              <span class="user-role">{{ userRole }}</span>
            </div>
          </transition>
        </div>
      </div>
    </el-aside>

    <!-- Mobile Overlay -->
    <div 
      v-if="sidebarOpen && isMobile" 
      class="sidebar-overlay" 
      @click="sidebarOpen = false"
    ></div>

    <!-- Main Content -->
    <el-container class="main-container">
      <!-- Header -->
      <el-header class="header">
        <div class="header-left">
          <button class="menu-toggle" @click="toggleSidebar">
            <el-icon><Expand v-if="sidebarOpen" /><Fold v-else /></el-icon>
          </button>
          <div class="breadcrumb">
            <span class="breadcrumb-item">{{ currentPageTitle }}</span>
          </div>
        </div>
        
        <div class="header-right">
          <!-- Time Display -->
          <div class="time-display">
            <el-icon><Clock /></el-icon>
            <span>{{ currentTime }}</span>
          </div>

          <!-- Notifications -->
          <el-dropdown trigger="click" class="notification-dropdown">
            <button class="icon-btn">
              <el-icon><Bell /></el-icon>
              <span class="notification-badge" v-if="unreadCount > 0">{{ unreadCount }}</span>
            </button>
            <template #dropdown>
              <el-dropdown-menu class="notification-menu">
                <div class="notification-header">
                  <span>通知</span>
                  <el-button type="primary" link size="small" @click="markAllRead" v-if="unreadCount > 0">全部已读</el-button>
                </div>
                <template v-if="notifications.length > 0">
                  <el-dropdown-item v-for="n in notifications" :key="'notif-' + n.id">
                    <div class="notification-item">
                      <div class="notification-content">
                        <p>{{ n.title }}</p>
                        <span>{{ formatRelativeTime(n.submitted_at) }}</span>
                      </div>
                    </div>
                  </el-dropdown-item>
                </template>
                <div v-else class="notification-empty">
                  <span>暂无通知</span>
                </div>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <!-- User Menu -->
          <el-dropdown trigger="click" @command="handleCommand">
            <button class="user-btn">
              <div class="user-avatar-small">
                <span>{{ userInitials }}</span>
              </div>
              <span class="user-name-small">{{ userEmployeeId }}</span>
              <el-icon><CaretBottom /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon>
                  个人中心
                </el-dropdown-item>
                <el-dropdown-item command="settings">
                  <el-icon><Setting /></el-icon>
                  系统设置
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- Main Content Area -->
      <el-main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import { getRecentRecords } from '@/api/exams'
import { 
  HomeFilled, 
  Reading, 
  Edit, 
  DataAnalysis, 
  User, 
  Setting, 
  Bell,
  Clock,
  Fold,
  Expand,
  CaretBottom,
  SwitchButton,
  Document,
  TrendCharts
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const settingsStore = useSettingsStore()

const activeMenu = computed(() => route.path)
const userName = computed(() => authStore.userName || '用户')
const userEmployeeId = computed(() => authStore.employeeId || '')
const userInitials = computed(() => {
  const name = userName.value
  return name.length > 2 ? name.slice(-2) : name.slice(0, 2)
})
const userRole = computed(() => authStore.isAdmin ? '系统管理员' : '普通用户')

const currentPageTitle = computed(() => {
  const item = menuItems.value.find(m => m.path === activeMenu.value)
  return item?.title || '首页'
})

const isMobile = ref(false)
const sidebarOpen = ref(false)
const sidebarWidth = computed(() => {
  if (isMobile.value) return sidebarOpen.value ? '240px' : '0px'
  return '240px'
})

const currentTime = ref('')
let timeInterval = null
let notifInterval = null
let notifTickInterval = null
const notifTick = ref(0)

const updateTime = () => {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const allMenuItems = [
  { path: '/dashboard', title: '管理首页', icon: 'HomeFilled', admin: true },
  { path: '/questions', title: '题库管理', icon: 'Reading', admin: true },
  { path: '/exams', title: '考试管理', icon: 'Edit', admin: true },
  { path: '/my-exams', title: '我的考试', icon: 'Tickets', admin: false },
  { path: '/statistics', title: '数据统计', icon: 'DataAnalysis', admin: true },
  { path: '/students', title: '学员管理', icon: 'User', admin: true },
  { path: '/settings', title: '系统设置', icon: 'Setting', admin: true },
]

const menuItems = computed(() => {
  return allMenuItems.filter(item => authStore.isAdmin || !item.admin)
})

// 计算相对时间
const formatRelativeTime = (dateStr) => {
  if (!dateStr) return ''
  // 服务器返回UTC时间，解析后加上8小时（中国时区）得到本地时间
  const [datePart, timePart] = dateStr.split('T')
  const [year, month, day] = datePart.split('-').map(Number)
  const [hour, minute, second] = timePart.split('.')[0].split(':').map(Number)
  // 服务器使用UTC时间，需要加8小时转为中国本地时间
  const date = new Date(year, month - 1, day, hour + 8, minute, second)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  const diffHour = Math.floor(diffMs / 3600000)
  const diffDay = Math.floor(diffMs / 86400000)

  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin}分钟前`
  if (diffHour < 24) return `${diffHour}小时前`
  if (diffDay < 7) return `${diffDay}天前`
  return date.toLocaleDateString('zh-CN')
}

// 加载通知数据
const loadNotifications = async () => {
  try {
    const data = await getRecentRecords()
    const arr = Array.isArray(data) ? data : []
    const list = []
    for (let i = 0; i < arr.length; i++) {
      const r = arr[i]
      list.push({
        id: 'r' + r.id,
        record_id: r.id,
        title: (r.user_name || r.employee_id || '未知') + '完成了「' + (r.exam_title || '考试') + '」',
        submitted_at: r.submitted_at,
        read: false
      })
    }
    // 合并本地已读状态
    const readIds = getReadIds()
    list.forEach(n => {
      if (readIds.has(n.id)) n.read = true
    })
    notifications.value = list
  } catch (e) {
    console.error('加载通知失败:', e)
    notifications.value = []
  }
}

const notifications = ref([])

// 从本地存储读写已读通知ID
const READ_STORAGE_KEY = 'exam_notif_read_ids'

const getReadIds = () => {
  try {
    const ids = JSON.parse(localStorage.getItem(READ_STORAGE_KEY) || '[]')
    return new Set(ids)
  } catch { return new Set() }
}

const saveReadIds = (ids) => {
  localStorage.setItem(READ_STORAGE_KEY, JSON.stringify([...ids]))
}

const unreadCount = computed(() => notifications.value.filter(n => !n.read).length)

const markAllRead = () => {
  notifications.value.forEach(n => n.read = true)
  const allIds = notifications.value.map(n => n.id)
  saveReadIds(new Set(allIds))
}

const checkMobile = () => {
  isMobile.value = window.innerWidth < 768
  if (!isMobile.value) sidebarOpen.value = false
}

const toggleSidebar = () => {
  sidebarOpen.value = !sidebarOpen.value
}

// 监听考试提交事件，刷新通知
const handleExamSubmitted = () => {
  if (authStore.token) loadNotifications()
}

// 监听 token 变化，初始化或重置轮询
watch(() => authStore.token, (token) => {
  if (notifInterval) clearInterval(notifInterval)
  if (notifTickInterval) clearInterval(notifTickInterval)
  if (token) {
    loadNotifications()
    notifInterval = setInterval(loadNotifications, 5000)
    notifTickInterval = setInterval(() => { notifTick.value++ }, 60000)
  }
}, { immediate: false })

onMounted(() => {
  checkMobile()
  updateTime()
  if (authStore.token) {
    loadNotifications()
    notifInterval = setInterval(loadNotifications, 5000)
    notifTickInterval = setInterval(() => { notifTick.value++ }, 60000)
  }
  timeInterval = setInterval(updateTime, 1000)
  window.addEventListener('resize', checkMobile)
  window.addEventListener('exam-submitted', handleExamSubmitted)
})

onUnmounted(() => {
  if (timeInterval) clearInterval(timeInterval)
  if (notifInterval) clearInterval(notifInterval)
  if (notifTickInterval) clearInterval(notifTickInterval)
  window.removeEventListener('resize', checkMobile)
  window.removeEventListener('exam-submitted', handleExamSubmitted)
})

// 每次路由切换时刷新通知
watch(() => route.path, () => {
  if (authStore.token) loadNotifications()
})

const handleMenuSelect = (index) => {
  router.push(index)
  if (isMobile.value) sidebarOpen.value = false
}

const handleCommand = (command) => {
  if (command === 'logout') {
    authStore.logout()
    router.push('/login')
  } else if (command === 'profile') {
    router.push('/settings')
  }
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
  background: var(--neutral-50);
}

/* Sidebar */
.sidebar {
  background: linear-gradient(180deg, #141B22 0%, #0A0F14 100%);
  display: flex;
  flex-direction: column;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.sidebar::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 100%;
  background: linear-gradient(180deg, rgba(13, 115, 119, 0.1) 0%, transparent 50%);
  pointer-events: none;
}

.sidebar-header {
  padding: var(--space-5);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.logo {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.logo-icon {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.logo-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.logo-svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 0 8px rgba(20, 255, 236, 0.3));
}

.logo-text {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 600;
  color: #fff;
  letter-spacing: 3px;
  white-space: nowrap;
}

/* Menu */
.sidebar-menu {
  flex: 1;
  background: transparent;
  border: none;
  padding: var(--space-3);
}

.sidebar-menu :deep(.el-menu-item) {
  height: 48px;
  margin-bottom: var(--space-1);
  border-radius: var(--radius-sm);
  color: rgba(255, 255, 255, 0.7);
  transition: all var(--transition-fast);
  animation: slideUp 0.4s ease-out backwards;
}

.sidebar-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, rgba(13, 115, 119, 0.4), rgba(13, 115, 119, 0.2));
  color: var(--accent-500);
}

.sidebar-menu :deep(.el-menu-item.is-active)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 24px;
  background: linear-gradient(180deg, var(--accent-500), var(--primary-500));
  border-radius: 0 var(--radius-full) var(--radius-full) 0;
}

.menu-icon {
  font-size: 18px;
  margin-right: var(--space-3);
}

.menu-title {
  font-size: 14px;
  font-weight: 500;
}

/* User Section */
.sidebar-footer {
  padding: var(--space-4);
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.user-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  background: rgba(255, 255, 255, 0.03);
  border-radius: var(--radius-sm);
}

.user-avatar {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--primary-500), var(--accent-500));
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.user-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.user-name {
  font-size: 13px;
  font-weight: 500;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-role {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}

/* Mobile Styles */
.sidebar-mobile {
  position: fixed;
  top: 0;
  left: 0;
  height: 100vh;
  z-index: 1000;
  width: 0 !important;
  overflow: hidden;
  transform: translateX(-100%);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.sidebar-mobile.sidebar-open {
  width: 240px !important;
  transform: translateX(0);
}

.sidebar-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 999;
  backdrop-filter: blur(4px);
}

/* Header */
.header {
  background: #fff;
  border-bottom: 1px solid var(--neutral-200);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 var(--space-6);
  height: 64px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.menu-toggle {
  width: 40px;
  height: 40px;
  border: none;
  background: var(--neutral-100);
  border-radius: var(--radius-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: var(--neutral-600);
  transition: all var(--transition-fast);
}

.menu-toggle:hover {
  background: var(--neutral-200);
  color: var(--neutral-800);
}

.breadcrumb-item {
  font-size: 16px;
  font-weight: 600;
  color: var(--neutral-800);
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.time-display {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--neutral-100);
  border-radius: var(--radius-full);
  font-size: 13px;
  color: var(--neutral-600);
  font-family: var(--font-number);
}

.icon-btn {
  position: relative;
  width: 40px;
  height: 40px;
  border: none;
  background: var(--neutral-100);
  border-radius: var(--radius-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: var(--neutral-600);
  transition: all var(--transition-fast);
}

.icon-btn:hover {
  background: var(--neutral-200);
  color: var(--neutral-800);
}

.notification-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  min-width: 16px;
  height: 16px;
  background: #F56C6C;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 600;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
}

.user-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  padding-left: var(--space-1);
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.user-btn:hover {
  background: var(--neutral-100);
}

.user-avatar-small {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--primary-500), var(--accent-500));
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}

.user-name-small {
  font-size: 14px;
  color: var(--neutral-700);
}

/* Notification Menu */
.notification-menu {
  width: 320px;
  padding: 0;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--neutral-200);
  font-weight: 600;
  color: var(--neutral-800);
}

.notification-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-2) 0;
}

.notification-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 14px;
  flex-shrink: 0;
}

.notification-content p {
  font-size: 13px;
  color: var(--neutral-700);
  margin: 0;
}

.notification-content span {
  font-size: 11px;
  color: var(--neutral-400);
}

.notification-empty {
  padding: 20px;
  text-align: center;
  color: var(--neutral-400);
  font-size: 13px;
}

/* Main Content */
.main-container {
  flex-direction: column;
}

.main-content {
  background: var(--neutral-50);
  padding: var(--space-6);
  overflow-y: auto;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.page-enter-active,
.page-leave-active {
  transition: all 0.3s ease;
}

.page-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* Responsive */
@media (max-width: 768px) {
  .header {
    padding: 0 var(--space-4);
  }
  
  .time-display {
    display: none;
  }
  
  .user-name-small {
    display: none;
  }
  
  .main-content {
    padding: var(--space-4);
  }
}
</style>
