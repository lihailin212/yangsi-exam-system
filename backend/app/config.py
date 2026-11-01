import os

# 前端访问地址（用于生成邀请链接，二维码，手机扫描后访问此地址）
# 开发环境：设置为电脑的局域网IP，如 http://192.168.x.x:5173
# 生产环境：设置为实际域名，如 https://exam.example.com
FRONTEND_BASE_URL = os.environ.get(
    "FRONTEND_BASE_URL",
    "https://exam.yangsi-lab.cn"  # Vercel 前端部署地址
)

# 应用版本号。与前端 src/version.js 保持一致，发版时一起改。
APP_VERSION = os.environ.get("APP_VERSION", "V1.1")

# 初始管理员密码。
#
# admin 账号第一次被创建时用它当密码；留空则生成一个随机密码并打印在后端
# 启动日志里（Railway 上看部署日志）。不管密码来自哪里，首次登录后都会被
# 强制要求改一次密码，初始密码随即作废。
ADMIN_INITIAL_PASSWORD = os.environ.get("ADMIN_INITIAL_PASSWORD", "").strip()
