<template>
  <div class="questions-page">
    <div class="page-header">
      <h2>题库管理</h2>
      <div class="header-actions">
        <el-button @click="importDialogVisible = true">
          <el-icon><Upload /></el-icon> 批量导入
        </el-button>
        <el-button @click="categoryDialogVisible = true">
          <el-icon><Collection /></el-icon> 分类管理
        </el-button>
        <el-button @click="handleExport">
          <el-icon><Download /></el-icon> 批量导出
        </el-button>
        <el-button type="primary" @click="openAdd">
          <el-icon><Plus /></el-icon> 添加题目
        </el-button>
      </div>
    </div>

    <!-- 搜索栏 -->
    <el-card class="search-card">
      <el-row :gutter="12">
        <el-col :xs="24" :sm="6">
          <el-input v-model="search" placeholder="搜索题目内容" clearable @change="loadData">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </el-col>
        <el-col :xs="8" :sm="4">
          <el-select v-model="filterType" placeholder="题型" clearable @change="loadData" style="width:100%">
            <el-option label="单选题" value="single" />
            <el-option label="多选题" value="multiple" />
            <el-option label="判断题" value="judgment" />
          </el-select>
        </el-col>
        <el-col :xs="16" :sm="5">
          <el-cascader
            v-model="filterCategory"
            :options="categoryOptions"
            :props="{ checkStrictly: true, checkOnClickNode: true, emitPath: false, label: 'label', value: 'value' }"
            placeholder="分类"
            clearable
            @change="loadData"
            style="width:100%"
          />
        </el-col>
      </el-row>
    </el-card>

    <!-- 题目列表 -->
    <el-card>
      <div v-if="selectionMode" style="margin-bottom: 16px; display: flex; gap: 8px; align-items: center;">
        <el-button type="primary" size="small" @click="handleSelectAll">
          <el-icon><Check /></el-icon> 全选
        </el-button>
        <el-button size="small" @click="handleCancelSelection">
          <el-icon><Close /></el-icon> 取消选择
        </el-button>
        <el-button type="danger" size="small" @click="handleBatchDelete" :disabled="selectedRows.length === 0">
          <el-icon><Delete /></el-icon> 批量删除 ({{ selectedRows.length }})
        </el-button>
        <el-button size="small" @click="selectionMode = false">
          退出多选
        </el-button>
      </div>
      <el-table
        ref="tableRef"
        :data="tableData"
        v-loading="loading"
        style="width:100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column v-if="selectionMode" type="selection" width="55" />
        <el-table-column label="序号" width="60">
          <template #default="{ $index }">
            {{ total - (currentPage - 1) * pageSize - $index }}
          </template>
        </el-table-column>
        <el-table-column label="题型" width="90">
          <template #default="{ row }">
            <el-tag :type="typeTagMap[row.type]?.type" size="small">{{ typeTagMap[row.type]?.label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="题目内容" min-width="200">
          <template #default="{ row }">
            <span v-html="row.content" class="content-preview" @click="onPreviewClick"></span>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column prop="answer" label="答案" width="80" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
            <el-button size="small" type="primary" @click="selectionMode = true" v-if="!selectionMode">多选</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next, first-page, last-page, jumper"
        style="margin-top:16px;justify-content:flex-end"
        @current-change="loadData"
      />
    </el-card>

    <!-- 图片预览（可缩放） -->
    <ImagePreview v-model="previewVisible" :src="previewSrc" :title="previewTitle" />

    <!-- 添加/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑题目' : '添加题目'" width="700px" :close-on-click-modal="false">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="80px">
        <el-form-item label="题型" prop="type">
          <el-radio-group v-model="form.type" @change="onTypeChange">
            <el-radio-button value="single">单选题</el-radio-button>
            <el-radio-button value="multiple">多选题</el-radio-button>
            <el-radio-button value="judgment">判断题</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="题目内容" prop="content">
          <div class="editor-wrapper">
            <div ref="editorToolbar" style="border-bottom:1px solid #ccc"></div>
            <div ref="editorContent" style="height:240px;overflow-y:auto"></div>
          </div>
        </el-form-item>

        <el-form-item label="分类">
          <el-cascader
            v-model="form.category"
            :options="categoryOptions"
            :props="{ checkStrictly: true, checkOnClickNode: true, emitPath: false, label: 'label', value: 'value' }"
            placeholder="请选择分类"
            clearable
            filterable
            style="width:250px"
          />
        </el-form-item>

        <!-- 单选/多选选项 -->
        <template v-if="form.type !== 'judgment'">
          <el-form-item label="选项">
            <div class="options-list">
              <div v-for="key in Object.keys(form.options)" :key="key" class="option-item">
                <span class="option-key">{{ key }}</span>
                <el-input v-model="form.options[key]" :placeholder="`选项${key}`" style="flex:1" />
                <el-button link type="danger" @click="removeOption(key)" v-if="Object.keys(form.options).length > 2">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
              <el-button link @click="addOption" v-if="Object.keys(form.options).length < 6">
                <el-icon><Plus /></el-icon> 添加选项
              </el-button>
            </div>
          </el-form-item>

          <el-form-item label="正确答案" prop="answer">
            <el-checkbox-group v-if="form.type === 'multiple'" v-model="multipleAnswer">
              <el-checkbox v-for="key in Object.keys(form.options)" :key="key" :value="key">{{ key }}</el-checkbox>
            </el-checkbox-group>
            <el-radio-group v-else v-model="form.answer">
              <el-radio v-for="key in Object.keys(form.options)" :key="key" :value="key">{{ key }}</el-radio>
            </el-radio-group>
          </el-form-item>
        </template>

        <!-- 判断题答案 -->
        <el-form-item label="正确答案" prop="answer" v-else>
          <el-radio-group v-model="form.answer">
            <el-radio value="正确">正确</el-radio>
            <el-radio value="错误">错误</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="解析">
          <el-input v-model="form.analysis" type="textarea" :rows="2" placeholder="答案解析（可选）" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入弹窗 -->
    <el-dialog v-model="importDialogVisible" title="批量导入题目" width="500px">
      <div class="import-tips">
        <p>支持格式：<strong>Excel (.xlsx)</strong>、<strong>TXT/CSV</strong></p>
        <p>Excel 表头：题型 | 题干 | 选项 | 答案 | 解析 | 分类</p>
        <p>TXT 格式（逗号分隔）：single,题目,A:选项1|B:选项2,A,解析,分类</p>
        <p>题型值：<code>single</code>（单选）/ <code>multiple</code>（多选）/ <code>judgment</code>（判断）</p>
      </div>
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        accept=".xlsx,.xls,.txt,.csv"
        :on-change="onFileChange"
        drag
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽文件到此处，或 <em>点击上传</em></div>
      </el-upload>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleImport" :loading="importing">开始导入</el-button>
      </template>
    </el-dialog>

    <!-- 分类管理弹窗 -->
    <el-dialog v-model="categoryDialogVisible" title="分类管理" width="600px">
      <div style="margin-bottom: 16px;">
        <el-button type="primary" @click="openCreateCategory">
          <el-icon><Plus /></el-icon> 添加分类
        </el-button>
      </div>
      <el-table :data="categories" v-loading="categoryLoading" style="width: 100%">
        <el-table-column prop="name" label="分类名称" />
        <el-table-column prop="count" label="题目数量" width="100" />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" @click="openRenameCategory(row)">重命名</el-button>
            <el-button size="small" type="danger" @click="handleDeleteCategory(row)" :disabled="row.count > 0">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 添加分类弹窗 -->
    <el-dialog v-model="createDialogVisible" title="添加分类" width="400px">
      <el-form>
        <el-form-item label="分类名称">
          <el-input v-model="createForm.name" placeholder="请输入新分类名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreateCategory">确定</el-button>
      </template>
    </el-dialog>

    <!-- 重命名分类弹窗 -->
    <el-dialog v-model="renameDialogVisible" title="重命名分类" width="400px">
      <el-form>
        <el-form-item label="原名称">
          <el-input v-model="renameForm.oldName" disabled />
        </el-form-item>
        <el-form-item label="新名称">
          <el-input v-model="renameForm.newName" placeholder="请输入新分类名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="renameDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleRenameCategory">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, watch, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getQuestions, createQuestion, updateQuestion, deleteQuestion, importQuestions, exportQuestions, getCategories, createCategory, renameCategory, deleteCategory } from '@/api/questions'

const loading = ref(false)
const saving = ref(false)
const importing = ref(false)
const tableData = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(15)
const search = ref('')
const filterType = ref('')
const filterCategory = ref('')
const dialogVisible = ref(false)
const importDialogVisible = ref(false)
const editingId = ref(null)
const formRef = ref(null)
import ImagePreview from '@/components/ImagePreview.vue'

const uploadRef = ref(null)
const importFile = ref(null)
const editorToolbar = ref(null)
const editorContent = ref(null)
const tableRef = ref(null)
let editorInstance = null

// 多选相关
const selectionMode = ref(false)
const selectedRows = ref([])

// 分类管理
const categoryDialogVisible = ref(false)
const renameDialogVisible = ref(false)
const createDialogVisible = ref(false)
const categories = ref([])

// 将分类转换为级联选择器需要的树形结构
const categoryOptions = computed(() => {
  const catMap = {}
  const result = []

  for (const cat of categories.value) {
    const parts = cat.name.split('/')
    if (parts.length === 1) {
      // 顶级分类
      catMap[cat.name] = { value: cat.name, label: cat.name, children: [] }
      result.push(catMap[cat.name])
    } else if (parts.length === 2) {
      // 二级分类
      const [parent, child] = parts
      if (!catMap[parent]) {
        catMap[parent] = { value: parent, label: parent, children: [] }
        result.push(catMap[parent])
      }
      catMap[parent].children.push({ value: cat.name, label: child })
    }
  }

  // 清理没有子分类的父级
  for (const item of result) {
    if (!item.children || item.children.length === 0) {
      delete item.children
    }
  }
  return result
})

const categoryLoading = ref(false)
const renameForm = reactive({ oldName: '', newName: '' })
const createForm = reactive({ name: '' })

const typeTagMap = {
  single: { label: '单选', type: 'primary' },
  multiple: { label: '多选', type: 'warning' },
  judgment: { label: '判断', type: 'success' },
}

const defaultOptions = () => ({ A: '', B: '', C: '', D: '' })

const form = reactive({
  type: 'single',
  content: '',
  options: defaultOptions(),
  answer: '',
  analysis: '',
  category: '',
})

const multipleAnswer = ref([])

const formRules = {
  type: [{ required: true, message: '请选择题型' }],
  content: [{ required: true, message: '请输入题目内容' }],
  answer: [{ required: true, message: '请设置正确答案' }],
}

const stripHtml = (html) => {
  const div = document.createElement('div')
  div.innerHTML = html || ''
  const text = div.textContent || div.innerText || ''
  return text.length > 60 ? text.slice(0, 60) + '...' : text
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

const fixImageUrls = (items) => {
  items.forEach(item => {
    if (item.content) {
      // 将所有 /uploads 开头的图片路径替换为完整的后端URL
      item.content = item.content.replace(/src=["'](\/uploads\/[^"']+)["']/g, (match, url) => {
        // 如果URL已经是以 http 开头的完整URL，不做处理
        if (url.startsWith('http://') || url.startsWith('https://')) {
          return match
        }
        // 否则拼接API基础URL（移除 /api 后缀）
        const baseUrl = API_BASE.replace(/\/api$/, '')
        return `src="${baseUrl}${url}"`
      })
    }
  })
  return items
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getQuestions({
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
      type: filterType.value,
      search: search.value,
      category: filterCategory.value,
    })
    tableData.value = fixImageUrls(res.items)
    total.value = res.total
  } finally {
    loading.value = false
  }
}

/*
 * 题干 HTML 规范化。
 *
 * 题库里 500 多道带图题的题干都是这种结构：
 *     <p>请选择下图所示细胞名称：</p><img src="..." alt="image" />
 * 图片是"裸"的顶层元素，不在任何块级标签里。
 *
 * wangEditor 底层是 Slate，Slate 的根节点只接受块级元素，
 * 顶层裸 <img> 会被直接丢掉 —— 表现就是"打开编辑弹窗，图片没了"，
 * 而 onChange 里 editor.getHtml() 再把丢过图片的内容写回数据库，
 * 一存就把图片彻底删掉了。
 *
 * 这里把顶层非块级元素包进 <p>，和正常能显示的图片结构保持一致。
 */
const BLOCK_TAGS = new Set([
  'P', 'DIV', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'UL', 'OL', 'LI',
  'TABLE', 'THEAD', 'TBODY', 'TR', 'TD', 'TH', 'BLOCKQUOTE', 'PRE',
  'HR', 'SECTION', 'ARTICLE', 'FIGURE', 'FIGCAPTION'
])

const normalizeEditorHtml = (html) => {
  if (!html) return html
  const box = document.createElement('div')
  box.innerHTML = html
  let changed = false
  for (const node of Array.from(box.childNodes)) {
    if (node.nodeType === Node.ELEMENT_NODE) {
      if (!BLOCK_TAGS.has(node.tagName)) {
        const p = document.createElement('p')
        box.insertBefore(p, node)
        p.appendChild(node)
        changed = true
      }
    } else if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
      const p = document.createElement('p')
      p.textContent = node.textContent
      box.replaceChild(p, node)
      changed = true
    }
  }
  return changed ? box.innerHTML : html
}

const countImages = (html) => (html.match(/<img\b/gi) || []).length

// 兜底：保存前发现图片少了，把原内容里的图片补回去，绝不让保存把图片删掉
const restoreLostImages = (originalHtml, currentHtml) => {
  if (!originalHtml || countImages(currentHtml) >= countImages(originalHtml)) return currentHtml
  const srcSet = (html) => {
    const box = document.createElement('div')
    box.innerHTML = html || ''
    return new Set(Array.from(box.querySelectorAll('img')).map(i => i.getAttribute('src')).filter(Boolean))
  }
  const currentSrcs = srcSet(currentHtml)
  const box = document.createElement('div')
  box.innerHTML = originalHtml
  const lost = Array.from(box.querySelectorAll('img')).filter(i => {
    const src = i.getAttribute('src')
    return src && !currentSrcs.has(src)
  })
  if (!lost.length) return currentHtml
  const out = document.createElement('div')
  out.innerHTML = currentHtml
  lost.forEach(img => {
    const p = document.createElement('p')
    p.appendChild(img.cloneNode(true))
    out.appendChild(p)
  })
  return out.innerHTML
}

// 编辑器里的图片点击看大图。
// 每次打开弹窗都会重建编辑器，所以要先把上一次的监听摘掉，避免重复绑定。
let editorClickTarget = null
let editorClickHandler = null
const bindEditorImageClick = () => {
  const el = editorContent.value
  if (editorClickTarget && editorClickHandler) {
    editorClickTarget.removeEventListener('click', editorClickHandler)
  }
  editorClickTarget = el
  if (!el) return
  editorClickHandler = (e) => {
    const img = e.target.closest?.('img')
    if (img) openPreview(img.src, '题目图片')
  }
  el.addEventListener('click', editorClickHandler)
}

// ---- 图片预览（题库里的图有时很大，列表里只有缩略图，看不清全貌）----
const previewVisible = ref(false)
const previewSrc = ref('')
const previewTitle = ref('')

const openPreview = (src, title = '') => {
  if (!src) return
  previewSrc.value = src
  previewTitle.value = title
  previewVisible.value = true
}

// 列表里的缩略图：点一下看大图
const onPreviewClick = (e) => {
  const img = e.target.closest?.('img')
  if (img) openPreview(img.src, '题目图片')
}

const initEditor = async () => {
  try {
    const { createEditor, createToolbar } = await import('@wangeditor/editor')
    if (editorInstance) {
      editorInstance.destroy()
      editorInstance = null
    }
    editorInstance = createEditor({
      selector: editorContent.value,
      // 顶层裸 <img> 会被 wangEditor 丢掉，先包成 <p> 再交给编辑器
      html: normalizeEditorHtml(form.content),
      config: {
        onChange(editor) {
          form.content = editor.getHtml()
        },
        placeholder: '请输入题目内容，支持图文混排...',
        MENU_CONF: {
          uploadImage: {
            server: '/api/upload/image',
            fieldName: 'file',
            maxFileSize: 5 * 1024 * 1024,
            maxNumberOfFiles: 10,
            allowedFileTypes: ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'],
            headers: {
              Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
            },
            customInsert(res, insertFn) {
              if (res.errno === 0 && res.data) {
                insertFn(res.data.url, res.data.alt || '', res.data.href || res.data.url)
              }
            },
            onInsertedImage(imageNode) {
              if (imageNode && imageNode.elem) {
                imageNode.elem.style.maxWidth = '50%'
              }
            },
            customBrowseAndUpload(insertFn) {
              const input = document.createElement('input')
              input.type = 'file'
              input.accept = 'image/*'
              input.onchange = async () => {
                const file = input.files[0]
                if (!file) return
                const formData = new FormData()
                formData.append('file', file)
                try {
                  const res = await fetch('/api/upload/image', {
                    method: 'POST',
                    headers: { Authorization: `Bearer ${localStorage.getItem('token') || ''}` },
                    body: formData,
                  })
                  const data = await res.json()
                  if (data.errno === 0 && data.data) {
                    insertFn(data.data.url, data.data.alt || '', data.data.href || data.data.url)
                  }
                } catch (err) {
                  console.error('图片上传失败:', err)
                }
              }
              input.click()
            },
          },
          editImage: {
            onUpdated(imageNode) {
              if (imageNode && imageNode.elem) {
                imageNode.elem.style.maxWidth = '50%'
              }
            },
          },
        },
      },
      mode: 'simple',
    })
    createToolbar({
      editor: editorInstance,
      selector: editorToolbar.value,
      config: { 
        toolbarKeys: [
          'bold', 'italic', 'underline', '|',
          'uploadImage', 'insertImage', 'editImage', '|',
          'undo', 'redo'
        ],
        insertImage: {
          onInsertedImage(imageNode) {
            if (imageNode) {
              imageNode.setAttr('style', 'max-width: 50%;')
            }
          }
        }
      },
      mode: 'simple',
    })
    // 图片大小调节由 wangEditor 内置的 hover 工具栏提供
    // 编辑器里的图片点一下可以看大图
    bindEditorImageClick()
  } catch {
    // wangeditor 未安装时降级为 textarea
  }
}

const openAdd = async () => {
  editingId.value = null
  originalContent.value = ''
  form.type = 'single'
  form.content = ''
  // 重置选项，保持响应式
  Object.keys(form.options).forEach(key => delete form.options[key])
  form.options['A'] = ''
  form.options['B'] = ''
  form.options['C'] = ''
  form.options['D'] = ''
  form.answer = ''
  form.analysis = ''
  form.category = ''
  multipleAnswer.value = []
  loadCategories()
  dialogVisible.value = true
  await nextTick()
  initEditor()
}

// 打开编辑时的原始题干，保存时用来兜底比对，防止图片被悄悄删掉
const originalContent = ref('')

const openEdit = async (row) => {
  editingId.value = row.id
  originalContent.value = row.content || ''
  form.type = row.type
  form.content = row.content
  // 原地修改 options，保持响应式绑定
  try {
    const newOptions = JSON.parse(row.options)
    // 清空现有选项
    Object.keys(form.options).forEach(key => delete form.options[key])
    // 复制新选项
    Object.keys(newOptions).forEach(key => form.options[key] = newOptions[key])
  } catch {
    Object.keys(form.options).forEach(key => delete form.options[key])
    form.options['A'] = ''
    form.options['B'] = ''
    form.options['C'] = ''
    form.options['D'] = ''
  }
  form.answer = row.answer
  form.analysis = row.analysis || ''
  form.category = row.category || ''
  multipleAnswer.value = row.type === 'multiple' ? row.answer.split(',') : []
  loadCategories()
  dialogVisible.value = true
  await nextTick()
  initEditor()
}

const onTypeChange = () => {
  form.answer = ''
  multipleAnswer.value = []
  if (form.type !== 'judgment') {
    Object.keys(form.options).forEach(key => delete form.options[key])
    form.options['A'] = ''
    form.options['B'] = ''
    form.options['C'] = ''
    form.options['D'] = ''
  }
}

const addOption = () => {
  const keys = Object.keys(form.options)
  const next = String.fromCharCode(65 + keys.length)
  form.options[next] = ''
}

const removeOption = (key) => {
  delete form.options[key]
}

const handleSave = async () => {
  console.log('handleSave called, editingId:', editingId.value)
  console.log('form.options before processing:', form.options)
  // 先处理多选题答案，再进行表单验证
  if (form.type === 'multiple') {
    if (multipleAnswer.value.length < 2) {
      ElMessage.warning('多选题至少选择2个正确答案')
      return
    }
    form.answer = multipleAnswer.value.sort().join(',')
  }
  try {
    await formRef.value.validate()
    console.log('form validation passed')
  } catch (e) {
    console.log('form validation failed:', e)
    return
  }
  if (!form.content || form.content === '<p><br></p>') {
    ElMessage.warning('请输入题目内容')
    return
  }
  // 兜底：编辑器万一把图片丢了，先问一句，绝不让"点一下保存"把图片悄悄删掉
  if (countImages(form.content) < countImages(originalContent.value)) {
    const origCount = countImages(originalContent.value)
    const nowCount = countImages(form.content)
    try {
      await ElMessageBox.confirm(
        `题干里的图片比原来少了（原来 ${origCount} 张，现在 ${nowCount} 张）。\n` +
        `通常是编辑器没能保留图片。是否把原图补回？\n（选"取消"则按当前内容保存，等于主动删除图片）`,
        '图片将被删除',
        { type: 'warning', confirmButtonText: '补回图片', cancelButtonText: '取消（删除图片）' }
      )
      form.content = restoreLostImages(originalContent.value, form.content)
    } catch {
      // 用户选择"取消"：按当前内容保存
    }
  }
  saving.value = true
  try {
    // 深拷贝选项，确保最新值
    const currentOptions = {}
    for (const key in form.options) {
      currentOptions[key] = form.options[key]
    }
    console.log('currentOptions:', currentOptions)
    const optionsStr = JSON.stringify(currentOptions)
    console.log('optionsStr:', optionsStr)
    const payload = {
      type: form.type,
      content: form.content,
      options: optionsStr,
      answer: form.answer,
      analysis: form.analysis || '',
      category: form.category || '',
    }
    console.log('payload:', payload)
    if (editingId.value) {
      console.log('Updating question:', editingId.value)
      const result = await updateQuestion(editingId.value, payload)
      console.log('Update result:', result)
      ElMessage.success('修改成功')
    } else {
      console.log('Creating new question')
      const result = await createQuestion(payload)
      console.log('Create result:', result)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (err) {
    console.error('Save error:', err)
    ElMessage.error('保存失败: ' + (err.message || err))
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm(`确定删除该题目？`, '提示', { type: 'warning' })
  await deleteQuestion(row.id)
  ElMessage.success('已删除')
  loadData()
}

const handleSelectionChange = (selection) => {
  selectedRows.value = selection
}

const handleSelectAll = () => {
  tableRef.value.toggleAllSelection()
}

const handleCancelSelection = () => {
  tableRef.value.clearSelection()
  selectedRows.value = []
}

const handleBatchDelete = async () => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要删除的题目')
    return
  }
  await ElMessageBox.confirm(`确定删除选中的 ${selectedRows.value.length} 道题目？`, '提示', { type: 'warning' })
  // 逐个删除选中的题目
  for (const row of selectedRows.value) {
    await deleteQuestion(row.id)
  }
  ElMessage.success(`已删除 ${selectedRows.value.length} 道题目`)
  selectedRows.value = []
  loadData()
}

const onFileChange = (file) => {
  importFile.value = file.raw
}

const handleImport = async () => {
  if (!importFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', importFile.value)
    const res = await importQuestions(fd)
    ElMessage.success(`成功导入 ${res.imported} 道题目`)
    importDialogVisible.value = false
    importFile.value = null
    loadData()
  } finally {
    importing.value = false
  }
}

const handleExport = async () => {
  const params = {}
  if (filterType.value) params.type = filterType.value
  if (search.value) params.search = search.value
  if (filterCategory.value) params.category = filterCategory.value
  try {
    await exportQuestions(params)
    ElMessage.success('导出成功！')
  } catch {
    ElMessage.error('导出失败，请重试')
  }
}

const loadCategories = async () => {
  categoryLoading.value = true
  try {
    categories.value = await getCategories()
  } finally {
    categoryLoading.value = false
  }
}

const openRenameCategory = (row) => {
  renameForm.oldName = row.name
  renameForm.newName = row.name
  renameDialogVisible.value = true
}

const handleRenameCategory = async () => {
  if (!renameForm.newName.trim()) {
    ElMessage.warning('请输入新分类名称')
    return
  }
  await renameCategory(renameForm.oldName, renameForm.newName.trim())
  ElMessage.success('重命名成功')
  renameDialogVisible.value = false
  loadCategories()
  loadData()
}

const handleDeleteCategory = async (row) => {
  await ElMessageBox.confirm(`确定删除分类「${row.name}」？`, '提示', { type: 'warning' })
  await deleteCategory(row.name)
  ElMessage.success('删除成功')
  loadCategories()
}

const openCreateCategory = () => {
  createForm.name = ''
  createDialogVisible.value = true
}

const handleCreateCategory = async () => {
  if (!createForm.name.trim()) {
    ElMessage.warning('请输入分类名称')
    return
  }
  await createCategory(createForm.name.trim())
  ElMessage.success('添加成功')
  createDialogVisible.value = false
  loadCategories()
}

watch(categoryDialogVisible, (val) => {
  if (val) loadCategories()
})

onMounted(() => {
  loadData()
  loadCategories()
  const style = document.createElement('style')
  style.id = 'editor-tooltip-style'
  style.textContent = `
    .w-e-bar-item { position: relative !important; }
    .w-e-bar-item > button {
      position: relative !important;
    }
    .w-e-bar-item > .editor-tooltip {
      position: absolute !important;
      bottom: calc(100% + 8px) !important;
      left: 50% !important;
      transform: translateX(-50%) !important;
      background: #303133 !important;
      color: #fff !important;
      padding: 6px 10px !important;
      border-radius: 4px !important;
      font-size: 12px !important;
      white-space: nowrap !important;
      opacity: 0 !important;
      visibility: hidden !important;
      transition: opacity 0.2s ease, visibility 0.2s ease !important;
      z-index: 100 !important;
      pointer-events: none !important;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
      line-height: 1.4 !important;
    }
    .w-e-bar-item:hover > .editor-tooltip {
      opacity: 1 !important;
      visibility: visible !important;
    }
  `
  document.head.appendChild(style)
})
</script>

<style scoped>
.questions-page { padding: 20px; }
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 { font-size: 18px; font-weight: 500; }
.header-actions { display: flex; gap: 8px; }
.search-card { margin-bottom: 16px; }
.search-card :deep(.el-card__body) { padding: 16px; }
.content-preview { font-size: 13px; color: #606266; display: block; max-height: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.content-preview :deep(img) { max-width: 120px; max-height: 80px; vertical-align: middle; }
.content-preview :deep(p) { margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.editor-wrapper { border: 1px solid #dcdfe6; border-radius: 4px; width: 100%; }
/*
 * 编辑器里的图片按容器宽度自适应。
 * 之前图片按原始尺寸渲染，编辑器区域只有 160px 高，
 * 大图只露出一条边，看起来就像"图片没了"。
 */
.editor-wrapper :deep(img) {
  max-width: 100%;
  height: auto;
  cursor: zoom-in;
}
.options-list { display: flex; flex-direction: column; gap: 8px; width: 100%; }
.option-item { display: flex; align-items: center; gap: 8px; }
.option-key {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #409EFF;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  flex-shrink: 0;
}
.import-tips {
  background: #f5f7fa;
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 16px;
  font-size: 13px;
  line-height: 2;
  color: #606266;
}
.import-tips code {
  background: #e8f4ff;
  padding: 1px 4px;
  border-radius: 3px;
  color: #409EFF;
}
:deep(.w-e-toolbar .w-e-bar-item) {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
}
:deep(.w-e-toolbar .w-e-bar-item button) {
  width: 32px !important;
  height: 32px !important;
  min-width: 32px !important;
  padding: 4px !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  border: none !important;
  border-radius: 4px !important;
  margin: 2px 4px !important;
  background: transparent !important;
  cursor: pointer !important;
  transition: background-color 0.2s !important;
}
:deep(.w-e-toolbar .w-e-bar-item button:hover) {
  background: #e8e8e8 !important;
}
:deep(.w-e-toolbar .w-e-bar-item button svg) {
  width: 18px !important;
  height: 18px !important;
  fill: #555 !important;
}
:deep(.w-e-toolbar) {
  background: #f8f9fa !important;
  border-radius: 4px 4px 0 0 !important;
  padding: 4px 8px !important;
  display: flex !important;
  flex-wrap: nowrap !important;
  align-items: center !important;
  gap: 4px !important;
}
:deep(.w-e-bar-divider) {
  width: 1px !important;
  height: 20px !important;
  background: #ddd !important;
  margin: 0 8px !important;
}
:deep(.editor-wrapper) {
  background: #fff !important;
}
</style>
