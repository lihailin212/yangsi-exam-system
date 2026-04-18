<template>
  <div class="dashboard">
    <!-- Welcome Section -->
    <div class="welcome-section">
      <div class="welcome-content">
        <h1 class="welcome-title">欢迎回来</h1>
        <p class="welcome-subtitle">今天是学习的好时光，让我们开始吧</p>
      </div>
      <div class="welcome-decoration">
        <div class="decoration-circle circle-1"></div>
        <div class="decoration-circle circle-2"></div>
        <div class="decoration-circle circle-3"></div>
      </div>
    </div>

    <!-- Stats Grid -->
    <el-row :gutter="24" class="stats-grid" v-loading="loading">
      <el-col 
        v-for="(stat, index) in statsData" 
        :key="stat.id"
        :xs="12" :sm="6"
      >
        <div 
          class="stat-card" 
          :class="`stat-${stat.id}`"
          :style="{ animationDelay: `${index * 100}ms` }"
        >
          <div class="stat-bg"></div>
          <div class="stat-content">
            <div class="stat-icon-wrapper">
              <div class="stat-icon" :style="{ background: stat.gradient }">
                <el-icon><component :is="stat.icon" /></el-icon>
              </div>
            </div>
            <div class="stat-info">
              <span class="stat-value" :class="`text-${stat.color}`">{{ stat.value }}</span>
              <span class="stat-label">{{ stat.label }}</span>
              <div class="stat-trend" v-if="stat.trend">
                <el-icon><component :is="stat.trend > 0 ? 'Top' : 'Bottom'" /></el-icon>
                <span>{{ Math.abs(stat.trend) }}%</span>
              </div>
            </div>
          </div>
          <div class="stat-glow" :style="{ background: stat.glow }"></div>
        </div>
      </el-col>
    </el-row>

    <!-- Quick Actions & Recent Activity -->
    <el-row :gutter="24" class="content-grid">
      <!-- Quick Actions -->
      <el-col :xs="24" :lg="14">
        <div class="section-card">
          <div class="section-header">
            <h2 class="section-title">
              <el-icon><Lightning /></el-icon>
              快捷操作
            </h2>
          </div>
          <div class="quick-actions">
            <div 
              v-for="(action, index) in quickActions" 
              :key="action.path"
              class="action-card"
              :style="{ animationDelay: `${(index + 4) * 100}ms` }"
              @click="goTo(action.path)"
            >
              <div class="action-icon" :style="{ background: action.gradient }">
                <el-icon><component :is="action.icon" /></el-icon>
              </div>
              <div class="action-content">
                <h3>{{ action.title }}</h3>
                <p>{{ action.desc }}</p>
              </div>
              <div class="action-arrow">
                <el-icon><ArrowRight /></el-icon>
              </div>
            </div>
          </div>
        </div>
      </el-col>

      <!-- Recent Activity -->
      <el-col :xs="24" :lg="10">
        <div class="section-card activity-card">
          <div class="section-header">
            <h2 class="section-title">
              <el-icon><Clock /></el-icon>
              最近动态
            </h2>
            <el-button type="primary" link>查看全部</el-button>
          </div>
          <div class="activity-list">
            <div 
              v-for="(activity, index) in recentActivity" 
              :key="index"
              class="activity-item"
              :style="{ animationDelay: `${(index + 8) * 100}ms` }"
            >
              <div class="activity-icon" :style="{ background: activity.color }">
                <el-icon><component :is="activity.icon" /></el-icon>
              </div>
              <div class="activity-content">
                <p class="activity-text">{{ activity.text }}</p>
                <span class="activity-time">{{ activity.time }}</span>
              </div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- Chart Section -->
    <el-row :gutter="24" class="chart-grid">
      <el-col :xs="24" :lg="16">
        <div class="section-card chart-card">
          <div class="section-header">
            <h2 class="section-title">
              <el-icon><DataLine /></el-icon>
              考试趋势
            </h2>
            <div class="chart-tabs">
              <button 
                v-for="period in ['本周', '本月', '本年']" 
                :key="period"
                :class="['chart-tab', { active: activePeriod === period }]"
                @click="activePeriod = period"
              >
                {{ period }}
              </button>
            </div>
          </div>
          <div class="chart-placeholder">
            <div class="chart-bars">
              <div class="chart-bar" v-for="(val, index) in chartData" :key="index" :style="{ height: `${val}%` }">
                <span class="bar-tooltip">{{ val }}</span>
              </div>
            </div>
            <div class="chart-labels">
              <span v-for="day in chartLabels" :key="day">{{ day }}</span>
            </div>
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :lg="8">
        <div class="section-card progress-card">
          <div class="section-header">
            <h2 class="section-title">
              <el-icon><Medal /></el-icon>
              学习进度
            </h2>
          </div>
          <div class="progress-list">
            <div 
              v-for="(item, index) in progressData" 
              :key="index"
              class="progress-item"
              :style="{ animationDelay: `${(index + 12) * 100}ms` }"
            >
              <div class="progress-info">
                <span class="progress-label">{{ item.label }}</span>
                <span class="progress-value">{{ item.value }}%</span>
              </div>
              <el-progress 
                :percentage="item.value" 
                :stroke-width="8"
                :color="item.color"
                :show-text="false"
              />
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getStatistics } from '@/api/statistics'
import { 
  User, 
  Edit, 
  Document, 
  TrendCharts, 
  Lightning,
  ArrowRight,
  Clock,
  Top,
  Bottom,
  DataLine,
  Medal,
  Reading
} from '@element-plus/icons-vue'

