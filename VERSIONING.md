# 版本控制说明

## 仓库信息

- 远程仓库：`https://github.com/lihailin212/yangsi-exam-system`
- 当前版本：**V1.0**（tag `V1.0`）
- 主分支：`master`

## 版本号从哪看

| 位置 | 内容 |
|---|---|
| `src/version.js` | 前端版本号常量（侧边栏底部会显示"版本 V1.0"） |
| `backend/app/config.py` | 后端 `APP_VERSION`，可用环境变量覆盖 |
| `GET /api/version` | 查当前运行的是哪一版 |
| `CHANGELOG.md` | 每个版本改了什么 |

## 发一个新版本的流程

```bash
# 1. 改版本号
#    src/version.js 里的 APP_VERSION 改成 V1.1
#    backend/app/config.py 里的 APP_VERSION 改成 V1.1

# 2. 写更新日志（CHANGELOG.md 顶部加一节）

# 3. 提交
git add -A
git commit -m "release: V1.1"

# 4. 打标签（带说明）
git tag -a V1.1 -m "V1.1 更新说明"

# 5. 推代码和标签
git push origin master
git push origin V1.1
```

查看历史版本：

```bash
git tag                 # 所有版本
git log --oneline V1.0  # V1.0 之后的提交
git show V1.0           # V1.0 这个版本的内容
git diff V1.0 V1.1      # 两个版本之间的差异
```

回退到某个版本（本地先留一份分支，避免丢改动）：

```bash
git switch -c fix/back-to-v1.0 V1.0
```

## 哪些文件不进版本库

`.gitignore` 里排除了这些东西，不要手动 `git add -f`：

- `.env.local` / `.env.production`：**数据库密码、Vercel Blob Token 等密钥**，绝对不能入库
- `uploads/`、`backend/uploads/`：运行时上传的图片（题库图片已放 Vercel Blob）
- `logs/`、`dist/`、`node_modules/`：日志、构建产物、依赖
- `_*.py`、`_*.json` 等临时脚本和调试产物
- `.agents/`、`.claude/skills/`、`.codebuddy/`、`.tools/`、`.playwright-cli/`：工具目录

## 安全提醒

`.env.local` 里存着 Neon 数据库密码和 Vercel Blob Token，
`git remote` 的地址里曾经带过 GitHub Personal Access Token。
**Token 泄露过就应该去 GitHub / Neon / Vercel 后台重新生成一个**，
并把远程地址改成不带 Token 的形式（凭据交给 Git Credential Manager 保管）：

```bash
git remote set-url origin https://github.com/lihailin212/yangsi-exam-system.git
```
