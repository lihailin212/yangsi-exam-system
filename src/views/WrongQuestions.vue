<template>
  <div class="wrong-page">
    <div class="page-header">
      <div>
        <h2>我的错题本</h2>
        <p class="page-sub">考试做错的题会自动记在这里，可以针对错题生成练习卷，也可以导出。</p>
      </div>
      <div class="header-actions">
        <el-button :loading="exporting" @click="handleExport">
          <el-icon><Download /></el-icon>导出错题记录
        </el-button>
        <el-button type="primary" :loading="generating" @click="generateVisible = true">
          <el-icon><Tickets /></el-icon>生成错题练习卷
        </el-button>
      </div>
    </div>

    <!-- 汇总 -->
    <div class="stat-row">
      <div class="stat-card">
        <div class="stat-value">{{ stats.wrong_total || 0 }}</div>
        <div class="stat-label">待复习错题</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.mastered_total || 0 }}</div>
        <div class="stat-label">已掌握</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.all_total || 0 }}</div>
        <div class="stat-label">记录总数</div>
      </div>
    </div>

    <!-- 筛选 -->
    <el-card shadow="never" class="filter-card">
      <div class="filter-row">
        <el-radio-group v-model="status" size="small" @change="loadData">
          <el-radio-button label="wrong">待复习</el-radio-button>
          <el-radio-button label="mastered">已掌握</el-radio-button>
          <el-radio-button label="">全部</el-radio-button>
        </el-radio-group>
        <el-select v-model="qType" placeholder="全部题型" clearable size="small" style="width:130px" @change="loadData">
          <el-option label="单选题" value="single" />
          <el-option label="多选题" value="multiple" />
          <el-option label="判断题" value="judgment" />
          <el-option label="填空题" value="fill" />
        </el-select>
        <el-input v-model="keyword" placeholder="搜索题干" clearable size="small" style="width:220px" @keyup.enter="loadData" @clear="loadData" />
        <el-button size="small" @click="loadData">查询</el-button>
      </div>
    </el-card>

    <!-- 列表 -->
    <el-card shadow="never">
      <el-table :data="items" v-loading="loading" style="width:100%" empty-text="还没有错题记录">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="detail-box">
              <div class="detail-q" v-html="row.content"></div>
              <div class="detail-line">
                <span class="detail-label">正确答案：</span>
                <span class="detail-answer">{{ row.answer || '（无）' }}</span>
              </div>
              <div class="detail-line">
                <span class="detail-label">我的错答：</span>
                <span class="detail-answer wrong">{{ row.wrong_answer || '（未作答）' }}</span>
              </div>
              <div v-if="row.analysis" class="detail-line">
                <span class="detail-label">解析：</span>
                <span>{{ row.analysis }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="题型" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="typeTag[row.type]?.type">{{ typeTag[row.type]?.label || row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="题干" min-width="280">
          <template #default="{ row }">
            <span class="content-preview" v-html="row.content"></span>
          </template>
        </el-table-column>
        <el-table-column label="分类" width="130" prop="category" />
        <el-table-column label="错次" width="70" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="danger">{{ row.wrong_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="来源考试" width="200">
          <template #default="{ row }">{{ row.exam_title || '—' }}</template>
        </el-table-column>
        <el-table-column label="最近错题时间" width="150">
          <template #default="{ row }">{{ formatTime(row.last_wrong_at) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'mastered' ? 'success' : 'warning'">
              {{ row.status === 'mastered' ? '已掌握' : '待复习' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ row }">
            <el-button link type="danger" @click="removeRow(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadData"
          @size-change="loadData"
        />
      </div>
    </el-card>

    <!-- 生成练习卷 -->
    <el-dialog v-model="generateVisible" title="生成错题练习卷" width="440px">
      <el-form label-width="90px">
        <el-form-item label="题目范围">
          <el-select v-model="genForm.status" style="width:100%">
            <el-option label="待复习的错题" value="wrong" />
            <el-option label="已掌握的题（再巩固一遍）" value="mastered" />
            <el-option label="全部错题记录" value="" />
          </el-select>
        </el-form-item>
        <el-form-item label="题型">
          <el-select v-model="genForm.q_type" clearable placeholder="不限" style="width:100%">
            <el-option label="单选题" value="single" />
            <el-option label="多选题" value="multiple" />
            <el-option label="判断题" value="judgment" />
            <el-option label="填空题" value="fill" />
          </el-select>
        </el-form-item>
        <el-form-item label="题目数量">
          <el-input-number v-model="genForm.limit" :min="1" :max="200" style="width:100%" />
        </el-form-item>
      </el-form>
      <el-alert type="info" :closable="false"
        title="生成的练习卷只有您自己能做，做对了的题会自动从错题本里标记为已掌握。" />
      <template #footer>
        <el-button @click="generateVisible = false">取消</el-button>
        <el-button type="primary" :loading="generating" @click="handleGenerate">生成并开始</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getWrongQuestions, getWrongQuestionStats, deleteWrongQuestion,
  generateExamFromWrong, exportWrongQuestions,
} from '@/api/wrongQuestions'

const router = useRouter()
const loading = ref(false)
const exporting = ref(false)
const generating = ref(false)
const generateVisible = ref(false)
const items = ref([])
const total = ref(0)
const stats = ref({})
const currentPage = ref(1)
const pageSize = ref(20)
const status = ref('wrong')
const qType = ref('')
const keyword = ref('')

const genForm = reactive({ status: 'wrong', q_type: '', limit: 50 })

const typeTag = {
  single: { label: '单选题', type: '' },
  multiple: { label: '多选题', type: 'warning' },
  judgment: { label: '判断题', type: 'success' },
  fill: { label: '填空题', type: 'info' },
}

const formatTime = (dt) => {
  if (!dt) return '—'
  const [d, t] = String(dt).split('T')
  const [y, m, day] = d.split('-')
  const [hh, mm] = (t || '').split(':')
  return `${y}-${m}-${day} ${hh}:${mm}`
}

const loadData = async () => {
  loading.value = true
  try {
    const params = {
      status: status.value,
      q_type: qType.value,
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
    }
    const res = await getWrongQuestions(params)
    let list = res.items || []
    if (keyword.value) {
      const kw = keyword.value.trim()
      list = list.filter(it => (it.content || '').includes(kw))
    }
    items.value = list
    total.value = res.total || 0
    stats.value = await getWrongQuestionStats()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

const removeRow = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定删除这道错题记录吗？（题号 ${row.question_id}）`, '删除错题', {
        type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
      })
    await deleteWrongQuestion(row.id)
    ElMessage.success('已删除')
    loadData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const handleGenerate = async () => {
  generating.value = true
  try {
    const res = await generateExamFromWrong({
      status: genForm.status,
      q_type: genForm.q_type,
      limit: genForm.limit,
    })
    generateVisible.value = false
    ElMessage.success(`已生成练习卷，共 ${res.question_count} 题`)
    router.push({ path: `/exam-take/${res.exam_id}` })
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '生成失败')
  } finally {
    generating.value = false
  }
}

const handleExport = async () => {
  exporting.value = true
  try {
    await exportWrongQuestions({ status: status.value, q_type: qType.value })
    ElMessage.success('已导出')
  } catch (e) {
    // 导出走 fetch，错误原因在 e.message 里（后端的 detail 已经透传过来了）
    ElMessage.error(e?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.wrong-page { padding: 20px; }
.page-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 16px;
}
.page-header h2 { font-size: 18px; font-weight: 500; margin: 0 0 4px; }
.page-sub { font-size: 13px; color: var(--neutral-500, #909399); margin: 0; }
.header-actions { display: flex; gap: 8px; }

.stat-row { display: flex; gap: 12px; margin-bottom: 14px; }
.stat-card {
  flex: 1; background: #fff; border-radius: 8px; padding: 14px 16px;
  border: 1px solid var(--neutral-200, #e4e7ed);
}
.stat-value { font-size: 24px; font-weight: 600; color: #13B7A5; }
.stat-label { font-size: 12px; color: var(--neutral-500, #909399); margin-top: 2px; }

.filter-card { margin-bottom: 12px; }
.filter-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }

.content-preview {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; line-height: 1.5;
}
.content-preview :deep(img) { max-height: 40px; vertical-align: middle; }

.detail-box { padding: 8px 48px 12px; line-height: 1.7; }
.detail-q { margin-bottom: 10px; }
.detail-q :deep(img) { max-width: 100%; max-height: 260px; }
.detail-line { margin-bottom: 6px; font-size: 13px; }
.detail-label { color: var(--neutral-500, #909399); margin-right: 6px; }
.detail-answer { font-weight: 600; color: #67C23A; }
.detail-answer.wrong { color: #F56C6C; }

.pager { display: flex; justify-content: flex-end; margin-top: 14px; }
</style>
