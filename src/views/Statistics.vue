<template>
  <div class="statistics-page">
    <div class="page-header"><h2>数据统计</h2></div>

    <!-- 汇总卡片 -->
    <el-row :gutter="16" class="summary-row" v-loading="loading">
      <el-col :xs="12" :sm="6" v-for="item in summaryCards" :key="item.label">
        <el-card class="summary-card">
          <div class="summary-icon" :style="{ background: item.color }">
            <el-icon><component :is="item.icon" /></el-icon>
          </div>
          <div class="summary-info">
            <div class="summary-value">{{ item.value }}</div>
            <div class="summary-label">{{ item.label }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-alert
      v-if="error"
      type="error"
      show-icon
      :closable="false"
      style="margin-bottom:16px"
      title="统计数据加载失败"
      :description="error + '（下面显示的是 0，不是真实数据；请检查后端是否在运行后刷新）'"
    />

    <!-- 图表区 -->
    <el-row :gutter="16" style="margin-top:16px">
      <el-col :xs="24" :sm="14">
        <el-card>
          <template #header>近7天考试趋势</template>
          <div ref="lineRef" style="height:280px"></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="10">
        <el-card>
          <template #header>成绩分布</template>
          <div ref="pieRef" style="height:280px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 考生答题情况 -->
    <el-card style="margin-top:16px">
      <template #header>
        <div class="records-header">
          <span>考生答题情况</span>
          <div class="records-actions">
            <el-input
              v-model="keyword"
              placeholder="搜索姓名 / 工号 / 考试"
              clearable
              style="width:240px"
              @change="loadRecords"
            />
            <el-button @click="loadRecords">查询</el-button>
            <el-button @click="exportCsv" :disabled="!records.length">导出 CSV</el-button>
          </div>
        </div>
      </template>

      <el-table :data="pagedRecords" v-loading="recordsLoading" style="width:100%" stripe>
        <el-table-column prop="submitted_at" label="提交时间" width="160">
          <template #default="{ row }">{{ formatTime(row.submitted_at) }}</template>
        </el-table-column>
        <el-table-column prop="name" label="姓名" width="100" />
        <el-table-column prop="employee_id" label="工号" width="90" />
        <el-table-column prop="exam_title" label="考试" min-width="200" show-overflow-tooltip />
        <el-table-column label="成绩" width="120">
          <template #default="{ row }">
            <span :class="row.passed ? 'score-pass' : 'score-fail'">
              {{ row.score }} / {{ row.total_score }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="得分率" width="90">
          <template #default="{ row }">{{ row.percent }}%</template>
        </el-table-column>
        <el-table-column label="用时" width="100">
          <template #default="{ row }">{{ formatUsed(row.used_seconds) }}</template>
        </el-table-column>
        <el-table-column prop="attempt_no" label="答题次数" width="90" align="center" />
        <el-table-column label="结果" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.passed ? 'success' : 'danger'" size="small">
              {{ row.passed ? '及格' : '不及格' }}
            </el-tag>
          </template>
        </el-table-column>
        <template #empty>
          <span v-if="recordsError">{{ recordsError }}</span>
          <span v-else>还没有考生交卷记录</span>
        </template>
      </el-table>

      <el-pagination
        v-if="records.length > pageSize"
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="records.length"
        layout="total, prev, pager, next"
        style="margin-top:12px;justify-content:flex-end"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { getStatistics, getStatisticsRecords } from '@/api/statistics'

const loading = ref(false)
const stats = ref(null)
const error = ref('')
const lineRef = ref(null)
const pieRef = ref(null)

const records = ref([])
const recordsLoading = ref(false)
const recordsError = ref('')
const keyword = ref('')
const currentPage = ref(1)
const pageSize = 20
const pagedRecords = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return records.value.slice(start, start + pageSize)
})

