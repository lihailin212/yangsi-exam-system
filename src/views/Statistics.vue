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
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import * as echarts from 'echarts'
import { getStatistics } from '@/api/statistics'

const loading = ref(false)
const stats = ref(null)
const lineRef = ref(null)
const pieRef = ref(null)

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
  try {
    stats.value = await getStatistics()
    setTimeout(initCharts, 100)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.statistics-page { padding: 20px; }
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
