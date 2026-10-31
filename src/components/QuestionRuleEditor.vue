<template>
  <div class="rule-editor">
    <div v-if="rules.length === 0" class="rule-empty">
      还没有规则，先添加一条：选分类（可留空表示全部）、题型、抽几道
    </div>

    <div v-for="(rule, index) in rules" :key="index" class="rule-row">
      <el-select
        v-model="rule.category"
        placeholder="分类（留空=全部）"
        style="width:200px"
        clearable
        filterable
      >
        <el-option-group label="形态学亚类别">
          <el-option
            v-for="s in subCategories"
            :key="s.value"
            :label="s.label"
            :value="s.value"
          />
        </el-option-group>
        <el-option-group label="题库分类">
          <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
        </el-option-group>
      </el-select>

      <el-select v-model="rule.type" placeholder="题型" style="width:120px" clearable>
        <el-option label="不限题型" value="" />
        <el-option label="单选题" value="single" />
        <el-option label="多选题" value="multiple" />
        <el-option label="判断题" value="judgment" />
        <el-option label="填空题" value="fill" />
      </el-select>

      <el-input-number v-model="rule.count" :min="0" :max="500" style="width:130px" />
      <span class="rule-unit">道</span>
      <el-button link type="danger" @click="removeRule(index)">删除</el-button>
    </div>

    <div class="rule-actions">
      <el-button size="small" @click="addRule()">
        <el-icon><Plus /></el-icon> 添加规则
      </el-button>
      <el-divider direction="vertical" />
      <span class="rule-tip">按题型：</span>
      <el-button size="small" @click="addTypeRule('single')">单选题</el-button>
      <el-button size="small" @click="addTypeRule('fill')">填空题</el-button>
      <el-button size="small" @click="addTypeRule('multiple')">多选题</el-button>
      <el-button size="small" @click="addTypeRule('judgment')">判断题</el-button>
      <el-divider direction="vertical" />
      <span class="rule-tip">按亚类别：</span>
      <el-button
        v-for="s in subCategories"
        :key="s.value"
        size="small"
        @click="addSubRule(s)"
      >{{ s.label }}</el-button>
    </div>

    <div v-if="rules.length" class="rule-summary">
      共 {{ totalCount }} 道题
      <span v-if="hasEmptyRule" class="rule-warn">（有规则没填数量，不会抽题）</span>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { Plus } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  categories: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])

// 规则列表在组件内部维护一份。
// 直接改 props.modelValue 会有个坑：父组件的值要等重新渲染才同步回来，
// 连续点两下"添加"（比如先点单选题再点血细胞）第二次会拿旧的空数组，
// 刚加的第一条就被覆盖掉了。
const rules = ref([])

// syncing 用来区分"父组件改的"和"用户在组件里改的"，
// 否则两边互相回写会形成死循环。
const syncing = ref(false)

const snapshot = (list) => JSON.stringify((list || []).map(r => ({
  category: r.category || '',
  type: r.type || '',
  count: Number(r.count) || 0,
})))

watch(
  () => props.modelValue,
  (val) => {
    if (syncing.value) return
    // 内容一致就不动，避免把用户正在输入的内容冲掉
    if (snapshot(val) === snapshot(rules.value)) return
    syncing.value = true
    rules.value = (val || []).map(r => ({ ...r }))
    nextTick(() => { syncing.value = false })
  },
  { immediate: true, deep: true }
)

// 用户改了分类/题型/数量后立刻同步给父组件。
// 以前只在"添加/删除规则"时才提交，导致管理员把 10 道改成 50 道后，
// 父组件发出去的仍是旧的 10 道，抽出来的题数和总分全都不对。
watch(
  rules,
  () => {
    if (syncing.value) return
    emit('update:modelValue', rules.value.map(r => ({ ...r })))
  },
  { deep: true }
)

// 形态学题库里的四个亚类别，管理员按名字选就能直接用
const subCategories = [
  { label: '血细胞', value: '血细胞' },
  { label: '尿沉渣', value: '尿沉渣' },
  { label: '寄生虫', value: '寄生虫' },
  { label: '其他体液', value: '其他体液' },
]

const totalCount = computed(() =>
  rules.value.reduce((sum, r) => sum + (Number(r.count) || 0), 0)
)

const hasEmptyRule = computed(() =>
  rules.value.some((r) => !Number(r.count) || Number(r.count) <= 0)
)

const addRule = (category = '', type = '', count = 10) => {
  rules.value.push({ category, type, count })
}

const addTypeRule = (type) => {
  // 同类型只保留一条，重复点击就是改数量
  const exist = rules.value.find((r) => r.type === type)
  rules.value = rules.value.filter((r) => r.type !== type)
  rules.value.push({
    category: exist?.category || '',
    type,
    count: exist?.count ?? 10,
  })
}

const addSubRule = (s) => {
  const exist = rules.value.find((r) => r.category === s.value)
  rules.value = rules.value.filter((r) => r.category !== s.value)
  rules.value.push({
    category: s.value,
    type: exist?.type || '',
    count: exist?.count ?? 10,
  })
}

const removeRule = (index) => {
  rules.value.splice(index, 1)
}
</script>

<style scoped>
.rule-editor {
  width: 100%;
}
.rule-empty {
  color: #909399;
  font-size: 13px;
  padding: 8px 0;
}
.rule-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.rule-unit {
  color: #606266;
  font-size: 13px;
}
.rule-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 4px;
}
.rule-tip {
  color: #909399;
  font-size: 12px;
}
.rule-summary {
  margin-top: 8px;
  color: #409eff;
  font-size: 13px;
}
.rule-warn {
  color: #e6a23c;
}
</style>
