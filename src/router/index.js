import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/my-exams' },
  {
    path: '/',
    component: () => import('@/components/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: 'dashboard', component: () => import('@/views/Dashboard.vue'), meta: { title: '管理首页', requiresAdmin: true } },
      { path: 'questions', component: () => import('@/views/Questions.vue'), meta: { title: '题库管理', requiresAdmin: true } },
      { path: 'exams', component: () => import('@/views/Exams.vue'), meta: { title: '考试管理', requiresAdmin: true } },
      { path: 'my-exams', component: () => import('@/views/StudentExams.vue'), meta: { title: '我的考试' } },
      { path: 'statistics', component: () => import('@/views/Statistics.vue'), meta: { title: '数据统计', requiresAdmin: true } },
      { path: 'settings', component: () => import('@/views/Settings.vue'), meta: { title: '系统设置', requiresAdmin: true } },
      { path: 'students', component: () => import('@/views/Students.vue'), meta: { title: '学员管理', requiresAdmin: true } },
    ]
  },
  { path: '/login', component: () => import('@/views/Login.vue') },
  { path: '/exam-take/:id', component: () => import('@/views/ExamTake.vue'), meta: { requiresAuth: true } },
  { path: '/exam-result/:id', component: () => import('@/views/ExamResult.vue'), meta: { requiresAuth: true } },
  { path: '/exam-login/:examId', component: () => import('@/views/ExamLogin.vue') },
  { path: '/invite/:code', component: () => import('@/views/ExamInvite.vue') },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const isAdmin = localStorage.getItem('isAdmin') === 'true'

  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next(isAdmin ? '/dashboard' : '/my-exams')
  } else if (to.meta.requiresAdmin && !isAdmin) {
    next('/my-exams')
  } else {
    next()
  }
})

export default router
