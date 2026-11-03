// -*- coding: utf-8 -*-
/**
 * Playwright 配置：自动拉起后端（临时 SQLite）和前端 dev server。
 *
 * 后端用的是 .e2e-data 目录下的独立 SQLite 库，不碰线上 Neon，
 * 也不碰本地的 backend/exam.db。跑完 playwright 会自己关掉这两个进程。
 */
const { defineConfig } = require('@playwright/test')
const path = require('path')

const E2E_DATA = path.join(__dirname, '.e2e-data')

module.exports = defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    headless: true,
    locale: 'zh-CN',
    // 用机器上已装的 Chrome，不用额外下载 Playwright 自带的 chromium。
    // 想跑自带版本就删掉这一行，执行 npx playwright install chromium。
    channel: 'chrome',
  },
  webServer: [
    {
      command: 'python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning',
      cwd: './backend',
      env: {
        // 空的 DATABASE_URL -> 走 SQLite 分支
        DATABASE_URL: '',
        RAILWAY_VOLUME_MOUNT_PATH: E2E_DATA,
        SECRET_KEY: 'e2e-smoke-secret-key-not-for-production',
        ADMIN_INITIAL_PASSWORD: 'AdminE2E123',
      },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npm run dev -- --port 5173 --host 127.0.0.1',
      cwd: '.',
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
