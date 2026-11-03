// -*- coding: utf-8 -*-
/**
 * 收费 / 机构改造的前端冒烟测试（Playwright）。
 *
 * 跑法（仓库根目录）：
 *     npx playwright test e2e/billing.spec.js
 *
 * playwright.config.js 会自动拉起后端（.e2e-data 下的独立 SQLite 库）和前端
 * dev server，跑完自动关掉，不碰线上 Neon，也不碰本地 backend/exam.db。
 *
 * 默认用机器上已装的 Chrome（channel: 'chrome'）；想跑 Playwright 自带的
 * chromium 就删掉 playwright.config.js 里的 channel，并先执行
 *     npx playwright install chromium
 */
const { test, expect } = require('@playwright/test')

const ADMIN_PWD = 'AdminE2E123'
const ADMIN_PWD2 = 'AdminE2E123X' // 上一次跑可能已经改过密

/** 随机手机号，避免重复跑的时候撞上已注册账号 */
function randomPhone() {
  return '139' + String(Date.now()).slice(-8)
}

async function apiPost(request, path, data, token, method) {
  const res = await request.fetch('/api' + path, {
    method: method || 'POST',
    data,
    headers: token ? { Authorization: 'Bearer ' + token } : {},
  })
  return { status: res.status(), body: await res.json().catch(() => ({})) }
}

async function apiGet(request, path, token) {
  const res = await request.get('/api' + path, {
    headers: token ? { Authorization: 'Bearer ' + token } : {},
  })
  return { status: res.status(), body: await res.json().catch(() => ({})) }
}

/** 超管登录（首登会要求改密，这里一步到位） */
async function adminToken(request) {
  for (const pwd of [ADMIN_PWD, ADMIN_PWD2]) {
    const r = await apiPost(request, '/auth/login', { employee_id: 'admin', password: pwd })
    if (r.status === 200) {
      const token = r.body.access_token
      if (r.body.must_change_password) {
        await apiPost(request, '/auth/change-password',
          { old_password: pwd, new_password: ADMIN_PWD2 }, token)
        const r2 = await apiPost(request, '/auth/login',
          { employee_id: 'admin', password: ADMIN_PWD2 })
        return r2.body.access_token
      }
      return token
    }
  }
  throw new Error('超管登录失败')
}

/** 注册页填表 */
async function fillRegister(page, { phone, name, password, inviteCode }) {
  await page.getByPlaceholder('请输入 11 位手机号').fill(phone)
  if (name) await page.getByPlaceholder('真实姓名，方便成绩统计').fill(name)
  await page.getByPlaceholder('至少 8 位').fill(password)
  await page.getByPlaceholder('再输入一次').fill(password)
  if (inviteCode) await page.getByPlaceholder('有邀请码会自动加入该机构').fill(inviteCode)
}

