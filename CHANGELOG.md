# 更新日志

本文件记录每个正式版本的变化。版本号规则：`V主版本.次版本`，
对应 git tag（如 `V1.0`）。

---

## 未发布

### 图片存储迁移：Vercel Blob → Supabase Storage
- **背景**：Vercel Hobby 版 Blob 每月 `Advanced Operations` 上限 2000 次，
  被之前的批量导入 / 清理 / 去水印重传耗尽后，Vercel 直接把这个 store 停掉了
  （上传报 `Store is suspended`，图片地址返回 403 `Your store is blocked`），
  整个题库的图都加载不出来。账号本身没问题（Neon 库正常、无欠费、无风控）。
  Hobby 的 2000 次/月对"每月批量导图"的流程本来就不够用。
- 迁移到 **Supabase Storage**（免费版 1GB 存储 / 5GB 流量，足够本项目）：
  - 项目 `exam-system-mr`（东京区，国内延迟友好），存储桶 `exam-images`（public）；
  - 659 张题库图（643 张在用 + 16 张新增，66MB）全部上传并逐张校验可访问；
  - 题库里 1318 处 blob 地址 + 站点 logo 地址批量换成 Supabase 公网地址，
    替换前已全量备份（`backend/backups/blob2supabase_urls_*.json`），可回滚；
  - `backend/app/storage.py` 新增 Supabase 分支：**新上传的图片直接进 Supabase**，
    以后再也不会碰到 Vercel 的月度配额；
  - `backend/app/main.py` 的 `/uploads` 路由在启用 Supabase 时同样走重定向；
  - 新增 `backend/scripts/upload_images_to_supabase.py`（批量上传）、
    `backend/scripts/migrate_blob_urls_to_supabase.py`（地址迁移，带备份）；
  - 导入 / 去水印 / 题库生成三个脚本改为走统一存储层，不再直接依赖 Vercel SDK。
- 迁移完成后**已删除旧的 Vercel Blob store**（`yangsi-exam-images`，643 个文件）：
  删除前做了三方对账 —— 数据库已无 blob 地址、643 个文件在 Supabase 全部存在、
  本地 `backend/uploads/images/morph/` 也都有备份，确认无独有数据后才删；
  Vercel 侧的 `BLOB_READ_WRITE_TOKEN` 也随之移除（删 store 会自动清掉），
  本地 `.env.local` 同步清掉。代码里保留 Blob 回落分支，随时可以再启用。


### 题库图片去水印
- 新增 `backend/scripts/clean_question_images.py`：自动识别并去除题库图片上的
  文字水印，处理完覆盖上传回 Vercel Blob（图片路径不变，题目里的地址不用改）。
  - 识别并清除**室间质评版权水印**（右下角三行小字）48 张；
  - 识别并清除**「细胞助手」公众号角标** 7 张；
  - 两种水印都用「模板匹配定位 + 细笔画提取 + 图像修复」处理，
    修复后肉眼看不出痕迹，题目里的图片已同步更新。

### 修复
- `get_exam_progress` 里写死了 Postgres 的 `NULL::bigint` / `NULL::text`，
  本地开发用的 SQLite 库会直接报语法错 —— 本地点「编辑考试」「开考」「交卷」
  全是 500，本地根本跑不了完整考试流程。
  改用 SQLAlchemy 的 `cast(null(), ...)`，两种数据库都能跑，结果不变
  （生产库上已与手工统计逐条对账一致）。
- 新增 `backend/scripts/test_sqlite_flow.py`：本地 SQLite 全流程回归测试。

### Vercel Blob 存储清理
- 新增 `backend/scripts/cleanup_unused_blobs.py`：清理 Blob 里"没有任何题目引用"的图片。
  Blob 里除了在用的形态学题库图（643 张 / 64MB），还压着今年 4 月上传的
  547 张历史原图（未压缩，单张 3~7MB，415MB），题目里一张都没引用 ——
  清掉后 Blob 从 479MB/1190 个文件降到 64MB/643 个文件，腾出 87% 空间。
  删除前会逐一比对生产库题目内容，且这些文件本地都有备份。

### 增量导入形态学图片
- 新增 `backend/scripts/import_morphology_images.py`：把 E 盘新增的图片按现有
  题库的规矩补进题库，**不动原有的题和考试**：
  - 扫描图片 → 文件名去掉编号得到规范答案，目录名决定分类；
  - MD5 + dHash 两级查重（和已有题库图片比）；
  - 压缩到最长边 1280，按 `sha1(相对路径)+sha1(文件名)` 命名存本地；
  - 每张图出一道单选题 + 一道填空题，干扰项优先取"形态易混淆"，
    再取同分类、最后跨分类随机；正确答案位置在 A/B/C/D 间均衡发牌；
  - 上传 Vercel Blob，写进生产库，并把新题备份成 JSON。
