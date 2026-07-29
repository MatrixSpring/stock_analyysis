<template>
  <div class="country-detail-wrap">
    <!-- 头部 -->
    <div class="header">
      <h2>{{ entityData?.name || '--' }}</h2>
      <div class="score-tag">
        <el-tag :type="scoreTagType" size="large">
          脆弱性得分：{{ entityData?.riskScore ?? '--' }}
        </el-tag>
        <span class="risk-desc">{{ riskText }}</span>
      </div>
    </div>

    <el-divider />

    <!-- 一、主权债务压力 -->
    <div class="panel-block">
      <div class="panel-title">📊 主权债务压力</div>
      <el-row :gutter="[12, 8]">
        <el-col :span="12"><div class="item">政府债务/GDP：{{ getVal('debt_gdp') }}%</div></el-col>
        <el-col :span="12"><div class="item">外债/外汇储备：{{ getVal('external_debt_reserve') }}%</div></el-col>
        <el-col :span="12"><div class="item">短期外债占比：{{ getVal('short_debt_ratio') }}%</div></el-col>
        <el-col :span="12"><div class="item">主权CDS：{{ getVal('cds_spread') }} bp</div></el-col>
        <el-col :span="24"><div class="item">财政赤字率：{{ getVal('fiscal_deficit') }}%</div></el-col>
      </el-row>
    </div>

    <!-- 二、国际收支 & 外贸 -->
    <div class="panel-block">
      <div class="panel-title">🌐 国际收支与外贸</div>
      <el-row :gutter="[12, 8]">
        <el-col :span="12"><div class="item">经常账户/GDP：{{ getVal('ca_gdp') }}%</div></el-col>
        <el-col :span="12"><div class="item">贸易差额：{{ getVal('trade_balance') }}</div></el-col>
        <el-col :span="12"><div class="item">FDI净流入：{{ getVal('fdi_flow') }}</div></el-col>
        <el-col :span="12"><div class="item">跨境证券资金：{{ getVal('sec_flow') }}</div></el-col>
      </el-row>
    </div>

    <!-- 三、利率汇率 & 国内流动性 -->
    <div class="panel-block">
      <div class="panel-title">💹 利率与汇率体系</div>
      <el-row :gutter="[12, 8]">
        <el-col :span="12"><div class="item">政策基准利率：{{ getVal('policy_rate') }}%</div></el-col>
        <el-col :span="12"><div class="item">实际利率：{{ getVal('real_rate') }}%</div></el-col>
        <el-col :span="12"><div class="item">CPI通胀：{{ getVal('cpi') }}%</div></el-col>
        <el-col :span="12"><div class="item">名义有效汇率：{{ getVal('neer') }}</div></el-col>
      </el-row>
    </div>

    <!-- 四、外汇储备 & 黄金 -->
    <div class="panel-block">
      <div class="panel-title">🏅 外汇储备 & 黄金</div>
      <el-row :gutter="[12, 8]">
        <el-col :span="12"><div class="item">外汇储备总量：{{ getVal('fx_reserve') }}</div></el-col>
        <el-col :span="12"><div class="item">外储环比变动：{{ getVal('fx_reserve_mom') }}</div></el-col>
        <el-col :span="12"><div class="item">官方黄金储备：{{ getVal('gold_stock') }}吨</div></el-col>
        <el-col :span="12"><div class="item">近半年黄金增减仓：{{ getVal('gold_half_year') }}吨</div></el-col>
      </el-row>
    </div>

    <!-- 五、沙盘推演资产影响 -->
    <div v-if="isSimulationMode" class="panel-block">
      <div class="panel-title">🎯 推演情景 — 资产影响预判</div>
      <div class="impact-block">
        <div class="positive">
          <div class="label">✅ 受益方向/板块</div>
          <div class="text">{{ impactData?.benefit || '暂无推演数据' }}</div>
        </div>
        <div class="negative">
          <div class="label">⚠️ 承压方向/板块</div>
          <div class="text">{{ impactData?.pressure || '暂无推演数据' }}</div>
        </div>
      </div>
    </div>

    <el-divider />

    <!-- 底部操作 -->
    <div class="btn-group">
      <el-button type="primary" @click="triggerAiAnalysis">🤖 AI宏观解读（豆包API）</el-button>
      <el-button @click="refreshData">🔄 刷新指标</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  entityData: { type: Object, default: () => null },
  isSimulationMode: { type: Boolean, default: false },
  impactData: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['ai-analysis', 'refresh'])

const getVal = (key) => {
  if (!props.entityData?.indicators) return '--'
  return props.entityData.indicators[key] ?? '--'
}

const riskScore = computed(() => props.entityData?.riskScore || 0)

const scoreTagType = computed(() => {
  const s = riskScore.value
  if (s <= 35) return 'success'
  if (s <= 60) return 'warning'
  if (s <= 80) return ''
  return 'danger'
})

const riskText = computed(() => {
  const s = riskScore.value
  if (s <= 35) return '货币基本面稳固'
  if (s <= 60) return '中等资金压力，持续跟踪'
  if (s <= 80) return '高脆弱，贬值风险上升'
  return '高危，警惕债务/汇率危机'
})

const triggerAiAnalysis = () => emit('ai-analysis', props.entityData, props.impactData)
const refreshData = () => emit('refresh', props.entityData?.id)
</script>

<style scoped>
.country-detail-wrap { padding: 8px 12px; height: 100%; overflow-y: auto; }
.header h2 { margin: 4px 0; font-size: 18px; }
.score-tag { display: flex; align-items: center; gap: 10px; }
.risk-desc { font-size: 13px; color: #666; }
.panel-block { margin-bottom: 16px; }
.panel-title { font-weight: bold; font-size: 15px; margin-bottom: 10px; }
.item { font-size: 13px; color: #333; padding: 4px 0; }
.impact-block { border: 1px solid #e5e7eb; border-radius: 6px; padding: 10px; }
.positive { margin-bottom: 8px; }
.positive .label { color: #00b42a; font-weight: 500; }
.negative .label { color: #ff7d00; font-weight: 500; }
.text { font-size: 13px; margin-top: 4px; line-height: 1.6; }
.btn-group { display: flex; gap: 10px; }
</style>
