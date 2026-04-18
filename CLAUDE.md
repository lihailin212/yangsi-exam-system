# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

瑞智学考试系统是一个功能完整的在线医学考试管理系统，采用前后端分离架构。前端使用 Vue 3 + Element Plus，后端使用 FastAPI + SQLAlchemy + SQLite。

## Development Commands

### Frontend (Vue 3 + Vite)
```bash
# Install dependencies (use --legacy-peer-deps for dependency conflicts)
npm install --legacy-peer-deps

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Backend (FastAPI)
```bash
# Navigate to backend directory
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Start development server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Or with auto-reload for development
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Default Admin Account
- Employee ID: `admin`
- Password: `admin123`
- Created automatically on first startup

## Architecture

### Frontend Structure
- **Framework**: Vue 3 (Composition API) with Vite 5
- **UI Library**: Element Plus components
- **State Management**: Pinia stores
- **Routing**: Vue Router 4 with hash history
- **HTTP Client**: Axios with request/response interceptors
- **Key Directories**:
  - `src/api/` - API service wrappers
  - `src/components/` - Reusable components
  - `src/views/` - Page components
  - `src/stores/` - Pinia state stores
  - `src/router/` - Route configuration

### Backend Structure
- **Framework**: FastAPI with SQLAlchemy ORM
- **Database**: SQLite (exam.db)
- **Authentication**: JWT with python-jose
- **Password Hashing**: bcrypt via passlib
- **Key Directories**:
  - `backend/app/routers/` - API endpoint modules
  - `backend/app/models.py` - SQLAlchemy models
  - `backend/app/schemas.py` - Pydantic schemas
  - `backend/app/crud.py` - Database operations
  - `backend/app/auth.py` - Authentication logic

### Database Models
- **User**: `users` table - system users (admin/student)
- **Exam**: `exams` table - exam definitions
- **Question**: `questions` table - question bank items
- **ExamRecord**: `exam_records` table - exam submissions and scores
- **exam_question**: Many-to-many relationship table

### API Routes
- `/api/auth/*` - Authentication endpoints
- `/api/exams/*` - Exam management
- `/api/questions/*` - Question bank management
- `/api/students/*` - Student/user management
- `/api/statistics/*` - Data analytics

### Development Configuration

#### Frontend Proxy
Vite is configured to proxy API requests:
```javascript
// vite.config.js
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    }
  }
}
```

#### CORS Configuration
Backend allows all origins in development:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### Authentication Flow
1. Login returns JWT token stored in localStorage
2. Frontend adds `Authorization: Bearer <token>` header to requests
3. Backend validates token via dependency injection
4. Routes with `requiresAuth: true` are protected

## Common Development Tasks

### Adding a New API Endpoint
1. Create Pydantic schemas in `schemas.py`
2. Add CRUD operations in `crud.py`
3. Create route module in `routers/` directory
4. Import and include router in `main.py`
5. Add corresponding API service in `src/api/`

### Adding a New Frontend Page
1. Create Vue component in `src/views/`
2. Add route in `src/router/index.js`
3. Create API service in `src/api/` if needed
4. Add to navigation menu in `Layout.vue`

### Database Migrations
Since SQLite is used, schema changes require:
1. Update models in `models.py`
2. Restart backend (tables auto-created)
3. For production, consider manual migration scripts

## Project Layout
```
exam-system-mr/
├── frontend/              # Vue 3 frontend
│   ├── src/
│   │   ├── api/          # API service modules
│   │   ├── components/   # Reusable components
│   │   ├── views/        # Page components
│   │   ├── stores/       # Pinia state stores
│   │   └── router/       # Vue Router configuration
│   ├── vite.config.js    # Vite configuration
│   └── package.json
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── routers/      # API route modules
│   │   ├── models.py     # SQLAlchemy models
│   │   ├── schemas.py    # Pydantic schemas
│   │   ├── crud.py       # Database operations
│   │   ├── auth.py       # Authentication
│   │   └── main.py       # FastAPI application
│   ├── exam.db          # SQLite database
│   └── requirements.txt
└── README.md            # Project documentation
```

## Notes for Claude Code
- 删除数据库前，请先备份数据库
- The system is fully functional and ready for production use
- All core features have been tested and verified
- Frontend and backend must run simultaneously for full functionality
- Default admin account is auto-created on first backend startup
- API documentation available at http://localhost:8000/docs when backend is running
- Frontend development server runs on http://localhost:5173 (or 5174 if occupied)
- Backend runs on http://127.0.0.1:8000