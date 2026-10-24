<template>
  <div class="arena-manage">
    <div class="page-header">
      <h2>专业擂台赛</h2>
      <el-button type="primary" @click="openCreateDialog">
        <el-icon><Plus /></el-icon> 创建擂台赛
      </el-button>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-select v-model="filterStatus" placeholder="状态筛选" clearable @change="loadArenas">
        <el-option label="全部" value="" />
        <el-option label="待开始" value="pending" />
        <el-option label="进行中" value="active" />
        <el-option label="已暂停" value="paused" />
        <el-option label="已结束" value="finished" />
      </el-select>
    </div>

    <!-- 擂台赛列表 -->
    <div class="arena-list">
      <el-empty v-if="arenas.length === 0" description="暂无擂台赛" />

      <div v-for="arena in arenas" :key="arena.id" class="arena-card" @click="openArena(arena)">
        <div class="arena-header">
          <h3>{{ arena.title }}</h3>
          <el-tag :type="getStatusType(arena.status)">{{ getStatusLabel(arena.status) }}</el-tag>
        </div>
        <div class="arena-info">
          <div class="info-item">
            <span class="label">队伍数</span>
            <span class="value">{{ arena.team_count }}</span>
          </div>
          <div class="info-item">
            <span class="label">题目数</span>
            <span class="value">{{ arena.question_count }}</span>
          </div>
          <div class="info-item">
            <span class="label">邀请码</span>
            <span class="value code">{{ arena.invite_code }}</span>
          </div>
        </div>
        <div class="arena-footer">
          <span class="date">创建于 {{ formatDate(arena.created_at) }}</span>
          <div class="actions">
            <el-button size="small" @click.stop="openDetail(arena)">详情</el-button>
            <el-button size="small" @click.stop="editArena(arena)">编辑</el-button>
            <el-button size="small" type="primary" @click.stop="openHost(arena.id)">主持</el-button>
            <el-button size="small" type="danger" @click.stop="deleteArenaFn(arena.id)">删除</el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="showCreateDialog" :title="editingArena ? '编辑擂台赛' : '创建擂台赛'" width="760px" top="5vh">
      <el-form :model="form" label-width="130px">
        <el-form-item label="擂台赛名称">
          <el-input v-model="form.title" placeholder="请输入擂台赛名称" />
        </el-form-item>

        <el-divider content-position="left">队伍设置</el-divider>

        <el-form-item label="队伍名称">
          <div class="team-inputs">
            <div v-for="(name, idx) in form.team_names" :key="idx" class="team-input-row">
              <el-input v-model="form.team_names[idx]" placeholder="队伍名称" style="width: 200px" />
              <el-color-picker v-model="form.team_colors[idx]" size="small" />
              <el-button type="danger" link @click="removeTeamRow(idx)" :disabled="form.team_names.length <= 2">
                删除
              </el-button>
            </div>
            <el-button @click="addTeamRow" :disabled="form.team_names.length >= 10">添加队伍</el-button>
          </div>
        </el-form-item>

        <el-divider content-position="left">规则设置</el-divider>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="必答题数量">
              <el-input-number v-model="form.settings.required_count" :min="1" :max="20" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="必答每题分值">
              <el-input-number v-model="form.settings.required_score" :min="1" :max="100" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="必答答题时间">
              <el-input-number v-model="form.settings.required_time" :min="10" :max="120" /> 秒
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="必答答错扣分">
              <el-switch v-model="form.settings.required_wrong_penalty" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="抢答题数量">
              <el-input-number v-model="form.settings.rush_count" :min="1" :max="30" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="抢答答对分值">
              <el-input-number v-model="form.settings.rush_correct_score" :min="1" :max="100" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="抢答答错扣分">
              <el-input-number v-model="form.settings.rush_wrong_penalty" :min="0" :max="50" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="抢答答题时间">
              <el-input-number v-model="form.settings.rush_answer_time" :min="5" :max="60" /> 秒
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="加赛题数量">
              <el-input-number v-model="form.settings.overtime_count" :min="1" :max="20" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="加赛每题分值">
              <el-input-number v-model="form.settings.overtime_score" :min="10" :max="100" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="加赛答错扣分">
              <el-input-number v-model="form.settings.overtime_wrong_penalty" :min="0" :max="100" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="淘汰队伍数">
              <el-input-number v-model="form.settings.elimination_count" :min="0" :max="5" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">题目配置</el-divider>

        <el-form-item label="筛选">
          <div class="question-filter">
            <el-input
              v-model="qSearch"
              placeholder="搜索题目内容"
              clearable
              style="width: 200px"
            />
            <el-select v-model="qType" placeholder="题型" clearable style="width: 120px">
              <el-option label="单选题" value="single" />
              <el-option label="多选题" value="multiple" />
              <el-option label="判断题" value="judgment" />
            </el-select>
            <el-cascader
              v-model="qCategory"
              :options="categoryOptions"
              :props="{ checkStrictly: true, checkOnClickNode: true, emitPath: false, label: 'label', value: 'value' }"
              placeholder="分类"
              clearable
              style="width: 200px"
            />
            <el-button @click="resetQuestionFilter">重置</el-button>
          </div>
          <div class="filter-summary">
            共匹配 {{ filteredQuestions.length }} 题（已选 {{ selectedQuestionCount }} 题）
          </div>
        </el-form-item>

        <el-form-item label="必答题库">
          <el-select v-model="form.required_question_ids" multiple filterable placeholder="选择必答题" style="width: 100%">
            <el-option v-for="q in visibleQuestions" :key="q.id" :label="questionLabel(q)" :value="q.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="抢答题库">
          <el-select v-model="form.rush_question_ids" multiple filterable placeholder="选择抢答题" style="width: 100%">
            <el-option v-for="q in visibleQuestions" :key="q.id" :label="questionLabel(q)" :value="q.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="综合分析题库">
          <el-select v-model="form.analysis_question_ids" multiple filterable placeholder="选择综合分析题" style="width: 100%">
            <el-option v-for="q in visibleQuestions" :key="q.id" :label="questionLabel(q)" :value="q.id" />
          </el-select>
        </el-form-item>

        <el-alert v-if="editingArena" type="info" :closable="false" show-icon>
          编辑模式下：队伍与题目会在保存时新增；如需删除队伍或题目，请在详情页操作。
        </el-alert>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">{{ editingArena ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="showDetailDrawer" :title="detailArena?.title || '擂台赛详情'" size="640px">
      <div v-if="detailArena">
        <el-descriptions :column="2" border class="detail-desc">
          <el-descriptions-item label="状态">{{ getStatusLabel(detailArena.status) }}</el-descriptions-item>
          <el-descriptions-item label="邀请码">{{ detailArena.invite_code }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(detailArena.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="当前轮次">{{ detailArena.current_round }}</el-descriptions-item>
        </el-descriptions>

        <div class="qr-section">
          <h4>选手扫码加入</h4>
          <div class="qr-body">
            <img v-if="qrImage" :src="qrImage" alt="加入二维码" class="qr-image" />
            <div class="qr-info">
              <p>邀请码：<strong>{{ detailArena.invite_code }}</strong></p>
              <p class="qr-hint">邀请码15分钟内有效，最多10人加入</p>
              <el-button size="small" @click="refreshInvite">刷新邀请码</el-button>
              <el-button size="small" type="primary" @click="copyJoinLink">复制选手链接</el-button>
            </div>
          </div>
        </div>

        <el-divider content-position="left">队伍（{{ detailTeams.length }}）</el-divider>
        <el-table :data="detailTeams" size="small" border>
          <el-table-column prop="name" label="队名" />
          <el-table-column label="颜色" width="140">
            <template #default="{ row }">
              <span class="color-dot" :style="{ background: row.color }"></span>
              {{ row.color }}
            </template>
          </el-table-column>
          <el-table-column prop="score" label="得分" width="70" />
          <el-table-column prop="status" label="状态" width="90" />
          <el-table-column label="操作" width="90">
            <template #default="{ row }">
              <el-button type="danger" link size="small" @click="removeTeamFn(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-divider content-position="left">题目（{{ detailQuestions.length }}）</el-divider>
        <el-table :data="detailQuestions" size="small" border max-height="320">
          <el-table-column prop="order_num" label="序号" width="70" />
          <el-table-column label="题型" width="100">
            <template #default="{ row }">{{ getTypeLabel(row.q_type) }}</template>
          </el-table-column>
          <el-table-column label="题目" show-overflow-tooltip>
            <template #default="{ row }">{{ stripHtml(row.question?.content) }}</template>
          </el-table-column>
          <el-table-column prop="score" label="分值" width="70" />
          <el-table-column label="操作" width="90">
            <template #default="{ row }">
              <el-button type="danger" link size="small" @click="removeQuestionFn(row)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import QRCode from 'qrcode'
import {
  getArenas, createArena, updateArena, deleteArena as apiDeleteArena,
  addArenaQuestions, getArenaQuestions, getArenaTeams, addTeam, updateTeam,
  deleteTeam, deleteArenaQuestion, refreshArenaInvite,
} from '@/api/arena'
import { getQuestions, getCategories } from '@/api/questions'
import { Plus } from '@element-plus/icons-vue'

const arenas = ref([])
const filterStatus = ref('')
const showCreateDialog = ref(false)
const editingArena = ref(null)
const saving = ref(false)
const allQuestions = ref([])
const categories = ref([])
const qSearch = ref('')
const qType = ref('')
const qCategory = ref('')

const showDetailDrawer = ref(false)
const detailArena = ref(null)
const detailTeams = ref([])
const detailQuestions = ref([])
const qrImage = ref('')

const defaultSettings = {
  required_count: 5,
  required_score: 10,
  required_time: 30,
  required_wrong_penalty: false,
  rush_count: 10,
  rush_correct_score: 20,
  rush_wrong_penalty: 10,
  rush_answer_time: 15,
  rush_per_person_limit: false,
  overtime_count: 10,
  overtime_score: 30,
  overtime_wrong_penalty: 15,
  help_per_round: 1,
  elimination_count: 1,
  resurrection_rounds: 1,
  resurrection_count: 5,
}

const palette = ['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399', '#8E44AD', '#3498DB', '#E74C3C', '#2ECC71', '#F39C12']

const form = ref({
  title: '',
  team_names: ['队伍1', '队伍2'],
  team_colors: ['#409EFF', '#67C23A'],
  settings: { ...defaultSettings },
  required_question_ids: [],
  rush_question_ids: [],
  analysis_question_ids: [],
})

// 保留 img 的 alt 文本：形态学题目的题干文字基本都写在 alt 里
// （如 alt="红细胞形态学.png"），直接去标签会把唯一的文字信息一并丢掉。
const stripHtml = (html) => (html || '')
  .replace(/<img[^>]*?\salt=(["'])(.*?)\1[^>]*>/gi, ' $2 ')
  .replace(/<[^>]*>/g, ' ')
  .replace(/\s+/g, ' ')
  .trim()

const questionLabel = (q) => {
  const text = stripHtml(q.content).slice(0, 40)
  const typeMap = { single: '单选', multiple: '多选', judgment: '判断' }
  const cat = q.category ? `(${q.category}) ` : ''
  return `[${typeMap[q.type] || q.type}] ${cat}${text}`
}

// 分类级联选择器树（父级 / 子级）
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
    if (!item.children || item.children.length === 0) delete item.children
  }
  return result
})

// 按分类 / 题型 / 关键词过滤题目
const filteredQuestions = computed(() => {
  const keyword = qSearch.value.trim().toLowerCase()
  const cat = qCategory.value
  return allQuestions.value.filter(q => {
    if (qType.value && q.type !== qType.value) return false
    if (cat) {
      const qCat = q.category || ''
      // 选中父分类时匹配其所有子分类
      if (!(qCat === cat || qCat.startsWith(cat + '/'))) return false
    }
    if (keyword && !stripHtml(q.content).toLowerCase().includes(keyword)) return false
    return true
  })
})

// 下拉选项 = 过滤结果 + 已选中但被过滤掉的题（避免已选项消失）
const visibleQuestions = computed(() => {
  const selected = new Set([
    ...form.value.required_question_ids,
    ...form.value.rush_question_ids,
    ...form.value.analysis_question_ids,
  ])
  const list = [...filteredQuestions.value]
  if (selected.size) {
    const ids = new Set(list.map(q => q.id))
    for (const q of allQuestions.value) {
      if (selected.has(q.id) && !ids.has(q.id)) list.push(q)
    }
  }
  return list
})

const selectedQuestionCount = computed(() => {
  const set = new Set([
    ...form.value.required_question_ids,
    ...form.value.rush_question_ids,
    ...form.value.analysis_question_ids,
  ])
  return set.size
})

const resetQuestionFilter = () => {
  qSearch.value = ''
  qType.value = ''
  qCategory.value = ''
}

const loadCategories = async () => {
  try {
    categories.value = await getCategories() || []
  } catch (e) {
    console.error('加载分类失败:', e)
    categories.value = []
  }
}

const loadArenas = async () => {
  try {
    const params = {}
    if (filterStatus.value) params.status = filterStatus.value
    const res = await getArenas(params)
    arenas.value = Array.isArray(res) ? res : (res?.items || [])
  } catch (e) {
    console.error('加载擂台赛失败:', e)
    ElMessage.error('加载失败')
  }
}

const loadQuestions = async () => {
  try {
    // 分页拉取全部题目（一次 limit 过大时后端会静默截断，导致最老的题抽不到）
    const PAGE = 200
    const items = []
    let total = 0
    for (let skip = 0; ; skip += PAGE) {
      const res = await getQuestions({ skip, limit: PAGE })
      const page = Array.isArray(res) ? res : (res?.items || [])
      items.push(...page)
      total = res?.total ?? items.length
      if (items.length >= total || page.length === 0) break
    }
    allQuestions.value = items
  } catch (e) {
    console.error('加载题目失败:', e)
    allQuestions.value = []
  }
}

const addTeamRow = () => {
  if (form.value.team_names.length >= 10) return
  const idx = form.value.team_names.length + 1
  form.value.team_names.push(`队伍${idx}`)
  form.value.team_colors.push(palette[idx % palette.length])
}

const removeTeamRow = (idx) => {
  if (form.value.team_names.length <= 2) return
  form.value.team_names.splice(idx, 1)
  form.value.team_colors.splice(idx, 1)
}

const openCreateDialog = () => {
  editingArena.value = null
  form.value = {
    title: '',
    team_names: ['队伍1', '队伍2'],
    team_colors: ['#409EFF', '#67C23A'],
    settings: { ...defaultSettings },
    required_question_ids: [],
    rush_question_ids: [],
    analysis_question_ids: [],
  }
  showCreateDialog.value = true
}

const submitForm = async () => {
  if (!form.value.title) {
    ElMessage.warning('请输入擂台赛名称')
    return
  }
  if (form.value.team_names.length < 2) {
    ElMessage.warning('至少需要2支队伍')
    return
  }
  const names = form.value.team_names.map(n => (n || '').trim())
  if (names.some(n => !n)) {
    ElMessage.warning('队伍名称不能为空')
    return
  }

  saving.value = true
  try {
    if (editingArena.value) {
      await updateArena(editingArena.value.id, {
        title: form.value.title,
        settings: form.value.settings,
      })
      // 同步队伍（新增 / 改色）
      const existing = await getArenaTeams(editingArena.value.id)
      const existingByName = new Map(existing.map(t => [t.name, t]))
      for (let i = 0; i < names.length; i++) {
        const found = existingByName.get(names[i])
        if (found) {
          if (found.color !== form.value.team_colors[i]) {
            await updateTeam(found.id, { color: form.value.team_colors[i] })
          }
        } else {
          await addTeam(editingArena.value.id, {
            name: names[i],
            color: form.value.team_colors[i],
          })
        }
      }

      // 同步题目（新增；已存在的题目后端会自动跳过）
      const existingQs = await getArenaQuestions(editingArena.value.id)
      const existingQuestionIds = new Set((existingQs || []).map(q => q.question_id))
      const qPayload = []
      let qOrder = (existingQs || []).length + 1
      const pushQuestions = (ids, qType, score) => {
        ids.forEach(id => {
          if (existingQuestionIds.has(id)) return
          qPayload.push({ question_id: id, q_type: qType, order_num: qOrder++, score })
        })
      }
      pushQuestions(form.value.required_question_ids, 'required', form.value.settings.required_score)
      pushQuestions(form.value.rush_question_ids, 'rush', form.value.settings.rush_correct_score)
      pushQuestions(form.value.analysis_question_ids, 'analysis', 100)
      if (qPayload.length > 0) {
        await addArenaQuestions(editingArena.value.id, qPayload)
      }
      ElMessage.success('保存成功')
    } else {
      const arenaData = {
        title: form.value.title,
        team_names: names,
        team_colors: form.value.team_colors,
        settings: form.value.settings,
      }
      const res = await createArena(arenaData)
      const arenaId = res?.id ?? res?.data?.id

      const payload = []
      let order = 1
      form.value.required_question_ids.forEach(id => {
        payload.push({ question_id: id, q_type: 'required', order_num: order++, score: form.value.settings.required_score })
      })
      form.value.rush_question_ids.forEach(id => {
        payload.push({ question_id: id, q_type: 'rush', order_num: order++, score: form.value.settings.rush_correct_score })
      })
      form.value.analysis_question_ids.forEach(id => {
        payload.push({ question_id: id, q_type: 'analysis', order_num: order++, score: 100 })
      })
      if (payload.length > 0) {
        await addArenaQuestions(arenaId, payload)
      }
      ElMessage.success('创建成功')
    }
    showCreateDialog.value = false
    editingArena.value = null
    loadArenas()
  } catch (e) {
    console.error('保存失败:', e)
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  } finally {
    saving.value = false
  }
}

const editArena = (arena) => {
  editingArena.value = arena
  form.value.title = arena.title
  form.value.settings = { ...defaultSettings, ...(arena.settings || {}) }
  form.value.team_names = []
  form.value.team_colors = []
  form.value.required_question_ids = []
  form.value.rush_question_ids = []
  form.value.analysis_question_ids = []
  showCreateDialog.value = true

  // 载入现有队伍与题目
  Promise.all([getArenaTeams(arena.id), getArenaQuestions(arena.id)])
    .then(([teams, qs]) => {
      ;(teams || []).forEach(t => {
        form.value.team_names.push(t.name)
        form.value.team_colors.push(t.color)
      })
      ;(qs || []).forEach(q => {
        if (q.q_type === 'required') form.value.required_question_ids.push(q.question_id)
        if (q.q_type === 'rush') form.value.rush_question_ids.push(q.question_id)
        if (q.q_type === 'analysis') form.value.analysis_question_ids.push(q.question_id)
      })
    })
    .catch(e => console.error('加载配置失败:', e))
}

const openArena = (arena) => {
  openDetail(arena)
}

const openDetail = async (arena) => {
  detailArena.value = arena
  showDetailDrawer.value = true
  try {
    const [teams, qs] = await Promise.all([
      getArenaTeams(arena.id),
      getArenaQuestions(arena.id),
    ])
    detailTeams.value = teams || []
    detailQuestions.value = qs || []
  } catch (e) {
    console.error('加载详情失败:', e)
  }
  await generateQR(arena)
}

const generateQR = async (arena) => {
  try {
    const url = `${window.location.origin}${window.location.pathname}#/arena-join?code=${arena.invite_code}`
    qrImage.value = await QRCode.toDataURL(url, { width: 180, margin: 1 })
  } catch (e) {
    console.error('生成二维码失败:', e)
    qrImage.value = ''
  }
}

const refreshInvite = async () => {
  try {
    const res = await refreshArenaInvite(detailArena.value.id)
    detailArena.value.invite_code = res.invite_code
    await generateQR(detailArena.value)
    ElMessage.success('邀请码已刷新')
    loadArenas()
  } catch (e) {
    ElMessage.error('刷新失败')
  }
}

const copyJoinLink = async () => {
  const url = `${window.location.origin}${window.location.pathname}#/arena-join?code=${detailArena.value.invite_code}`
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success('链接已复制')
  } catch (e) {
    ElMessage.warning('复制失败，请手动选择链接')
  }
}

const removeTeamFn = async (team) => {
  try {
    await ElMessageBox.confirm(`确定删除队伍「${team.name}」吗？`, '提示', { type: 'warning' })
    await deleteTeam(team.id)
    detailTeams.value = detailTeams.value.filter(t => t.id !== team.id)
    ElMessage.success('删除成功')
    loadArenas()
  } catch (e) {
    // 取消
  }
}

const removeQuestionFn = async (question) => {
  try {
    await ElMessageBox.confirm('确定从本擂台赛移除该题目吗？', '提示', { type: 'warning' })
    await deleteArenaQuestion(question.id)
    detailQuestions.value = detailQuestions.value.filter(q => q.id !== question.id)
    ElMessage.success('移除成功')
    loadArenas()
  } catch (e) {
    // 取消
  }
}

const openHost = (arenaId) => {
  window.open(`${location.origin}${location.pathname}#/arena-host/${arenaId}`, '_blank')
}

const deleteArenaFn = async (arenaId) => {
  try {
    await ElMessageBox.confirm('确定要删除此擂台赛吗？', '警告', { type: 'warning' })
    await apiDeleteArena(arenaId)
    ElMessage.success('删除成功')
    loadArenas()
  } catch (e) {
    // 取消
  }
}

const getStatusType = (status) => {
  const map = { pending: 'info', active: 'success', paused: 'warning', finished: '' }
  return map[status] || 'info'
}

const getStatusLabel = (status) => {
  const map = { pending: '待开始', active: '进行中', paused: '已暂停', finished: '已结束' }
  return map[status] || status
}

const getTypeLabel = (type) => {
  const map = { required: '必答题', rush: '抢答题', analysis: '综合分析题', overtime: '加赛题' }
  return map[type] || type
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadArenas().catch(e => console.error('加载擂台赛失败:', e))
  loadQuestions().catch(e => console.error('加载题目失败:', e))
  loadCategories().catch(e => console.error('加载分类失败:', e))
})
</script>