const router = useRouter()
const loading = ref(false)
const stats = ref(null)
const activePeriod = ref('本周')

const statsData = computed(() => {
  const s = stats.value || {}
  return [
    { 
      id: 'users', 
      label: '总学员数', 
      value: s.total_users ?? 0, 
      icon: 'User', 
      color: 'primary',
      gradient: 'linear-gradient(135deg, #0D7377, #14FFEC)',
      glow: 'rgba(13, 115, 119, 0.3)',
      trend: 12
    },
    { 
      id: 'exams', 
      label: '考试总数', 
      value: s.total_exams ?? 0, 
      icon: 'Edit', 
      color: 'success',
      gradient: 'linear-gradient(135deg, #67C23A, #95d475)',
      glow: 'rgba(103, 194, 58, 0.3)',
      trend: 8
    },
    { 
      id: 'records', 
      label: '答卷总数', 
      value: s.total_records ?? 0, 
      icon: 'Document', 
      color: 'warning',
      gradient: 'linear-gradient(135deg, #E6A23C, #f3d19e)',
      glow: 'rgba(230, 162, 60, 0.3)',
      trend: -3
    },
    { 
      id: 'pass', 
      label: '及格率', 
      value: s.pass_rate ? s.pass_rate + '%' : '0%', 
      icon: 'TrendCharts', 
      color: 'danger',
      gradient: 'linear-gradient(135deg, #F56C6C, #f89898)',
      glow: 'rgba(245, 108, 108, 0.3)',
      trend: 5
    },
  ]
})

const quickActions = [
  { path: '/exams', icon: 'Edit', title: '创建考试', desc: '快速创建考试，支持多种选题方式', gradient: 'linear-gradient(135deg, #0D7377, #14FFEC)' },
  { path: '/questions', icon: 'Reading', title: '题库管理', desc: '批量导入、单/多选/判断题管理', gradient: 'linear-gradient(135deg, #67C23A, #95d475)' },
  { path: '/students', icon: 'User', title: '学员管理', desc: '添加学员，查看学习和考试记录', gradient: 'linear-gradient(135deg, #E6A23C, #f3d19e)' },
]

const recentActivity = [
  { icon: 'Document', text: '张三完成了「医学基础考核」', time: '10分钟前', color: 'rgba(13, 115, 119, 0.15)' },
  { icon: 'Edit', text: '李四开始作答「临床技能测试」', time: '25分钟前', color: 'rgba(230, 162, 60, 0.15)' },
  { icon: 'TrendCharts', text: '王五考试成绩优秀 (92分)', time: '1小时前', color: 'rgba(103, 194, 58, 0.15)' },
  { icon: 'User', text: '新学员赵六加入系统', time: '2小时前', color: 'rgba(20, 255, 236, 0.15)' },
]

