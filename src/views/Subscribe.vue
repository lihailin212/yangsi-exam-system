<template>
  <div class="subscribe-page">
    <el-card class="status-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>我的订阅</span>
          <el-button size="small" :loading="loading" @click="loadAll">刷新</el-button>
        </div>
      </template>

      <el-alert
        v-if="ent.active && ent.reason === 'trial'"
        type="warning" :closable="false" show-icon
        :title="`免费试用中，${ent.days_left ?? 0} 天后到期`"
        description="试用结束后若仍未加入有效订阅，学习与考试功能将无法使用。成绩记录不受影响。"
        class="mb16" />
      <el-alert
        v-else-if="ent.active && ent.reason === 'organization'"
        type="success" :closable="false" show-icon
        :title="`${org.name} 订阅有效，${ent.days_left ?? 0} 天后到期`"
        class="mb16" />
      <el-alert
        v-else-if="ent.active && ent.reason === 'billing_disabled'"
        type="info" :closable="false" show-icon
        title="当前未开启收费，所有功能正常开放" class="mb16" />
      <el-alert
        v-else-if="ent.reason === 'organization_expired'"
        type="error" :closable="false" show-icon
        title="机构订阅已到期" class="mb16"
        description="学习与考试功能已停用，成绩记录仍可查询。请联系机构管理员续费，或使用下方兑换码续期。" />
      <el-alert
        v-else type="error" :closable="false" show-icon
        title="尚未开通订阅" class="mb16"
        description="学习与考试功能已停用，成绩记录仍可查询。请联系机构管理员开通，或使用下方兑换码。" />

      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="手机号">{{ phone }}</el-descriptions-item>
        <el-descriptions-item label="所属机构">{{ org.name || '未加入机构' }}</el-descriptions-item>
        <el-descriptions-item label="试用到期">{{ fmt(ent.trial_expires_at) || '—' }}</el-descriptions-item>
        <el-descriptions-item label="机构订阅到期">{{ fmt(org.subscription_expires_at) || '—' }}</el-descriptions-item>
        <el-descriptions-item label="机构席位">{{ org.seat_used ?? 0 }} / {{ org.seat_limit ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="机构邀请码">{{ org.invite_code || '—' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="mb16" shadow="never">
      <template #header><span>使用兑换码开通 / 续费</span></template>
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="兑换码">
          <el-input v-model="redeemInput" placeholder="请输入管理员提供的兑换码" clearable
                    style="width: 280px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="redeeming" @click="handleRedeem">立即兑换</el-button>
        </el-form-item>
      </el-form>
      <div class="tip">
        兑换码是给「你所属机构」续期的；没加入机构的话请先用机构邀请码注册，或联系机构管理员把你加入机构。
      </div>
    </el-card>

    <el-card class="mb16" shadow="never">
      <template #header><span>机构套餐</span></template>
      <el-empty v-if="!plans.length" description="暂无可用套餐" />
      <div class="plan-grid">
        <div v-for="p in plans" :key="p.id" class="plan-card">
          <div class="plan-name">{{ p.name }}</div>
          <div class="plan-price">￥{{ yuan(p.price_cents) }}</div>
          <div class="plan-meta">{{ p.seat_limit }} 个席位 · 有效期 {{ p.duration_days }} 天</div>
          <div class="plan-desc">{{ p.description }}</div>
          <el-button type="primary" plain size="small" @click="handleOrder(p)">购买</el-button>
        </div>
      </div>
      <div v-if="contactWechat" class="tip">购买请联系客服微信：{{ contactWechat }}</div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getBillingConfig, getMySubscription, getPlans, redeemCode, createOrder } from '@/api/billing'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const loading = ref(false)
const redeeming = ref(false)
const redeemInput = ref('')
const plans = ref([])
const config = ref({})
const ent = ref({ active: false, reason: '', days_left: 0 })
const org = ref({})

const contactWechat = computed(() => config.value.contact_wechat || '')
const phone = computed(() => authStore.employeeId || '')

const fmt = (v) => {
  if (!v) return ''
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  return d.toLocaleString('zh-CN', { hour12: false })
}
const yuan = (cents) => ((cents || 0) / 100).toFixed(0)

const loadAll = async () => {
  loading.value = true
  try {
    const [me, planRes, cfg] = await Promise.all([
      getMySubscription(), getPlans(), getBillingConfig(),
    ])
    ent.value = me
    org.value = me.organization || {}
    plans.value = planRes.items || []
    config.value = cfg || {}
    // 同步本地权益标记，路由守卫靠它拦截
    authStore.setEntitlement(me.active, me.days_left)
  } catch (e) {
    // 402 说明订阅过期，接口本身已经提示过了
  } finally {
    loading.value = false
  }
}

const handleRedeem = async () => {
  const code = redeemInput.value.trim()
  if (!code) {
    ElMessage.warning('请输入兑换码')
    return
  }
  redeeming.value = true
  try {
    const res = await redeemCode(code)
    ElMessage.success(res.message || '兑换成功')
    redeemInput.value = ''
    await loadAll()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '兑换失败')
  } finally {
    redeeming.value = false
  }
}

const handleOrder = async (plan) => {
  try {
    const res = await createOrder({ plan_id: plan.id })
    ElMessageBox.alert(
      `订单号：${res.order_no}\n金额：￥${yuan(res.amount_cents)}\n${res.pay_url || '请在管理员处完成付款并开通'}`,
      '订单已创建', { confirmButtonText: '知道了' })
  } catch (e) {
    const detail = e?.response?.data?.detail
    ElMessage.warning(typeof detail === 'string' ? detail : '在线支付即将开放，请联系管理员')
  }
}

onMounted(loadAll)
</script>

<style scoped>
.subscribe-page { max-width: 1000px; margin: 0 auto; }
.mb16 { margin-bottom: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.tip { font-size: 12px; color: #909399; line-height: 1.6; margin-top: 6px; }
.plan-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px;
}
.plan-card {
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.plan-name { font-size: 15px; font-weight: 600; color: #303133; }
.plan-price { font-size: 24px; color: #0d7377; font-weight: 700; }
.plan-meta { font-size: 13px; color: #606266; }
.plan-desc { font-size: 12px; color: #909399; min-height: 32px; }
</style>
