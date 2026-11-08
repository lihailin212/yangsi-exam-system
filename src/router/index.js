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
      { path: 'arena', component: () => import('@/views/ArenaManage.vue'), meta: { title: '专业擂台赛', requiresAdmin: true } },
      { path: 'my-exams', component: () => import('@/views/StudentExams.vue'), meta: { title: '我的考试' } },
      { path: 'wrong-questions', component: () => import('@/views/WrongQuestions.vue'), meta: { title: '我的错题本' } },
      { path: 'self-study', component: () => import('@/views/SelfStudy.vue'), meta: { title: '考生自学', requiresEntitlement: true } },
      { path: 'statistics', component: () => import('@/views/Statistics.vue'), meta: { title: '数据统计', requiresAdmin: true } },
      { path: 'settings', component: () => import('@/views/Settings.vue'), meta: { title: '系统设置', requiresAdmin: true } },
      { path: 'students', component: () => import('@/views/Students.vue'), meta: { title: '学员管理', requiresAdminOrOrgAdmin: true } },
      // ---- 收费 / 机构 ----
      { path: 'subscribe', component: () => import('@/views/Subscribe.vue'), meta: { title: '我的订阅' } },
      { path: 'past-papers', component: () => import('@/views/PastPapers.vue'), meta: { title: '历年真题', requiresEntitlement: true } },
      { path: 'org-members', component: () => import('@/views/OrgMembers.vue'), meta: { title: '机构学员', requiresOrgAdmin: true } },
      { path: 'organizations', component: () => import('@/views/Organizations.vue'), meta: { title: '机构管理', requiresAdmin: true } },
      { path: 'subscription-plans', component: () => import('@/views/SubscriptionPlans.vue'), meta: { title: '套餐管理', requiresAdmin: true } },
      { path: 'subscription-orders', component: () => import('@/views/SubscriptionOrders.vue'), meta: { title: '开通记录', requiresAdmin: true } },
    ]
  },
  { path: '/login', component: () => import('@/views/Login.vue') },
  { path: '/register', component: () => import('@/views/Register.vue') },
  { path: '/change-password', component: () => import('@/views/ChangePassword.vue') },
  { path: '/exam-take/:id', component: () => import('@/views/ExamTake.vue'), meta: { requiresAuth: true, requiresEntitlement: true } },
  { path: '/exam-result/:id', component: () => import('@/views/ExamResult.vue'), meta: { requiresAuth: true } },
  { path: '/exam-login/:examId', component: () => import('@/views/ExamLogin.vue') },
  { path: '/invite/:code', component: () => import('@/views/ExamInvite.vue') },
  // 擂台赛路由
  { path: '/arena-join', component: () => import('@/views/ArenaJoin.vue') },
  { path: '/arena-host/:arenaId', component: () => import('@/views/ArenaHost.vue'), meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/arena-player/:arenaId/:teamId', component: () => import('@/views/ArenaPlayer.vue') },
]

const router = createRouter({
  // 使用 HashRouter，确保手机端扫码访问正常
  // URL 格式：https://xxx/#/exam-login/2
  history: createWebHashHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const isAdmin = localStorage.getItem('isAdmin') === 'true'
  const mustChangePassword = localStorage.getItem('mustChangePassword') === 'true'
  // 收费总开关（main.js 启动时从 /api/auth/capabilities 拉下来）
  const billingEnabled = localStorage.getItem('billingEnabled') === 'true'
  const entitlementActive = localStorage.getItem('entitlementActive') !== 'false'
  const orgRole = localStorage.getItem('orgRole') || ''
  const organizationId = Number(localStorage.getItem('organizationId')) || 0

  if (to.path === '/change-password') {
    // 改密码页不走下面的规则，但没登录也不该进
    if (!token) next('/login')
    else next()
  } else if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (mustChangePassword) {
    // 初始密码还没改，先去改密码
    next('/change-password')
  } else if (to.path === '/login' && token) {
    next(isAdmin ? '/dashboard' : '/my-exams')
  } else if (to.path === '/register' && token) {
    next(isAdmin ? '/dashboard' : '/my-exams')
  } else if (to.meta.requiresAdmin && !isAdmin) {
    next('/my-exams')
  } else if (to.meta.requiresAdminOrOrgAdmin && !isAdmin && !(orgRole === 'admin' && organizationId)) {
    // 学员管理：超管看全部，机构管理员只看本机构
    next(isAdmin ? '/dashboard' : '/my-exams')
  } else if (to.meta.requiresOrgAdmin && !(orgRole === 'admin' && organizationId)) {
    // 机构管理员入口：非机构管理员回自己的首页
    next(isAdmin ? '/dashboard' : '/my-exams')
  } else if (to.meta.requiresEntitlement && billingEnabled && !entitlementActive) {
    // 订阅过期/未开通：拦在订阅页（后端也会返回 402 兜底）
    next('/subscribe')
  } else {
    next()
  }
})

export default router