- 新增 `backend/scripts/rollback_morphology_import.py`：一键回滚某次导入。
- 已导入：E 盘 `新增/血细胞/反应性淋巴细胞 (1~16).jpg` 共 16 张，
  生成 32 道题（16 单选 + 16 填空），血细胞形态学单选 308→324、填空 308→324。

### 抽题规则（可按分类 / 按题型）
- 抽题接口 `POST /api/questions/random` 支持规则式写法
  `{"rules":[{"category":"血细胞","type":"single","count":5}]}`：
  - `category` 支持形态学亚类别短名（**血细胞 / 尿沉渣 / 寄生虫 / 其他体液**）、
    完整分类名（形态学/血细胞形态学）或关键字（形态学）；
  - `type` 支持 **单选题 / 填空题 / 多选题 / 判断题**，留空表示不限题型；
  - 两种维度可以混着写，每条规则独立抽题、抽过的题不重复，题库不够直接报错。
- 老写法 `{"single":5,"multiple":3,...}` 继续可用。
- 管理端「随机抽题」弹窗改成规则表格：可加分类、可加题型、可加数量，
  并提供「按题型」「按亚类别」两组快捷按钮。

### 每人随机卷（题数固定、题目随机）
- 考试新增 **卷面方式** 开关：固定卷面 / 每人随机卷。
- 随机卷模式下，管理员用抽题规则规定每个分类、每个题型各抽多少道；
  每位考生进考试时按同一份规则从题库随机抽题，**每人题目数量相同、题目各不相同**，
  防止考生之间对答案。
- 新增 `exam_papers` 表记录每位考生每一轮抽到的题：
  同一个人刷新页面、重新进入都拿同一份卷子；补考自动换一份新卷子。
- 判分、成绩总分、成绩导出全部按考生本人那份卷子计算；
  考生看不到候选题库，也拿不到答案。
- 新增 `GET /api/exams/{id}/preview-paper`：管理员可先抽一份样卷核对规则。

---

## V1.0（2026-10-24）

首个正式版本基线。把此前散落在本机、未纳入版本管理的全部改动整理入库。

### 后端
- 数据库改用 **Neon PostgreSQL**（`DATABASE_URL` 驱动，未配置时回退本地 SQLite）。
- 新增「擂台赛」模块：`arenas.py` / `arenas_ws.py`（含 WebSocket 实时对战）。
- 新增 `timeutil.py` 统一时间口径（考试时间窗用北京时间，答题计时用 UTC）。
- 新增 `storage.py`：题库图片统一存 Vercel Blob。
- 统计接口补齐真实数据：新增 `/api/statistics/recent-activity`（最近动态）、
  `/api/statistics/trend`（交卷量趋势），`/api/statistics` 增加 `deltas`、`progress`。
- 新增 `/api/version` 版本查询接口。
- 作答会话机制（`exam_attempts`）：服务端计时、超时自动交卷、重考次数限制。

### 前端
- 管理首页改为**真实数据**：最近动态、考试趋势、学习进度、卡片涨跌箭头
  （此前是写死的演示数据）。
- 考试管理列表：首列改为「序号」（连续编号），操作按钮一行排开不再折行。
- 题库管理：
  - 编辑题目弹窗支持**拖动 / 缩放 / 最小化到任务栏 / 最大化**；
  - 长弹窗不再顶出屏幕，标题栏始终可见；
  - 新增**图片预览**（可缩放、平移、适应窗口），列表缩略图与编辑器内图片均可点开；
  - 修复**顶层裸 `<img>` 被 wangEditor 丢弃导致保存后图片丢失**的问题，
    并加了保存兜底确认；
  - 题库查询超时放宽到 60s（境外数据库往返 20~40 秒）。
- 考生答题页（移动端）：题号面板改为**可收起的答题卡**，题干与选项不再被挤掉。
- 修复全局弹窗插件的坐标系错误：拖动时按鼠标**增量**计算，
  窗口不再在按下鼠标时自己飞到屏幕右下角。

### 部署
- 新增局域网一键启动 / 守护 / 自启脚本（`scripts/*.ps1`），前后端分离运行。
- `vercel.json` 改为前后端同项目（Services）部署配置。
- 新增 `DEPLOY.md` 部署与迁移说明。

### 工程
- 首次纳入 git 版本管理，打标签 `V1.0`。
- `.gitignore` 清理：运行时上传目录、密钥文件、临时脚本、工具目录均不再入库。
- 版本号单一来源：`src/version.js`（前端展示）与 `backend/app/config.py`（后端接口）。
