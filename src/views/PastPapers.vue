<template>
  <div class="past-papers-page">
    <div class="page-header">
      <div>
        <h2>历年真题</h2>
        <p class="page-sub">按年份和分卷练习，做完可看答案解析，可反复重做。</p>
      </div>
      <el-button :loading="loading" @click="loadData">刷新</el-button>
    </div>

    <el-alert
      v-if="!loading && !years.length"
      title="暂无历年真题"
      type="info"
      :closable="false"
      show-icon
    />

    <div v-for="group in years" :key="group.year" class="year-block">
      <div class="year-head">
        <span class="year-title">{{ group.year }} 年</span>
        <span class="year-sub">临床医学检验技术（初级）</span>
      </div>
      <el-row :gutter="14">
        <el-col v-for="p in group.papers" :key="p.exam_id" :xs="24" :sm="12" :md="6">
          <el-card class="paper-card" shadow="hover" @click="goPaper(p)">
            <div class="paper-name">{{ p.paper_name }}</div>
            <div class="paper-meta">
              <span>{{ p.question_count }} 题</span>
              <span>{{ p.duration }} 分钟</span>
              <span>满分 {{ p.total_score }}</span>
            </div>
            <div class="paper-foot">
              <el-tag v-if="p.done" type="success" size="small">
                已完成 {{ p.best_score }} 分
              </el-tag>
              <el-tag v-else-if="p.attempts" type="warning" size="small">
                做过 {{ p.attempts }} 次
              </el-tag>
              <el-tag v-else type="info" size="small">未开始</el-tag>
              <el-button type="primary" size="small" plain>去做</el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getPastPapers } from '@/api/pastPapers'

const router = useRouter()
const loading = ref(false)
const years = ref([])

const loadData = async () => {
  loading.value = true
  try {
    const res = await getPastPapers()
    years.value = res.years || []
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

const goPaper = (p) => {
  router.push({ path: `/exam-take/${p.exam_id}` })
}

onMounted(loadData)
</script>

<style scoped>
.past-papers-page { padding: 20px; }
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 18px;
}
.page-header h2 { font-size: 18px; font-weight: 500; margin: 0 0 6px; }
.page-sub { margin: 0; font-size: 13px; color: var(--neutral-500, #909399); }

.year-block { margin-bottom: 22px; }
.year-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--neutral-200, #e4e7ed);
}
.year-title { font-size: 16px; font-weight: 600; color: var(--neutral-800, #303133); }
.year-sub { font-size: 12px; color: var(--neutral-400, #c0c4cc); }

.paper-card { cursor: pointer; margin-bottom: 14px; }
.paper-name { font-size: 15px; font-weight: 600; margin-bottom: 10px; }
.paper-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--neutral-500, #909399);
  margin-bottom: 12px;
}
.paper-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