test.describe('收费 / 机构前台流程', () => {
  test('登录页：工号/手机号、注册入口、短信 Tab 占位', async ({ page }) => {
    await page.goto('/#/login')
    await expect(page.getByText('工号 / 手机号')).toBeVisible()
    await expect(page.getByPlaceholder('请输入工号或手机号')).toBeVisible()
    await expect(page.getByText('没有账号？')).toBeVisible()
    // 短信没开通时，验证码登录 Tab 不可用，并给出"即将开放"提示
    await expect(page.getByText('短信验证码登录即将开放', { exact: false })).toBeVisible()
    const smsTab = page.getByRole('tab', { name: '验证码登录' })
    await expect(smsTab).toHaveClass(/is-disabled/)
  })

  test('注册 → 自动登录 → 进我的订阅页', async ({ page }) => {
    const phone = randomPhone()
    await page.goto('/#/register')
    await fillRegister(page, { phone, name: '冒烟学员', password: 'E2ePass12345' })
    await page.getByRole('button', { name: /注册并登录/ }).click()

    await expect(page).toHaveURL(/#\/my-exams/)
    expect(await page.evaluate(() => localStorage.getItem('token'))).toBeTruthy()

    // 订阅页可打开，兑换码输入框正常
    await page.goto('/#/subscribe')
    await expect(page.getByText('我的订阅').first()).toBeVisible()
    const codeInput = page.getByPlaceholder('请输入管理员提供的兑换码')
    await expect(codeInput).toBeVisible()
    await expect(codeInput).toHaveValue('')
  })

  test('兑换码开通 → 机构到期日出现 → 到期后 402 跳订阅页', async ({ page, request }) => {
    const token = await adminToken(request)
    const phone = randomPhone()
    const orgName = 'E2E机构' + Date.now()

    // 打开收费开关并把试用天数设为 0：试用期内本来就放行，
    // 不关掉试用就测不出"机构到期 -> 402"
    const billing = await apiPost(request, '/settings/billing',
      { enabled: true, free_trial_days: 0 }, token)
    expect(billing.status).toBe(200)

    // 1. 建机构 + 生成绑机构兑换码
    let r = await apiPost(request, '/organizations',
      { name: orgName, seat_limit: 5, contact_name: '测试', contact_phone: randomPhone() }, token)
    expect(r.status).toBe(200)
    const orgId = r.body.id
    const inviteCode = r.body.invite_code

    const plans = await apiGet(request, '/billing/admin/plans', token)
    const plan = plans.body.items[0]
    r = await apiPost(request, '/billing/admin/codes/generate',
      { plan_id: plan.id, count: 1, valid_days: 30, organization_id: orgId }, token)
    expect(r.status).toBe(200)
    const code = r.body.codes[0]

    // 2. 用邀请码注册，登录后到订阅页兑换
    await page.goto('/#/register')
    await fillRegister(page, { phone, password: 'E2ePass12345', inviteCode })
    await page.getByRole('button', { name: /注册并登录/ }).click()
    await expect(page).toHaveURL(/#\/my-exams/)

    await page.goto('/#/subscribe')
    await page.getByPlaceholder('请输入管理员提供的兑换码').fill(code)
    await page.getByRole('button', { name: '立即兑换' }).click()
    await expect(page.getByText(/兑换成功/)).toBeVisible()

    // 机构订阅到期日不再是空
    const userToken = await page.evaluate(() => localStorage.getItem('token'))
    const me = await apiGet(request, '/billing/me', userToken)
    expect(me.body.organization.subscription_expires_at).toBeTruthy()

    // 3. 让机构到期（把到期日改到过去），自学接口应该 402
    const expired = await apiPost(request, '/organizations/' + orgId,
      { subscription_expires_at: '2020-01-01' }, token, 'PUT')
    expect(expired.status).toBe(200)

    const status = await page.evaluate(async () => {
      const t = localStorage.getItem('token')
      const res = await fetch('/api/questions/study', { headers: { Authorization: 'Bearer ' + t } })
      return res.status
    })
    expect(status).toBe(402)

    // 4. 前端路由守卫：无权益时自学页跳订阅页
    await page.evaluate(() => localStorage.setItem('entitlementActive', 'false'))
    await page.goto('/#/self-study')
    await expect(page).toHaveURL(/#\/subscribe/)
    // 登录态不清掉，成绩记录仍可查
    expect(await page.evaluate(() => localStorage.getItem('token'))).toBeTruthy()
    const recStatus = await page.evaluate(async () => {
      const t = localStorage.getItem('token')
      const res = await fetch('/api/exam-records/recent', { headers: { Authorization: 'Bearer ' + t } })
      return res.status
    })
    expect(recStatus).toBe(200)
  })

  test('机构管理员：菜单出现"机构学员"，且只能看到本机构', async ({ page, request }) => {
    const token = await adminToken(request)
    const phone = randomPhone()
    const orgName = 'E2E机构B' + Date.now()

    let r = await apiPost(request, '/organizations',
      { name: orgName, seat_limit: 5, contact_name: '测试', contact_phone: randomPhone() }, token)
    const orgId = r.body.id

    // 机构管理员账号（超管建在机构里）
    r = await apiPost(request, `/organizations/${orgId}/members`,
      { phone, name: '机构管理员', password: 'E2ePass12345' }, token)
    expect(r.status).toBe(200)
    const memberId = r.body.id
    const promoted = await apiPost(request, `/organizations/${orgId}/members/${memberId}`,
      { org_role: 'admin' }, token, 'PUT')
    expect(promoted.status).toBe(200)

    // 登录
    await page.goto('/#/login')
    await page.getByPlaceholder('请输入工号或手机号').fill(phone)
    await page.getByPlaceholder('请输入密码').fill('E2ePass12345')
    await page.getByRole('button', { name: '登 录' }).click()
    await expect(page).toHaveURL(/#\/my-exams/)

    // 菜单里有"机构学员"和"学员管理"，但没有"机构管理"/"套餐管理"
    await expect(page.getByRole('menuitem', { name: '机构学员' })).toBeVisible()
    await expect(page.getByRole('menuitem', { name: '学员管理' })).toBeVisible()
    await expect(page.getByRole('menuitem', { name: '机构管理' })).toHaveCount(0)

    // 机构学员页只列本机构的人
    await page.goto('/#/org-members')
    await expect(page.getByText(orgName)).toBeVisible()

    // 越权：看不到别的机构
    const orgToken = await page.evaluate(() => localStorage.getItem('token'))
    const orgs = await apiGet(request, '/organizations', orgToken)
    expect(orgs.body.items.length).toBe(1)
  })
})
