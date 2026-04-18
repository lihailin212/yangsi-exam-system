<template>
  <div class="exams-page">
    <div class="page-header">
      <h2>考试管理</h2>
      <el-button type="primary" @click="openAdd">
        <el-icon><Plus /></el-icon> 创建考试
      </el-button>
    </div>

    <el-card>
      <el-table :data="tableData" v-loading="loading" style="width:100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="考试名称" min-width="160" />
        <el-table-column label="时长" width="90">
          <template #default="{ row }">{{ row.duration }}分钟</template>
        </el-table-column>
        <el-table-column label="题目数" width="80">
          <template #default="{ row }">{{ row.question_count }}</template>
        </el-table-column>
        <el-table-column label="参考人数" width="90">
          <template #default="{ row }">{{ row.participant_count }}</template>
        </el-table-column>
        <el-table-column label="及格分" width="80">
          <template #default="{ row }">{{ row.pass_score }}分</template>
        </el-table-column>
        <el-table-column label="总分" width="80">
          <template #default="{ row }">{{ row.total_score }}分</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row)">{{ getStatus(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="160">
          <template #default="{ row }">{{ formatDate(row.start_time) }}</template>
        </el-table-column>
        <el-table-column label="结束时间" width="160">
          <template #default="{ row }">{{ formatDate(row.end_time) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openRecords(row)">成绩</el-button>
            <el-button size="small" type="success" @click="openDistribution(row)">分发</el-button>
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top:16px;justify-content:flex-end"
        @current-change="loadData"
      />
    </el-card>

    <!-- 创建/编辑考试弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑考试' : '创建考试'"
      width="760px" :close-on-click-modal="false">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="14">
            <el-form-item label="考试名称" prop="title">
              <el-input v-model="form.title" placeholder="请输入考试名称" />
            </el-form-item>
          </el-col>
          <el-col :span="10">
            <el-form-item label="时长(分钟)" prop="duration">
              <el-input-number v-model="form.duration" :min="5" :max="300" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="开始时间">
              <el-date-picker v-model="form.start_time" type="datetime" placeholder="选择开始时间"
                format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束时间">
              <el-date-picker v-model="form.end_time" type="datetime" placeholder="选择结束时间"
                format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="及格分数">
          <el-input-number v-model="form.pass_score" :min="0" :max="100" />
          <span style="margin-left:8px;color:#909399;font-size:13px">（百分制）</span>
        </el-form-item>

        <el-form-item label="补考次数">
          <el-input-number v-model="form.retake_limit" :min="0" :max="99" />
          <span style="margin-left:8px;color:#909399;font-size:13px">（0=不限，>0=最多考该次数）</span>
        </el-form-item>

        <el-form-item label="题型分值">
          <div style="display: flex; gap: 16px; align-items: center;">
            <div>
              <span style="margin-right:8px;font-size:13px;color:#606266">单选题</span>
              <el-input-number v-model="form.single_score" :min="1" :max="100" />
            </div>
            <div>
              <span style="margin-right:8px;font-size:13px;color:#606266">多选题</span>
              <el-input-number v-model="form.multiple_score" :min="1" :max="100" />
            </div>
            <div>
              <span style="margin-right:8px;font-size:13px;color:#606266">判断题</span>
              <el-input-number v-model="form.judgment_score" :min="1" :max="100" />
            </div>
          </div>
          <div style="margin-top:8px;color:#909399;font-size:13px">设置每类题型的分值，用于计算考试总分</div>
        </el-form-item>

        <el-form-item label="选择题目">
          <div style="width:100%">
            <div class="question-filter">
              <el-input v-model="qSearch" placeholder="搜索题目" style="width:180px" clearable @input="loadQuestions" />
              <el-select v-model="qType" placeholder="题型" clearable style="width:100px" @change="loadQuestions">
                <el-option label="单选题" value="single" />
                <el-option label="多选题" value="multiple" />
                <el-option label="判断题" value="judgment" />
              </el-select>
              <el-cascader
                v-model="qCategory"
                :options="categoryOptions"
                :props="{ checkStrictly: true, emitPath: false, label: 'label', value: 'value' }"
                placeholder="分类"
                clearable
                @change="loadQuestions"
                style="width:160px"
              />
              <el-button type="primary" @click="openRandomDialog">
                <el-icon><Refresh /></el-icon> 随机抽题
              </el-button>
            </div>
            <el-table
              ref="questionTableRef"
              :data="allQuestions"
              @selection-change="onSelectionChange"
              max-height="260"
              style="width:100%;margin-top:8px"
              v-loading="qLoading"
              row-key="id"
            >
              <el-table-column type="selection" width="50" :reserve-selection="true" />
              <el-table-column label="题型" width="80">
                <template #default="{ row }">
                  <el-tag size="small" :type="typeTagMap[row.type]?.type">{{ typeTagMap[row.type]?.label }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="题目内容" min-width="200">
                <template #default="{ row }">
                  <div class="question-content-cell" v-html="row.content"></div>
                </template>
              </el-table-column>
              <el-table-column label="分值" width="60">
                <template #default="{ row }">
                  {{ getQuestionScore(row) }}
                </template>
              </el-table-column>
            </el-table>
            <div style="margin-top:8px;color:#409EFF;font-size:13px">
              已选 {{ form.question_ids.length }} 道题，总分 {{ totalScore }} 分
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 随机抽题弹窗 -->
    <el-dialog v-model="randomDialogVisible" title="随机抽题" width="400px" :close-on-click-modal="false">
      <el-form :model="randomForm" label-width="100px">
        <el-form-item label="单选题">
          <el-input-number v-model="randomForm.single" :min="0" :max="100" style="width:150px" />
          <span style="margin-left:8px;color:#909399;font-size:13px">道</span>
        </el-form-item>
        <el-form-item label="多选题">
          <el-input-number v-model="randomForm.multiple" :min="0" :max="100" style="width:150px" />
          <span style="margin-left:8px;color:#909399;font-size:13px">道</span>
        </el-form-item>
        <el-form-item label="判断题">
          <el-input-number v-model="randomForm.judgment" :min="0" :max="100" style="width:150px" />
          <span style="margin-left:8px;color:#909399;font-size:13px">道</span>
        </el-form-item>
      </el-form>
      <div style="color:#909399;font-size:13px;margin-top:8px">
        系统将从题库中随机选择指定数量的题目
      </div>
      <template #footer>
        <el-button @click="randomDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleRandomSelect" :loading="randomLoading">确定</el-button>
      </template>
    </el-dialog>

    <!-- 成绩记录弹窗 -->
    <el-dialog v-model="recordsVisible" :title="`${currentExam?.title} — 成绩记录`" width="700px">
      <el-table :data="records" v-loading="recordsLoading" style="width:100%">
        <el-table-column prop="exam_title" label="考试名称" min-width="160" />
        <el-table-column prop="employee_id" label="工号" width="100" />
        <el-table-column prop="user_name" label="姓名" width="90" />
        <el-table-column label="得分" width="90">
          <template #default="{ row }">
            <span :style="{ color: row.percent >= currentExam?.pass_score ? '#67C23A' : '#F56C6C' }">
              {{ row.score }}/{{ row.total_score }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="百分制" width="90">
          <template #default="{ row }">
            <el-tag :type="row.percent >= currentExam?.pass_score ? 'success' : 'danger'" size="small">
              {{ row.percent }}分
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="提交时间" min-width="160">
          <template #default="{ row }">{{ formatDate(row.submitted_at) }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 分发考试弹窗 -->
    <el-dialog v-model="distDialogVisible" :title="`分发考试 — ${currentExam?.title}`" width="640px">
      <div v-if="currentExam">
        <el-alert type="info" :closable="false" style="margin-bottom:16px;">
          将二维码或链接发给考生，考生扫码后输入工号和密码即可参加考试。
        </el-alert>

        <div class="invite-link-row">
          <span class="invite-link-label">考试链接：</span>
          <code class="invite-link">{{ examLoginUrl }}</code>
          <el-button size="small" @click="copyLink" style="margin-left:8px">复制链接</el-button>
        </div>

        <div style="margin-top:16px; text-align:center;">
          <el-button size="large" type="primary" @click="showQrcodeDialog">
            <el-icon><Monitor /></el-icon> 显示二维码
          </el-button>
        </div>

        <el-divider content-position="left">允许参加的考生</el-divider>

        <div class="dist-tip" style="margin-bottom:12px; color:#909399; font-size:13px;">
          不选择考生则所有账号均可参加。选择考生后，只有被选中的考生才能参加。
        </div>

        <!-- 已选考生列表 -->
        <div v-if="selectedStudents.length > 0">
          <div class="selected-students">
            <el-tag
              v-for="s in selectedStudents"
              :key="s.user_id"
              closable
              @close="removeStudent(s.user_id)"
              style="margin: 4px 4px 4px 0;"
            >
              {{ s.user_name }} ({{ s.employee_id }})
            </el-tag>
          </div>
        </div>

        <!-- 选择考生 -->
        <div class="add-student-row">
          <el-select
            v-model="selectedUserIds"
            multiple
            placeholder="搜索并选择考生"
            filterable
            style="flex:1"
            :loading="studentsLoading"
            @change="handleStudentSelect"
          >
            <el-option
              v-for="u in allStudents"
              :key="u.id"
              :label="`${u.name} (${u.employee_id})`"
              :value="u.id"
            />
          </el-select>
          <el-button type="primary" @click="handleStudentSelect" :disabled="selectedUserIds.length === 0">
            添加
          </el-button>
        </div>
      </div>
    </el-dialog>

    <!-- 二维码弹窗 -->
    <el-dialog v-model="qrcodeDialogVisible" title="考试邀请二维码" width="300px">
      <div ref="qrcodeRef" style="display:flex;justify-content:center;padding:8px;"></div>
      <p style="text-align:center;color:#909399;font-size:12px;margin-top:8px;">
        扫码即可开始考试
      </p>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getExams, createExam, updateExam, deleteExam, getExamRecords } from '@/api/exams'
import { getQuestions, randomQuestions, getCategories } from '@/api/questions'
import { getExamLoginUrl, getExamStudents, setExamStudents } from '@/api/distributions'
import { getStudents } from '@/api/students'
import { Monitor } from '@element-plus/icons-vue'

const loading = ref(false)
const saving = ref(false)
const tableData = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(15)
const dialogVisible = ref(false)
const editingId = ref(null)
const formRef = ref(null)
const questionTableRef = ref(null)

const allQuestions = ref([])
const qLoading = ref(false)
const qSearch = ref('')
const qType = ref('')
const qCategory = ref('')
const categories = ref([])

// 将分类转换为级联选择器需要的树形结构
const categoryOptions = computed(() => {
  const catMap = {}
  const result = []
  for (const cat of categories.value) {
    const parts = cat.name.split('/')
    if (parts.length === 1) {
      catMap[cat.name] = { value: cat.name, label: cat.name, children: [] }
      result.push(catMap[cat.name])
    } else if (parts.length === 2) {
      const [parent, child] = parts
      if (!catMap[parent]) {
        catMap[parent] = { value: parent, label: parent, children: [] }
        result.push(catMap[parent])
      }
      catMap[parent].children.push({ value: cat.name, label: child })
    }
  }
  for (const item of result) {
    if (!item.children || item.children.length === 0) {
      delete item.children
    }
  }
  return result
})

const recordsVisible = ref(false)
const records = ref([])
const recordsLoading = ref(false)
const currentExam = ref(null)

// 随机抽题
const randomDialogVisible = ref(false)
const randomLoading = ref(false)
const randomForm = reactive({
  single: 0,
  multiple: 0,
  judgment: 0
})

const typeTagMap = {
  single: { label: '单选', type: 'primary' },
  multiple: { label: '多选', type: 'warning' },
  judgment: { label: '判断', type: 'success' },
}

const form = reactive({
  title: '',
  duration: 90,
  start_time: null,
  end_time: null,
  pass_score: 60,
  retake_limit: 0,
  single_score: 10,
  multiple_score: 20,
  judgment_score: 5,
  question_ids: [],
})

const formRules = {
  title: [{ required: true, message: '请输入考试名称' }],
  duration: [{ required: true, message: '请设置考试时长' }],
}

// 获取题目分值（根据考试设置）
const getQuestionScore = (question) => {
  const scoreMap = {
    single: form.single_score,
    multiple: form.multiple_score,
    judgment: form.judgment_score,
  }
  return scoreMap[question.type] || 10
}

// 已选题目类型统计（用于计算总分）
const selectionTypes = ref([])
const randomTypes = ref([])
const randomIds = ref([])  // 随机选中的 ID 集合

// 合并两种来源，手动勾选优先
const selectedQuestionTypes = computed(() => {
  if (selectionTypes.value.length > 0) return selectionTypes.value
  return randomTypes.value
})

// 根据已选题目类型计算总分
const totalScore = computed(() => {
  const scoreMap = {
    single: form.single_score,
    multiple: form.multiple_score,
    judgment: form.judgment_score,
  }
  return selectedQuestionTypes.value.reduce((sum, type) => sum + (scoreMap[type] || 10), 0)
})

const stripHtml = (html) => {
  const div = document.createElement('div')
  div.innerHTML = html || ''
  const t = div.textContent || ''
  return t.length > 50 ? t.slice(0, 50) + '...' : t
}

const formatDate = (dt) => {
  if (!dt) return '-'
  // 服务器返回UTC时间，解析后加8小时转为中国本地时间
  const [datePart, timePart] = dt.split('T')
  const [year, month, day] = datePart.split('-').map(Number)
  const [hour, minute, second] = timePart.split(':').map(Number)
  const d = new Date(year, month - 1, day, hour + 8, minute, second)
  const date = d.toLocaleDateString('zh-CN').replace(/\//g, '-')
  const time = d.toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit' })
  return `${date} ${time}`
}

const getStatus = (exam) => {
  const now = new Date()
  if (exam.start_time && new Date(exam.start_time) > now) return '未开始'
  if (exam.end_time && new Date(exam.end_time) < now) return '已结束'
  if (exam.start_time) return '进行中'
  return '未设置'
}

const getStatusType = (exam) => {
  const s = getStatus(exam)
  return { '进行中': 'success', '未开始': 'info', '已结束': '', '未设置': 'warning' }[s]
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getExams({ skip: (currentPage.value - 1) * pageSize.value, limit: pageSize.value })
    tableData.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

const loadQuestions = async () => {
  qLoading.value = true
  try {
    const res = await getQuestions({ skip: 0, limit: 200, search: qSearch.value, type: qType.value, category: qCategory.value })
    allQuestions.value = res.items
  } finally {
    qLoading.value = false
  }
}

const loadCategories = async () => {
  try {
    categories.value = await getCategories()
  } catch (e) {
    console.error('加载分类失败', e)
  }
}

const onSelectionChange = (rows) => {
  // 批量恢复选中期间不更新，由 restoreSelection 统一设置
  if (syncPending.value) return
  form.question_ids = rows.map(r => r.id)
  selectionTypes.value = rows.map(r => r.type)
}

// 批量恢复选中期间暂停 onSelectionChange
const syncPending = ref(false)

// 恢复表格选中状态（通过 ID 匹配新数组中的行对象）
const restoreSelection = () => {
  if (!questionTableRef.value) return
  const idSet = new Set(randomIds.value)
  questionTableRef.value.clearSelection()
  syncPending.value = true
  allQuestions.value.forEach(q => {
    if (idSet.has(q.id)) {
      questionTableRef.value.toggleRowSelection(q, true)
    }
  })
  // 恢复完成后一次性设置，不要依赖事件的累积
  form.question_ids = randomIds.value
  syncPending.value = false
}

const openAdd = async () => {
  editingId.value = null
  Object.assign(form, {
    title: '', duration: 90, start_time: null, end_time: null, pass_score: 60,
    retake_limit: 0, single_score: 10, multiple_score: 20, judgment_score: 5, question_ids: []
  })
  qSearch.value = ''
  qType.value = ''
  qCategory.value = ''
  selectionTypes.value = []
  randomTypes.value = []
  randomIds.value = []
  dialogVisible.value = true
  await nextTick()
  if (questionTableRef.value) questionTableRef.value.clearSelection()
  loadCategories()
  loadQuestions()
}

const openEdit = async (row) => {
  editingId.value = row.id
  const { getExam } = await import('@/api/exams')
  const detail = await getExam(row.id)
  const ids = detail.question_ids || []
  Object.assign(form, {
    title: detail.title,
    duration: detail.duration,
    start_time: detail.start_time,
    end_time: detail.end_time,
    pass_score: detail.pass_score,
    retake_limit: detail.retake_limit || 0,
    single_score: detail.single_score || 10,
    multiple_score: detail.multiple_score || 20,
    judgment_score: detail.judgment_score || 5,
    question_ids: ids,
  })
  qSearch.value = ''
  qType.value = ''
  qCategory.value = ''
  selectionTypes.value = []
  randomTypes.value = []
  randomIds.value = ids  // 从后端获取的 ID 集合
  dialogVisible.value = true
  await nextTick()
  if (questionTableRef.value) questionTableRef.value.clearSelection()
  loadCategories()
  await loadQuestions()
  await nextTick()
  restoreSelection()
}

const handleSave = async () => {
  await formRef.value.validate()
  saving.value = true
  try {
    const payload = {
      title: form.title,
      duration: form.duration,
      start_time: form.start_time,
      end_time: form.end_time,
      pass_score: form.pass_score,
      retake_limit: form.retake_limit,
      single_score: form.single_score,
      multiple_score: form.multiple_score,
      judgment_score: form.judgment_score,
      question_ids: form.question_ids,
    }
    if (editingId.value) {
      await updateExam(editingId.value, payload)
      ElMessage.success('修改成功')
    } else {
      await createExam(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (err) {
    console.error('保存失败:', err)
    ElMessage.error(err?.response?.data?.detail || err?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm(`确定删除考试「${row.title}」？`, '提示', { type: 'warning' })
  await deleteExam(row.id)
  ElMessage.success('已删除')
  loadData()
}

const openRecords = async (row) => {
  currentExam.value = row
  recordsVisible.value = true
  recordsLoading.value = true
  try {
    records.value = await getExamRecords(row.id)
  } finally {
    recordsLoading.value = false
  }
}

// 随机抽题
const openRandomDialog = () => {
  randomForm.single = 0
  randomForm.multiple = 0
  randomForm.judgment = 0
  randomDialogVisible.value = true
}

// ---- 分发管理 ----
const distDialogVisible = ref(false)
const qrcodeDialogVisible = ref(false)
const qrcodeRef = ref(null)
const examLoginUrl = ref('')
const studentsLoading = ref(false)
const allStudents = ref([])
const selectedStudents = ref([])  // 已保存的考生
const selectedUserIds = ref([])   // 下拉框选中的ID

const openDistribution = async (row) => {
  currentExam.value = row
  examLoginUrl.value = ''
  selectedStudents.value = []
  selectedUserIds.value = []
  distDialogVisible.value = true
  try {
    const res = await getExamLoginUrl(row.id)
    examLoginUrl.value = res.url
  } catch (e) {
    examLoginUrl.value = `${window.location.origin}/#/exam-login/${row.id}`
  }
  await loadExamStudents(row.id)
  await loadAllStudents()
}

const loadExamStudents = async (examId) => {
  studentsLoading.value = true
  try {
    selectedStudents.value = await getExamStudents(examId)
  } catch (e) {
    selectedStudents.value = []
  } finally {
    studentsLoading.value = false
  }
}

const loadAllStudents = async () => {
  studentsLoading.value = true
  try {
    const res = await getStudents({ skip: 0, limit: 500 })
    allStudents.value = res.items || []
  } finally {
    studentsLoading.value = false
  }
}

const handleStudentSelect = async () => {
  if (selectedUserIds.value.length === 0) return
  // 将选中的用户转为考生信息对象，加入已选列表
  const newStudents = selectedUserIds.value
    .map(id => allStudents.value.find(u => u.id === id))
    .filter(Boolean)
    .map(u => ({ user_id: u.id, user_name: u.name, employee_id: u.employee_id }))

  // 合并（去重）
  const existingIds = new Set(selectedStudents.value.map(s => s.user_id))
  for (const s of newStudents) {
    if (!existingIds.has(s.user_id)) {
      selectedStudents.value.push(s)
    }
  }
  selectedUserIds.value = []
  await saveExamStudents()
}

const removeStudent = async (userId) => {
  selectedStudents.value = selectedStudents.value.filter(s => s.user_id !== userId)
  await saveExamStudents()
}

const saveExamStudents = async () => {
  if (!currentExam.value) return
  try {
    const userIds = selectedStudents.value.map(s => s.user_id)
    await setExamStudents(currentExam.value.id, userIds)
  } catch (e) {
    ElMessage.error('保存考生名单失败')
  }
}

const copyLink = async () => {
  try {
    await navigator.clipboard.writeText(examLoginUrl.value)
    ElMessage.success('链接已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

const showQrcodeDialog = async () => {
  qrcodeDialogVisible.value = true
  await nextTick()
  if (qrcodeRef.value) {
    qrcodeRef.value.innerHTML = ''
    try {
      const QRCode = (await import('qrcode')).default
      const canvas = document.createElement('canvas')
      await QRCode.toCanvas(canvas, examLoginUrl.value, {
        width: 220,
        margin: 2,
        color: { dark: '#0D7377', light: '#ffffff' }
      })
      qrcodeRef.value.appendChild(canvas)
    } catch {
      qrcodeRef.value.innerHTML = '<p style="color:#F56C6C;text-align:center">二维码生成失败</p>'
    }
  }
}

// 弹窗关闭时清空二维码
import { watch } from 'vue'
watch(qrcodeDialogVisible, (val) => {
  if (!val && qrcodeRef.value) qrcodeRef.value.innerHTML = ''
})

const handleRandomSelect = async () => {
  const total = randomForm.single + randomForm.multiple + randomForm.judgment
  if (total === 0) {
    ElMessage.warning('请至少选择一道题目')
    return
  }
  randomLoading.value = true
  try {
    const res = await randomQuestions({
      single: randomForm.single,
      multiple: randomForm.multiple,
      judgment: randomForm.judgment
    })
    form.question_ids = res.question_ids
    randomIds.value = res.question_ids  // 保存 ID 集合
    randomTypes.value = (res.questions || []).map(q => q.type)
    selectionTypes.value = []  // 清除手动选择，手动勾选时会覆盖
    randomDialogVisible.value = false
    ElMessage.success(`成功随机抽取 ${res.question_ids.length} 道题目`)
    // 刷新表格并恢复选中状态
    await loadQuestions()
    await nextTick()
    restoreSelection()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '抽题失败，请检查题库题目数量是否足够')
  } finally {
    randomLoading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.exams-page { padding: 20px; }
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 { font-size: 18px; font-weight: 500; }
.question-filter { display: flex; gap: 8px; }
.invite-link-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  margin-top: 4px;
}
.invite-link-label { font-weight: 500; color: #303133; white-space: nowrap; }
.invite-link {
  font-family: monospace;
  color: #409EFF;
  background: #ecf5ff;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  word-break: break-all;
  flex: 1;
}
.invite-link-hint { color: #909399; font-size: 13px; }
.add-student-row { display: flex; gap: 8px; }
.selected-students { min-height: 32px; max-height: 160px; overflow-y: auto; margin-bottom: 8px; padding: 8px; background: #f5f7fa; border-radius: 6px; }
.question-content-cell { font-size: 13px; max-height: 80px; overflow: hidden; text-overflow: ellipsis; }
.question-content-cell :deep(img) { max-width: 120px; max-height: 80px; vertical-align: middle; }
.question-content-cell :deep(p) { margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
