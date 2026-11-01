# 瑞智学考试系统 🎓

> ### ⚠️ 版权声明与使用限制
>
> 本项目为上海杨思医院检验科的**私有商业项目**，版权所有 © 2026 上海杨思医院 检验科。
>
> 仓库在 GitHub 上公开**仅用于展示与协作**，**未向任何人授予**源代码许可：
> 不得复制、下载、克隆、修改、分发、公开发布、商用或再许可本项目的代码及素材。
> GitHub 等托管平台服务条款允许的站内浏览与 Fork，同样不构成对本项目的授权。
>
> 未经项目维护者**事先书面许可**，不得将本项目用于任何商业用途。
> 如需授权使用（试用、集成、二次开发、教学或商业部署），请联系项目维护者取得书面授权。
>
> 完整条款见 [LICENSE](LICENSE)。

一个功能完整的在线医学考试管理系统，采用现代化的前后端分离架构，支持多种题型、在线考试、成绩统计等完整功能。

## ✨ 项目状态：✅ 功能完整，可直接使用

经过全面测试，本项目所有核心功能均已实现并可以正常运行：
- ✅ 前端界面完整，可正常构建和运行
- ✅ 后端API完整，数据库设计合理
- ✅ 身份认证系统完善
- ✅ 在线考试功能完整
- ✅ 数据统计和分析功能

## 🚀 核心功能

### 🔐 用户认证系统
- **登录认证**：支持账号密码登录和扫码登录
- **权限控制**：基于JWT的身份验证和路由保护
- **角色管理**：管理员和普通用户权限区分

### 📚 题库管理
- **多题型支持**：单选题、多选题、判断题
- **富文本编辑**：支持题目内容富文本编辑
- **分类管理**：题目分类和标签管理
- **批量操作**：题目的增删改查和批量导入

### 📝 考试管理
- **考试配置**：考试基本信息、时长、及格分设置
- **题目抽取**：支持随机抽题和固定题目
- **状态控制**：考试发布、暂停、结束等状态管理
- **参考统计**：实时查看参考人数和完成率

### 🎓 在线考试
- **实时计时**：考试倒计时显示，时间到自动提交
- **答题界面**：清晰的题目展示和选项选择
- **进度跟踪**：显示答题进度和已答题目
- **防作弊机制**：答题过程监控

### 📊 数据统计
- **成绩分析**：详细的考试成绩统计分析
- **题目分析**：题目正确率和难度分析
- **用户统计**：用户增长趋势和学习数据
- **可视化图表**：使用ECharts展示数据图表

### 👥 学员管理
- **信息管理**：学员基本信息管理
- **学习记录**：学习进度和考试记录追踪
- **成绩统计**：个人和班级成绩统计分析

### ⚙️ 系统设置
- **基础配置**：系统参数和基本信息设置
- **考试配置**：默认考试参数配置
- **通知设置**：系统通知和提醒配置

## 🛠 技术栈

### 前端技术
- **框架**: Vue 3 (Composition API)
- **UI组件**: Element Plus
- **路由**: Vue Router 4
- **状态管理**: Pinia
- **构建工具**: Vite 5
- **图表库**: ECharts
- **HTTP客户端**: Axios
- **富文本编辑器**: @wangeditor/editor

### 后端技术
- **框架**: FastAPI
- **数据库**: SQLAlchemy + SQLite
- **认证**: JWT (python-jose)
- **密码加密**: passlib[bcrypt]
- **部署**: Uvicorn

## 🚀 快速开始

### 环境要求
- **前端**: Node.js 18+，npm 9+
- **后端**: Python 3.8+，pip

### 安装部署

#### 1. 克隆项目
```bash
git clone <repository-url>
cd exam-system-mr
```

#### 2. 前端安装
```bash
# 安装依赖（使用--legacy-peer-deps解决依赖冲突）
npm install --legacy-peer-deps

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

#### 3. 后端安装
```bash
cd backend

# 安装Python依赖
pip install fastapi uvicorn[standard] sqlalchemy python-jose[cryptography] passlib[bcrypt] python-multipart openpyxl python-docx

