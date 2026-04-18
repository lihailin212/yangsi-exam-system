import os

# 前端访问地址（用于生成邀请链接，二维码，手机扫描后访问此地址）
# 开发环境：设置为电脑的局域网IP，如 http://192.168.x.x:5173
# 生产环境：设置为实际域名，如 https://exam.example.com
FRONTEND_BASE_URL = os.environ.get(
    "FRONTEND_BASE_URL",
    "https://yangsi-exam.vercel.app"  # 部署后填入实际 Vercel 域名
)