const chartData = ref([45, 65, 52, 78, 60, 85, 70])
const chartLabels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

const progressData = [
  { label: '题库完成度', value: 78, color: '#0D7377' },
  { label: '本月考试率', value: 92, color: '#67C23A' },
  { label: '学习时长', value: 65, color: '#E6A23C' },
  { label: '知识点掌握', value: 85, color: '#14FFEC' },
]

const goTo = (path) => router.push(path)

onMounted(async () => {
  loading.value = true
  try {
    stats.value = await getStatistics()
  } catch {
    // 非管理员无权限时忽略
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.dashboard {
  padding: 0;
  animation: fadeIn 0.5s ease-out;
}

/* Welcome Section */
.welcome-section {
  position: relative;
  background: linear-gradient(135deg, #141B22 0%, #0D7377 100%);
  border-radius: var(--radius-lg);
  padding: var(--space-8);
  margin-bottom: var(--space-6);
  overflow: hidden;
}

.welcome-content {
  position: relative;
  z-index: 1;
}

.welcome-title {
  font-family: var(--font-display);
  font-size: 32px;
  font-weight: 700;
  color: #fff;
  margin-bottom: var(--space-2);
  animation: slideUp 0.6s ease-out;
}

.welcome-subtitle {
  font-size: 15px;
  color: rgba(255, 255, 255, 0.7);
  animation: slideUp 0.6s ease-out 0.1s backwards;
}

.welcome-decoration {
  position: absolute;
  right: -50px;
  top: -50px;
  width: 300px;
  height: 300px;
}

.decoration-circle {
  position: absolute;
  border-radius: 50%;
  filter: blur(40px);
}

.circle-1 {
  width: 150px;
  height: 150px;
  background: rgba(20, 255, 236, 0.3);
  top: 0;
  right: 0;
  animation: float 6s ease-in-out infinite;
}

.circle-2 {
  width: 100px;
  height: 100px;
  background: rgba(13, 115, 119, 0.4);
  bottom: 20px;
  right: 100px;
  animation: float 8s ease-in-out infinite reverse;
}

.circle-3 {
  width: 60px;
  height: 60px;
  background: rgba(20, 255, 236, 0.2);
  top: 100px;
  right: 200px;
  animation: float 10s ease-in-out infinite;
}

/* Stats Grid */
.stats-grid {
  margin-bottom: var(--space-6);
}

.stat-card {
  position: relative;
  background: #fff;
  border-radius: var(--radius-md);
  padding: var(--space-5);
  margin-bottom: var(--space-4);
  overflow: hidden;
  cursor: pointer;
  transition: all var(--transition-base);
  animation: slideUp 0.5s ease-out backwards;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
}

.stat-bg {
  position: absolute;
  top: 0;
  right: 0;
  width: 120px;
  height: 120px;
  background: var(--neutral-100);
  border-radius: 0 0 0 100%;
  opacity: 0.5;
}

.stat-content {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.stat-icon-wrapper {
  flex-shrink: 0;
}

.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: #fff;
  box-shadow: var(--shadow-md);
}

.stat-info {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-family: var(--font-number);
  font-size: 28px;
  font-weight: 700;
  display: block;
  line-height: 1.2;
}

.text-primary { color: var(--primary-500); }
.text-success { color: #67C23A; }
.text-warning { color: #E6A23C; }
.text-danger { color: #F56C6C; }

.stat-label {
  font-size: 13px;
  color: var(--neutral-400);
}

.stat-trend {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  color: #67C23A;
  margin-left: var(--space-2);
}

.stat-glow {
  position: absolute;
  bottom: -30px;
  right: -30px;
  width: 100px;
  height: 100px;
  border-radius: 50%;
  filter: blur(40px);
  opacity: 0.5;
}

/* Section Cards */
.section-card {
  background: #fff;
  border-radius: var(--radius-md);
  padding: var(--space-5);
  margin-bottom: var(--space-6);
  animation: slideUp 0.5s ease-out backwards;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-5);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--neutral-100);
}

.section-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  color: var(--neutral-800);
}

.section-title .el-icon {
  color: var(--primary-500);
}

/* Quick Actions */
.quick-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.action-card {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4);
  background: var(--neutral-50);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-base);
  animation: slideUp 0.5s ease-out backwards;
}

.action-card:hover {
  background: var(--neutral-100);
  transform: translateX(8px);
}

.action-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 20px;
  flex-shrink: 0;
}

.action-content {
  flex: 1;
}

.action-content h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--neutral-800);
  margin-bottom: 2px;
}

