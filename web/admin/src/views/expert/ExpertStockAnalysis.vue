<template>
  <div class="expert-stock-page">
    <!-- 顶部全局研判栏 -->
    <div class="global-judge-bar">
      <div class="judge-item"><div class="label">当前市场周期</div><div class="value cycle-value">{{ globalCycle.cycleName }}</div></div>
      <div class="judge-item"><div class="label">推荐投资风格</div><div class="value style-value">{{ globalCycle.styleName }}</div></div>
      <div class="judge-item"><div class="label">建议仓位区间</div><div class="value pos-value">{{ globalCycle.positionRange }}</div></div>
      <div class="judge-item"><div class="label">市场风险等级</div><el-tag :type="globalCycle.riskType">{{ globalCycle.riskName }}</el-tag></div>
      <div class="judge-btn-group">
        <el-button type="primary" @click="refreshAllData">一键刷新前瞻数据</el-button>
        <el-button @click="generateAiReport">生成专家前瞻报告</el-button>
      </div>
    </div>

    <!-- Tab核心功能面板 -->
    <el-tabs v-model="activeTab" type="card" class="mt16">
      <el-tab-pane label="宏观周期择时" name="macro">
        <MacroCyclePanel :macro-data="macroData" />
      </el-tab-pane>
      <el-tab-pane label="行业前瞻赛道" name="industry">
        <IndustryTrackPanel :industry-list="industryTopList" />
      </el-tab-pane>
      <el-tab-pane label="产业链弹性推演" name="chain">
        <IndustryChainPanel />
      </el-tab-pane>
      <el-tab-pane label="专家多因子选股" name="stock">
        <StockFactorPanel :stock-list="expertStockList" />
      </el-tab-pane>
      <el-tab-pane label="AI投研报告" name="report">
        <AiReportPanel :report-content="aiReportContent" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import MacroCyclePanel from './MacroCyclePanel.vue'
import IndustryTrackPanel from './IndustryTrackPanel.vue'
import IndustryChainPanel from '../../views/IndustryChainPanel.vue'
import StockFactorPanel from './StockFactorPanel.vue'
import AiReportPanel from './AiReportPanel.vue'

const activeTab = ref('macro')

const globalCycle = ref({
  cycleName: '震荡偏多 · 结构牛', styleName: '成长风格 + 均衡配置',
  positionRange: '60%~80%', riskType: 'warning', riskName: '中等风险',
})

const macroData = ref({
  liquidity: '中性偏宽', riskAppetite: '回暖', rateTrend: '下行通道',
  fundFlow: '北向净流入+85亿 ｜ 两融回升', cycleScore: 72,
})

const industryTopList = ref([
  { rank: 1, name: 'AI算力', score: 92, trend: 'up', signal: '强推', reason: '算力需求爆发+政策加持+国产替代' },
  { rank: 2, name: '机器人', score: 88, trend: 'up', signal: '推荐', reason: '产业化落地加速+龙头扩产' },
  { rank: 3, name: '半导体设备', score: 85, trend: 'up', signal: '推荐', reason: '国产化率提升+资本开支上行' },
  { rank: 4, name: '新能源车', score: 78, trend: 'up', signal: '关注', reason: '渗透率突破+出海逻辑强化' },
  { rank: 5, name: '医药生物', score: 72, trend: 'flat', signal: '关注', reason: '估值修复+创新药管线兑现' },
])

const expertStockList = ref([
  { code: '688256', name: '寒武纪', sector: 'AI算力', score: 95, rating: '强推', logic: '国产GPU龙头，算力基建核心标的' },
  { code: '300308', name: '中际旭创', sector: 'AI算力', score: 93, rating: '强推', logic: '800G光模块全球份额领先' },
  { code: '300750', name: '宁德时代', sector: '新能源', score: 88, rating: '推荐', logic: '动力电池全球龙头，海外份额提升' },
  { code: '002472', name: '双环传动', sector: '机器人', score: 85, rating: '推荐', logic: 'RV减速器国产突破，人形机器人弹性标的' },
  { code: '688981', name: '中芯国际', sector: '半导体', score: 82, rating: '推荐', logic: '晶圆代工龙头，成熟制程份额提升' },
])

const aiReportContent = ref('')

async function refreshAllData() {
  try {
    const { data } = await axios.get('/api/v1/expert/overview')
    if (data.data) {
      macroData.value = data.data.macro || macroData.value
      industryTopList.value = data.data.industries || industryTopList.value
      expertStockList.value = data.data.stocks || expertStockList.value
    }
  } catch { /* use defaults */ }
}

async function generateAiReport() {
  aiReportContent.value = '⏳ 豆包 AI 正在生成专家前瞻报告...'
  try {
    const { data } = await axios.post('/api/v1/llm/chat', {
      prompt: `当前宏观环境：${macroData.value.liquidity}，${macroData.value.rateTrend}。推荐赛道：${industryTopList.value.slice(0,3).map(i=>i.name).join('、')}。请生成一份500字的A股投资策略前瞻报告。`,
      model_type: 'doubao', temperature: 0.3,
    })
    aiReportContent.value = data.data?.content || '报告生成完成'
  } catch { aiReportContent.value = 'AI 服务暂不可用，请稍后重试' }
}

onMounted(() => refreshAllData())
</script>

<style scoped>
.expert-stock-page { padding: 16px; }
.global-judge-bar { display: flex; align-items: center; gap: 24px; background: linear-gradient(135deg, #1e293b, #0f172a); border-radius: 12px; padding: 16px 24px; color: #e2e8f0; }
.judge-item .label { font-size: 11px; color: #94a3b8; margin-bottom: 4px; }
.judge-item .value { font-size: 15px; font-weight: 700; }
.cycle-value { color: #38bdf8; } .style-value { color: #34d399; } .pos-value { color: #fbbf24; }
.judge-btn-group { margin-left: auto; display: flex; gap: 8px; }
.mt16 { margin-top: 16px; }
</style>