<style scoped>
.arena-manage {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  color: var(--neutral-800);
}

.filter-bar {
  margin-bottom: 20px;
}

.question-filter {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.filter-summary {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}

.arena-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 20px;
}

.arena-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.3s ease;
  border: 1px solid var(--neutral-200);
}

.arena-card:hover {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.arena-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.arena-header h3 {
  margin: 0;
  font-size: 18px;
  color: var(--neutral-800);
}

.arena-info {
  display: flex;
  gap: 20px;
  margin-bottom: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
}

.info-item .label {
  font-size: 12px;
  color: var(--neutral-400);
}

.info-item .value {
  font-size: 16px;
  font-weight: 600;
  color: var(--neutral-700);
}

.info-item .value.code {
  font-family: var(--font-number, monospace);
  color: var(--accent-600);
}

.arena-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 16px;
  border-top: 1px solid var(--neutral-100);
}

.arena-footer .date {
  font-size: 12px;
  color: var(--neutral-400);
}

.arena-footer .actions {
  display: flex;
  gap: 8px;
}

.team-inputs {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.team-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.detail-desc {
  margin-bottom: 20px;
}

.qr-section {
  margin-bottom: 20px;
}

.qr-section h4 {
  margin: 0 0 12px 0;
}

.qr-body {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}

.qr-image {
  width: 180px;
  height: 180px;
  border: 1px solid var(--neutral-200);
  border-radius: 8px;
}

.qr-info p {
  margin: 0 0 8px 0;
}

.qr-hint {
  font-size: 12px;
  color: var(--neutral-400);
}

.color-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
</style>