.action-content p {
  font-size: 12px;
  color: var(--neutral-400);
  margin: 0;
}

.action-arrow {
  color: var(--neutral-300);
  font-size: 18px;
  transition: all var(--transition-fast);
}

.action-card:hover .action-arrow {
  color: var(--primary-500);
  transform: translateX(4px);
}

/* Activity List */
.activity-card {
  height: 100%;
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.activity-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--neutral-50);
  border-radius: var(--radius-sm);
  animation: slideUp 0.5s ease-out backwards;
}

.activity-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-500);
  font-size: 16px;
  flex-shrink: 0;
}

.activity-content {
  flex: 1;
}

.activity-text {
  font-size: 13px;
  color: var(--neutral-700);
  margin: 0 0 4px;
}

.activity-time {
  font-size: 11px;
  color: var(--neutral-400);
}

/* Chart Section */
.chart-card {
  min-height: 320px;
}

.chart-tabs {
  display: flex;
  gap: var(--space-2);
}

.chart-tab {
  padding: var(--space-2) var(--space-4);
  border: none;
  background: var(--neutral-100);
  border-radius: var(--radius-full);
  font-size: 13px;
  color: var(--neutral-500);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.chart-tab:hover {
  color: var(--neutral-700);
}

.chart-tab.active {
  background: var(--primary-500);
  color: #fff;
}

.chart-placeholder {
  padding: var(--space-4) 0;
}

.chart-bars {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  height: 180px;
  padding: 0 var(--space-4);
}

.chart-bar {
  width: 40px;
  background: linear-gradient(180deg, var(--primary-500), var(--accent-500));
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  position: relative;
  transition: all var(--transition-base);
  cursor: pointer;
  min-height: 20px;
}

.chart-bar:hover {
  transform: scaleY(1.05);
  filter: brightness(1.1);
}

.bar-tooltip {
  position: absolute;
  top: -28px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--neutral-800);
  color: #fff;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-family: var(--font-number);
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.chart-bar:hover .bar-tooltip {
  opacity: 1;
}

.chart-labels {
  display: flex;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4) 0;
}

.chart-labels span {
  font-size: 12px;
  color: var(--neutral-400);
  width: 40px;
  text-align: center;
}

/* Progress Card */
.progress-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.progress-item {
  animation: slideUp 0.5s ease-out backwards;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}

.progress-label {
  font-size: 13px;
  color: var(--neutral-600);
}

.progress-value {
  font-family: var(--font-number);
  font-size: 14px;
  font-weight: 600;
  color: var(--neutral-800);
}

.progress-item :deep(.el-progress-bar__outer) {
  background: var(--neutral-100);
  border-radius: var(--radius-full);
}

/* Responsive */
@media (max-width: 768px) {
  .welcome-title {
    font-size: 24px;
  }
  
  .welcome-section {
    padding: var(--space-6);
  }
  
  .stat-card {
    padding: var(--space-4);
  }
  
  .stat-icon {
    width: 44px;
    height: 44px;
    font-size: 20px;
  }
  
  .stat-value {
    font-size: 24px;
  }
  
  .chart-bars {
    height: 140px;
  }
  
  .chart-bar {
    width: 30px;
  }
}
</style>