# 启动后端服务
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

#### 4. 访问系统
- **前端地址**: http://localhost:5173 (开发) 或 http://localhost:5174 (预览)
- **后端API**: http://127.0.0.1:8000
- **API文档**: http://127.0.0.1:8000/docs

## 🔐 默认账号与初始密码

- **管理员账号**：工号固定为 `admin`，首次启动时自动创建
- **初始密码来源**（二选一）：
  - 环境变量 `ADMIN_INITIAL_PASSWORD` —— 部署时自己指定，推荐
  - 没配这个变量时，后端启动会**随机生成**一个 16 位密码，并打印在**后端启动日志**里（Vercel 上看后端服务的 Runtime Logs）
- 初始密码**只能用一次**：用初始密码登录后会被强制跳转到「修改初始密码」页面，
  在改完之前除改密码接口外的所有接口都返回 403
- 历史遗留的老账号如果还在用写死的 `admin123`，服务重启时会被自动标记为「必须修改」

```bash
# 部署平台（Vercel / Docker 等）的环境变量里配置
ADMIN_INITIAL_PASSWORD=你设定的初始密码
SECRET_KEY=你生成的 JWT 签名密钥
```

改完密码后，初始密码立即失效，密码只以 bcrypt 哈希存在数据库里。

**SECRET_KEY 也必须配。**JWT 签名密钥写死在源码里等于公开签名密钥——任何人拿到源码都能伪造管理员 token。
后端未配置时会退化为每进程随机生成并打警告：多实例部署时各实例密钥不一致，登录态会互相失效。
更换 SECRET_KEY 会让所有已登录用户的 token 立即失效，需要重新登录。

## 📁 项目结构

```
exam-system-mr/
├── src/                    # 前端源代码
│   ├── api/              # API接口封装
│   │   ├── auth.js       # 认证接口
│   │   ├── exams.js      # 考试接口
│   │   ├── questions.js  # 题库接口
│   │   ├── students.js  # 学员接口
│   │   └── statistics.js # 统计接口
│   ├── components/       # 公共组件
│   │   └── Layout.vue    # 主布局组件
│   ├── stores/           # 状态管理
│   │   └── auth.js       # 认证状态
│   ├── views/            # 页面组件
│   │   ├── Dashboard.vue    # 管理首页
│   │   ├── Questions.vue    # 题库管理
│   │   ├── Exams.vue        # 考试管理
│   │   ├── ExamTake.vue     # 在线考试
│   │   ├── ExamResult.vue  # 考试结果
│   │   ├── Statistics.vue   # 数据统计
│   │   ├── Students.vue     # 学员管理
│   │   ├── Settings.vue     # 系统设置
│   │   └── Login.vue        # 登录页面
│   ├── router/           # 路由配置
│   │   └── index.js
│   ├── App.vue           # 根组件
│   └── main.js           # 入口文件
├── backend/               # 后端源代码
│   ├── app/
│   │   ├── routers/       # API路由
│   │   │   ├── auth.py     # 认证路由
│   │   │   ├── exams.py    # 考试路由
│   │   │   ├── questions.py # 题库路由
│   │   │   ├── students.py # 学员路由
│   │   │   └── statistics.py # 统计路由
│   │   ├── models.py      # 数据库模型
│   │   ├── schemas.py     # Pydantic模型
│   │   ├── crud.py        # 数据库操作
│   │   ├── auth.py        # 认证模块
│   │   ├── database.py    # 数据库连接
│   │   └── main.py        # FastAPI应用入口
│   ├── exam.db           # SQLite数据库文件
│   └── requirements.txt  # Python依赖
├── dist/                  # 构建输出目录
├── public/                # 静态资源
├── index.html            # 入口HTML文件
├── package.json          # 前端依赖配置
├── vite.config.js        # Vite配置
└── README.md            # 项目说明
```

## 🔧 API接口概览

### 认证接口
```
POST /api/auth/login     # 用户登录
```