// 后端存的是 UTC，浏览器这边统一按本地时区显示
const formatTime = (iso) => {
  if (!iso) return '-'
  const d = new Date(iso)
  if (isNaN(d)) return String(iso)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

const formatUsed = (seconds) => {
  if (seconds === null || seconds === undefined) return '—'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (m < 60) return `${m}分${String(s).padStart(2, '0')}秒`
  return `${Math.floor(m / 60)}小时${String(m % 60).padStart(2, '0')}分`
}

const loadRecords = async () => {
  recordsLoading.value = true
  recordsError.value = ''
  try {
    records.value = await getStatisticsRecords({ keyword: keyword.value || undefined })
    currentPage.value = 1
  } catch (e) {
    records.value = []
    recordsError.value = '答题记录加载失败：' + (e?.response?.data?.detail || e?.message || '未知错误')
  } finally {
    recordsLoading.value = false
  }
}

const exportCsv = () => {
  const header = ['提交时间', '姓名', '工号', '考试', '成绩', '满分', '得分率(%)', '用时', '答题次数', '结果']
  const lines = records.value.map((r) => [
    formatTime(r.submitted_at),
    r.name,
    r.employee_id,
    r.exam_title,
    r.score,
    r.total_score,
    r.percent,
    formatUsed(r.used_seconds),
    r.attempt_no,
    r.passed ? '及格' : '不及格',
  ])
  const csv = '\ufeff' + [header, ...lines]
    .map((row) => row.map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`).join(','))
    .join('\r\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = `考生成绩明细_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success(`已导出 ${records.value.length} 条记录`)
}

const summaryCards = computed(() => {
  const s = stats.value || {}
  return [
    { label: '总学员数', value: s.total_users ?? 0, icon: 'User', color: '#409EFF' },
    { label: '考试总数', value: s.total_exams ?? 0, icon: 'Edit', color: '#67C23A' },
    { label: '答卷总数', value: s.total_records ?? 0, icon: 'Document', color: '#E6A23C' },
    { label: '平均得分', value: s.avg_score ? s.avg_score + '分' : '0分', icon: 'TrendCharts', color: '#F56C6C' },
  ]
})

const initCharts = () => {
  if (!stats.value) return
  const { trend, score_dist } = stats.value

  // 折线图
  const lineChart = echarts.init(lineRef.value)
  lineChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 20, bottom: 40 },
    xAxis: {
      type: 'category',
      data: trend.map(t => t.date.slice(5)),
      axisLabel: { fontSize: 11 },
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      name: '答卷数',
      type: 'line',
      smooth: true,
      data: trend.map(t => t.count),
      areaStyle: { color: 'rgba(64,158,255,0.15)' },
      lineStyle: { color: '#409EFF' },
      itemStyle: { color: '#409EFF' },
    }]
  })

  // 饼图
  const pieChart = echarts.init(pieRef.value)
  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}人 ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie',
      radius: ['35%', '65%'],
      center: ['50%', '45%'],
      data: [
        { value: score_dist['90-100'], name: '90~100分', itemStyle: { color: '#67C23A' } },
        { value: score_dist['80-89'], name: '80~89分', itemStyle: { color: '#409EFF' } },
        { value: score_dist['70-79'], name: '70~79分', itemStyle: { color: '#E6A23C' } },
        { value: score_dist['60-69'], name: '60~69分', itemStyle: { color: '#909399' } },
        { value: score_dist['below60'], name: '60分以下', itemStyle: { color: '#F56C6C' } },
      ].filter(d => d.value > 0),
      label: { fontSize: 12 },
    }]
  })

  window.addEventListener('resize', () => {
    lineChart.resize()
    pieChart.resize()
  })
}

onMounted(async () => {
  loading.value = true
  error.value = ''
  // 汇总和明细一起拉：两个接口都在境外，任一失败都要说清楚，
  // 不能再让页面安安静静显示一排 0，让人以为真的没数据。
  const [s] = await Promise.allSettled([getStatistics(), loadRecords()])
  if (s.status === 'fulfilled') {
    stats.value = s.value
    setTimeout(initCharts, 100)
  } else {
    const e = s.reason
    error.value = e?.response?.data?.detail || e?.message || '请求失败'
  }
  loading.value = false
})
</script>

<style scoped>
.statistics-page { padding: 20px; }
.records-header {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
}
.records-actions { display: flex; align-items: center; gap: 8px; }
.score-pass { color: #67c23a; font-weight: 600; }
.score-fail { color: #f56c6c; font-weight: 600; }
.page-header { margin-bottom: 16px; }
.page-header h2 { font-size: 18px; font-weight: 500; }
.summary-row { margin-bottom: 8px; }

.summary-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
}

.summary-icon {
  width: 52px;
  height: 52px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  color: #fff;
  flex-shrink: 0;
}

.summary-value { font-size: 26px; font-weight: bold; color: #303133; }
.summary-label { font-size: 13px; color: #909399; margin-top: 2px; }

@media (max-width: 576px) {
  .summary-card :deep(.el-card__body) { padding: 14px; gap: 10px; }
  .summary-icon { width: 40px; height: 40px; font-size: 20px; }
  .summary-value { font-size: 20px; }
}
</style>
