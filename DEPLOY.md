# 杨思学考试系统 - 部署与迁移指南

## 一、已完成的修改

### 1. 手机扫码问题修复
- **路由改为 HashRouter**：`src/router/index.js`
  - URL 格式从 `/exam-login/2` 改为 `/#/exam-login/2`
  - 手机扫码后直接进入考试登录页，无需邀请码

- **前端地址更新**：`backend/app/config.py`
  - `FRONTEND_BASE_URL` 改为 `https://exam.yangsi-lab.cn`
  - 二维码 URL 格式：`https://exam.yangsi-lab.cn/#/exam-login/{exam_id}`

- **后端 URL 推断**：`backend/app/routers/distributions.py`
  - 优先使用 HTTPS
  - 支持 `localhost:8000` 作为开发环境回退

### 2. Railway 配置清理
- `backend/railway.json` 移除了 disk 配置（不再依赖本地文件存储）
- 数据统一迁移到 Supabase

### 3. 数据库迁移脚本
- `supabase_migration.sql` - Supabase SQL 执行脚本（包含完整数据和 schema）
- `migrate_to_supabase.py` - Python 迁移辅助脚本

---

## 二、部署步骤

### 第一步：推送代码到 GitHub（已有仓库会自动触发 Railway 部署）
```bash
cd D:\opencodeli\exam-system-mr
git add -A
git commit -m "fix: use HashRouter for mobile QR code access, update frontend URL"
git push origin master
```

### 第二步：迁移数据到 Supabase

#### 2.1 创建 Supabase 项目（如已有可跳过）
1. 访问 https://supabase.com 注册/登录
2. 点击 "New Project" → 项目名称随意，Region 选择 Asia
3. 在 Settings → Database 获取连接字符串（格式：`postgresql://postgres:<password>@<host>.supabase.co:5432/postgres`）

#### 2.2 执行数据迁移
在 Supabase SQL Editor 中执行 `migrate_to_supabase.sql` 文件的全部内容（包含 schema + 所有数据）。

### 第三步：配置 Railway 环境变量

在 Railway 控制台（https://railway.app）配置后端服务 `stellar-youth-production-1591`：

| 变量名 | 值 |
|--------|-----|
| `DATABASE_URL` | `postgresql://postgres:<password>@<host>.supabase.co:5432/postgres`（Supabase 连接字符串） |
| `FRONTEND_BASE_URL` | `https://exam.yangsi-lab.cn` |

配置后点击 **Redeploy**。

### 第四步：部署前端

前端使用 Railway 部署，已有项目。将 `dist` 文件夹内容推送到 Railway 前端项目：

```bash
cd D:\opencodeli\exam-system-mr\dist
# 使用 Railway CLI 或 Git 部署
railway login
railway init
railway up
```

或通过 Railway 控制台手动部署（将 `dist` 目录打包上传）。

---

## 三、验证功能

部署完成后，用手机扫码测试：

```
二维码内容：
https://exam.yangsi-lab.cn/#/exam-login/2
```

扫码后应显示考试登录页，输入工号和密码即可参加考试。

---

## 四、图片问题说明

题目图片目前存储在 Railway 后端的 `/uploads` 目录。迁移到 Supabase 后：
- **选项 A**：继续使用 Railway 后端的 `/uploads`（保持现状）
- **选项 B**：将 `uploads/images/` 目录上传到 Supabase Storage，修改数据库中的图片 URL

如果图片不显示，检查：
```bash
# 测试图片访问
curl "(Vercel: https://exam.yangsi-lab.cn)/uploads/images/20260412_1c9d88384b5d491292dd9261ecdf116b.jpg"
```

---

## 五、各环境初始密码

管理员工号固定为 dmin。初始密码由后端环境变量 ADMIN_INITIAL_PASSWORD 决定；
没配置时后端启动会随机生成并打印在后端启动日志里。

初始密码只能用一次：首次登录会强制跳转改密页，改完之前其他接口不可用。

### 在 Vercel 上配置

线上环境是 **Vercel**（项目 yangsi-exam-system，地址 https://exam.yangsi-lab.cn），
不是 Railway（旧的 Railway 地址已全部 404）。

在 Vercel 项目的 **Settings → Environment Variables** 里添加：

| 变量名 | 值 | 类型 | 环境 |
|--------|----|----|------|
| ADMIN_INITIAL_PASSWORD | 自己定义的强密码 | Secret | Production / Preview / Development |

`ash
# 以命令行方式配置（项目级，对 frontend 和 backend 两个 service 都生效）
vercel env add ADMIN_INITIAL_PASSWORD --environment "production,preview,development" \
  --value "<你的强密码>" --sensitive --force
`

注意：

- Vercel CLI 目前不支持 **service 级**变量，只能加项目级。前端是 Vite 构建，
  非 VITE_ 前缀的变量不会被打包到浏览器里，安全。
- 改完环境变量后必须**重新部署**才会生效（现有 deployment 不会自动重跑）：
  `ash
  vercel redeploy <deployment-url> --environment production
  `
- 变量只在**创建 admin 账号那一刻**生效。账号已存在时，后端会忽略这个变量（不会重置线上已有密码）。
- 如果账号已存在但密码还是旧的 dmin123，服务启动时会自动把它标记为“必须修改”。

| 环境 | 地址 |
|------|------|
| 生产前端 + 后端 | https://exam.yangsi-lab.cn |
| Neon 数据库 | ep-cold-unit-b82uf79n-pooler.c-14.us-east-1.aws.neon.tech |
| Supabase | https://supabase.com（需登录查看） |