### 考试接口
```
GET    /api/exams         # 获取考试列表
POST   /api/exams         # 创建考试
GET    /api/exams/{id}    # 获取考试详情
PUT    /api/exams/{id}    # 更新考试
DELETE /api/exams/{id}    # 删除考试
POST   /api/exams/{id}/submit  # 提交考试答案
GET    /api/exam-records  # 获取考试记录
```

### 题库接口
```
GET    /api/questions     # 获取题目列表
POST   /api/questions     # 创建题目
GET    /api/questions/{id}    # 获取题目详情
PUT    /api/questions/{id}    # 更新题目
DELETE /api/questions/{id}   # 删除题目
```

### 学员接口
```
GET    /api/students      # 获取学员列表
POST   /api/students      # 创建学员
PUT    /api/students/{id} # 更新学员信息
DELETE /api/students/{id}# 删除学员
```

### 统计接口
```
GET /api/statistics/overview  # 统计总览
GET /api/statistics/exam/{id} # 考试统计详情
```

## 🎨 界面预览

### 登录页面
- 现代化设计，支持账号登录和扫码登录
- 响应式布局，适配桌面和移动设备

### 管理后台
- 清晰的侧边栏导航
- 数据统计卡片展示
- 快捷操作入口

### 考试界面
- 实时倒计时显示
- 清晰的题目和选项布局
- 答题进度指示器

## 🔒 安全特性

- **JWT Token身份验证**：安全的用户身份验证机制
- **密码加密存储**：使用bcrypt算法加密用户密码
- **路由权限控制**：前端路由守卫保护
- **API访问限制**：后端中间件权限验证
- **XSS防护**：输入输出过滤
- **SQL注入防护**：使用ORM避免SQL注入

## 🚀 生产部署

### 前端部署
```bash
# 构建生产版本
npm run build

# 将dist/目录部署到Web服务器（Nginx/Apache等）
```

### 后端部署
```bash
# 使用Gunicorn + Uvicorn部署
pip install gunicorn

gunicorn -k uvicorn.workers.UvicornWorker app.main:app -b 0.0.0.0:8000
```

### Docker部署（推荐）
```dockerfile
# 前端Dockerfile
FROM nginx:alpine
COPY dist/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/nginx.conf

# 后端Dockerfile  
FROM python:3.9
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 📈 性能优化

- **前端优化**：代码分割、懒加载、静态资源压缩
- **后端优化**：数据库查询优化、连接池管理
- **缓存机制**：JWT Token缓存、静态资源缓存
- **Gzip压缩**：传输数据压缩

## 🐛 常见问题

### Q: 前端安装依赖失败
A: 使用 `npm install --legacy-peer-deps` 解决依赖冲突问题

### Q: 后端启动失败
A: 检查Python依赖是否安装完整，端口8000是否被占用

### Q: 数据库连接问题
A: 确保应用对exam.db文件有读写权限

### Q: 跨域问题
A: 后端已配置CORS，允许所有来源访问（生产环境建议限制来源）

## 📊 测试结果

✅ **前端构建**: 成功构建，生成生产包
✅ **后端服务**: 成功启动，API接口正常
✅ **用户登录**: JWT认证正常，Token生成有效
✅ **数据库**: SQLite数据库正常，表结构完整
✅ **路由保护**: 前端路由守卫正常工作
✅ **API接口**: 所有核心API接口测试通过

## 🎯 后续扩展建议

1. **移动端适配**：开发专门的移动端应用
2. **实时监控**：添加考试过程实时监控功能
3. **AI辅助**：集成AI进行智能组卷和评分
4. **离线支持**：添加PWA支持，实现离线考试
5. **多租户**：支持多机构多租户管理

## 📄 许可证

本项目为**私有商业项目，未开放源代码许可**，保留所有权利。

- 仓库公开仅用于展示与协作，**不授予**任何人复制、修改、分发、商用或再许可本代码的权利
- 使用本项目代码即表示同意上述条款；未经书面授权不得用于商业用途
- 如需授权使用（试用、集成、二次开发），请联系项目维护者

详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献指南

欢迎提交Issue和Pull Request来改进这个项目！

## 📞 支持

如有问题或建议，请提交Issue。

---

**瑞智学考试系统** - 专业的在线医学考试解决方案 🎓
