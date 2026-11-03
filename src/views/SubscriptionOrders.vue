<template>
  <div class="page">
    <el-tabs v-model="tab">
      <!-- 开通记录 -->
      <el-tab-pane label="开通记录" name="orders">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>开通记录</span>
              <el-button size="small" @click="loadOrders">刷新</el-button>
            </div>
          </template>
          <el-table :data="orders" v-loading="loadingOrders" border size="small">
            <el-table-column prop="order_no" label="订单号" width="220" />
            <el-table-column prop="organization_name" label="机构" width="140" />
            <el-table-column prop="plan_name" label="套餐" width="130" />
            <el-table-column prop="seat_limit" label="席位" width="80" />
            <el-table-column prop="duration_days" label="时长(天)" width="100" />
            <el-table-column label="金额" width="100">
              <template #default="{ row }">￥{{ (row.amount_cents / 100).toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="渠道" width="110">
              <template #default="{ row }">
                <el-tag size="small">{{ CHANNEL[row.channel] || row.channel }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="90" />
            <el-table-column label="开通时间" width="180">
              <template #default="{ row }">{{ fmt(row.paid_at || row.created_at) }}</template>
            </el-table-column>
            <el-table-column prop="note" label="备注" min-width="140" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 兑换码 -->
      <el-tab-pane label="兑换码" name="codes">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>兑换码</span>
              <div>
                <el-button size="small" @click="loadCodes">刷新</el-button>
                <el-button size="small" type="primary" @click="genVisible = true">批量生成</el-button>
              </div>
            </div>
          </template>

          <div class="filters">
            <el-select v-model="codeFilter.status" placeholder="状态" clearable style="width: 120px"
                       @change="loadCodes">
              <el-option label="未使用" value="unused" />
              <el-option label="已使用" value="used" />
              <el-option label="已作废" value="void" />
            </el-select>
          </div>

          <el-table :data="codes" v-loading="loadingCodes" border size="small">
            <el-table-column prop="code" label="兑换码" width="180">
              <template #default="{ row }">
                <span class="mono">{{ row.code }}</span>
                <el-button size="small" text @click="copy(row.code)">复制</el-button>
              </template>
            </el-table-column>
            <el-table-column prop="plan_name" label="套餐" width="120" />
            <el-table-column prop="duration_days" label="时长(天)" width="100" />
            <el-table-column prop="seat_limit" label="席位" width="80" />
            <el-table-column label="金额" width="100">
              <template #default="{ row }">￥{{ (row.amount_cents / 100).toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="限用机构" width="110">
              <template #default="{ row }">{{ row.organization_id || '通用' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="row.status === 'used' ? 'success' : (row.status === 'void' ? 'info' : 'warning')">
                  {{ row.status === 'used' ? '已使用' : (row.status === 'void' ? '已作废' : '未使用') }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="过期时间" width="180">
              <template #default="{ row }">{{ fmt(row.expires_at) || '不过期' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button v-if="row.status === 'unused'" size="small" text @click="voidIt(row)">作废</el-button>
                <el-button v-if="row.status === 'unused'" size="small" text type="primary" @click="openRedeem(row)">代兑换</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 机构订阅 -->
      <el-tab-pane label="机构订阅" name="orgs">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>机构订阅总览</span>
              <el-button size="small" @click="loadOrgs">刷新</el-button>
            </div>
          </template>
          <el-table :data="orgs" v-loading="loadingOrgs" border size="small">
            <el-table-column prop="name" label="机构" width="160" />
            <el-table-column label="席位" width="100">
              <template #default="{ row }">{{ row.seat_used }} / {{ row.seat_limit }}</template>
            </el-table-column>
            <el-table-column label="订阅到期" width="200">
              <template #default="{ row }">{{ fmt(row.subscription_expires_at) || '未开通' }}</template>
            </el-table-column>
            <el-table-column prop="subscription_plan_code" label="套餐" width="130" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="row.is_active ? 'success' : 'info'">
                  {{ row.is_active ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="contact_name" label="联系人" width="120" />
            <el-table-column prop="contact_phone" label="联系电话" width="140" />
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 批量生成 -->
    <el-dialog v-model="genVisible" title="批量生成兑换码" width="460px">
      <el-form :model="genForm" label-width="110px">
        <el-form-item label="套餐">
          <el-select v-model="genForm.plan_id" clearable placeholder="选择套餐">
            <el-option v-for="p in plans" :key="p.id"
                       :label="`${p.name}（${p.seat_limit}席/${p.duration_days}天）`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="有效期(天)">
          <el-input-number v-model="genForm.duration_days" :min="0" :max="3650" />
        </el-form-item>
        <el-form-item label="席位数">
          <el-input-number v-model="genForm.seat_limit" :min="0" :max="9999" />
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="genForm.count" :min="1" :max="500" />
        </el-form-item>
        <el-form-item label="码有效期(天)">
          <el-input-number v-model="genForm.valid_days" :min="0" :max="365" />
          <span class="tip">0 = 兑换码永不过期</span>
        </el-form-item>
        <el-form-item label="限用机构">
          <el-select v-model="genForm.organization_id" clearable placeholder="不选 = 通用码">
            <el-option v-for="o in orgs" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="genVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleGenerate">生成</el-button>
      </template>
    </el-dialog>

    <!-- 生成结果 -->
    <el-dialog v-model="resultVisible" title="生成结果" width="520px">
      <el-input type="textarea" :rows="12" :model-value="generated.join('\n')" readonly />
      <template #footer>
        <el-button @click="copyAll">复制全部</el-button>
        <el-button type="primary" @click="resultVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 代兑换 -->
    <el-dialog v-model="redeemVisible" title="代机构兑换" width="400px">
      <el-form :model="redeemForm" label-width="100px">
        <el-form-item label="兑换码">
          <el-input v-model="redeemForm.code" disabled />
        </el-form-item>
        <el-form-item label="机构">
          <el-select v-model="redeemForm.organization_id" style="width: 100%">
            <el-option v-for="o in orgs" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="redeemVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleRedeemFor">确认兑换</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getOrders, getCodes, generateCodes, voidCode, adminRedeemCode, getAdminPlans } from '@/api/billing'
import { getOrganizations } from '@/api/organizations'

const CHANNEL = { manual: '后台开通', redemption_code: '兑换码', wechat: '微信支付' }

const tab = ref('orders')
const orders = ref([])
const codes = ref([])
const orgs = ref([])
const plans = ref([])
const loadingOrders = ref(false)
const loadingCodes = ref(false)
const loadingOrgs = ref(false)
const saving = ref(false)

const genVisible = ref(false)
const resultVisible = ref(false)
const redeemVisible = ref(false)
const generated = ref([])
const codeFilter = reactive({ status: '' })
const genForm = reactive({ plan_id: null, duration_days: 0, seat_limit: 0, count: 10, valid_days: 0, organization_id: null })
const redeemForm = reactive({ code: '', organization_id: null })

const fmt = (v) => {
  if (!v) return ''
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  return d.toLocaleString('zh-CN', { hour12: false })
}

const copy = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch (e) {
    ElMessage.warning('复制失败，请手动选中')
  }
}
const copyAll = () => copy(generated.value.join('\n'))

const loadOrders = async () => {
  loadingOrders.value = true
  try {
    const res = await getOrders({ limit: 100 })
    orders.value = res.items || []
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载失败')
  } finally {
    loadingOrders.value = false
  }
}

const loadCodes = async () => {
  loadingCodes.value = true
  try {
    const res = await getCodes({ limit: 100, status: codeFilter.status || undefined })
    codes.value = res.items || []
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载失败')
  } finally {
    loadingCodes.value = false
  }
}

const loadOrgs = async () => {
  loadingOrgs.value = true
  try {
    const res = await getOrganizations()
    orgs.value = res.items || []
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载失败')
  } finally {
    loadingOrgs.value = false
  }
}

const loadPlans = async () => {
  try {
    const res = await getAdminPlans()
    plans.value = res.items || []
  } catch (e) { /* 忽略 */ }
}

const handleGenerate = async () => {
  if (!genForm.plan_id && !genForm.duration_days) {
    ElMessage.warning('请选择套餐或填写有效期天数')
    return
  }
  saving.value = true
  try {
    const res = await generateCodes({ ...genForm })
    generated.value = res.codes || []
    resultVisible.value = true
    genVisible.value = false
    loadCodes()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '生成失败')
  } finally {
    saving.value = false
  }
}

const voidIt = async (row) => {
  try {
    await voidCode(row.id)
    ElMessage.success('已作废')
    loadCodes()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '作废失败')
  }
}

const openRedeem = (row) => {
  redeemForm.code = row.code
  redeemForm.organization_id = row.organization_id || (orgs.value[0]?.id ?? null)
  redeemVisible.value = true
}

const handleRedeemFor = async () => {
  saving.value = true
  try {
    await adminRedeemCode({ code: redeemForm.code, organization_id: redeemForm.organization_id })
    ElMessage.success('已兑换并开通')
    redeemVisible.value = false
    loadCodes()
    loadOrders()
    loadOrgs()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '兑换失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadOrders()
  loadCodes()
  loadOrgs()
  loadPlans()
})
</script>

<style scoped>
.page { max-width: 1400px; margin: 0 auto; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.filters { margin-bottom: 10px; }
.mono { font-family: monospace; letter-spacing: 1px; }
.tip { font-size: 12px; color: #909399; margin-left: 8px; }
</style>
