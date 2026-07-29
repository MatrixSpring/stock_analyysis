<template>
  <div class="industry-chain-panel">
    <!-- 事件选择 + 推演控制 -->
    <div class="control-card">
      <div class="control-left">
        <div class="title">动态事件推演引擎</div>
        <el-select v-model="selectEvent" placeholder="选择宏观/产业事件" style="width:360px;margin-right:12px" size="small">
          <el-option label="美联储降息周期开启" value="us_rate_cut" />
          <el-option label="国内流动性宽松加码" value="cn_loose" />
          <el-option label="大宗商品涨价周期" value="commodity_up" />
          <el-option label="高端制造进口限制升级" value="tech_sanction" />
          <el-option label="新能源产业补贴政策落地" value="new_energy_policy" />
          <el-option label="出口地缘贸易利好释放" value="trade_benefit" />
        </el-select>
        <el-button type="primary" size="small" @click="startChainSim" :loading="simLoading">开始动态推演</el-button>
        <el-button size="small" @click="resetChart">重置图谱</el-button>
      </div>
    </div>

    <!-- 多因子图层开关 -->
    <div class="layer-card mt16">
      <div class="layer-title">多因子可视化图层（叠加展示）</div>
      <el-checkbox-group v-model="activeLayerList" size="small">
        <el-checkbox label="policy">产业政策图层</el-checkbox>
        <el-checkbox label="game">行业博弈图层</el-checkbox>
        <el-checkbox label="sentiment">舆情情绪图层</el-checkbox>
        <el-checkbox label="capital">资金压力图层</el-checkbox>
        <el-checkbox label="geo">地缘政治图层</el-checkbox>
      </el-checkbox-group>
    </div>

    <!-- 图谱 + 溯源日志 -->
    <el-row :gutter="16" class="mt16">
      <el-col :span="16">
        <div class="chart-main-card">
          <div class="chart-title">产业链动态传导图谱（含层级/属性/传导强度）</div>
          <div ref="chainChartRef" class="chart-container"></div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="log-card">
          <div class="chart-title">传导过程溯源日志（中间博弈过程）</div>
          <div class="log-content">
            <div v-for="(item, idx) in traceLogList" :key="idx" class="log-item" :class="item.type">
              <span class="time">{{ item.time }}</span><span class="text">{{ item.text }}</span>
            </div>
            <div v-if="!traceLogList.length" class="empty-tip">请启动事件推演，查看产业链传导过程</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 节点属性 + 三级穿透 -->
    <el-row :gutter="16" class="mt16">
      <el-col :span="12">
        <div class="attr-card">
          <div class="chart-title">当前节点量化属性详情</div>
          <div v-if="curNodeInfo.id" class="attr-content">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="节点名称">{{ curNodeInfo.name }}</el-descriptions-item>
              <el-descriptions-item label="所属层级">{{ curNodeInfo.layer }}</el-descriptions-item>
              <el-descriptions-item label="供需属性">{{ curNodeInfo.supplyDemand }}</el-descriptions-item>
              <el-descriptions-item label="传导弹性">{{ curNodeInfo.elastic }}</el-descriptions-item>
              <el-descriptions-item label="壁垒类型">{{ curNodeInfo.barrier }}</el-descriptions-item>
              <el-descriptions-item label="风险等级">{{ curNodeInfo.risk }}</el-descriptions-item>
              <el-descriptions-item label="资金状态">{{ curNodeInfo.capital }}</el-descriptions-item>
              <el-descriptions-item label="综合得分">{{ curNodeInfo.score }}</el-descriptions-item>
            </el-descriptions>
          </div>
          <div v-else class="empty-tip">点击图谱节点查看详细属性</div>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="stock-chain-card">
          <div class="chart-title">三级穿透：关联上市公司传导列表</div>
          <el-table :data="stockChainList" border stripe size="small" max-height="260">
            <el-table-column prop="code" label="代码" width="80" align="center"/>
            <el-table-column prop="name" label="公司" width="100"/>
            <el-table-column prop="relation" label="传导关系" width="110"/>
            <el-table-column prop="effect" label="影响" width="90" align="center">
              <template #default="s"><el-tag :type="s.row.effectType" size="small">{{ s.row.effect }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="logic" label="传导逻辑" min-width="180"/>
          </el-table>
        </div>
      </el-col>
    </el-row>

    <!-- 推演结论 -->
    <div class="result-card mt16">
      <div class="chart-title">📊 事件综合推演结论</div>
      <p class="result-text">{{ simulateResult }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'

const selectEvent = ref('')
const simLoading = ref(false)
const activeLayerList = ref(['policy', 'game', 'sentiment', 'capital', 'geo'])
const chainChartRef = ref(null)
let chainChart = null
const traceLogList = ref([])
const curNodeInfo = ref({})
const stockChainList = ref([])
const simulateResult = ref('暂无推演数据，请选择产业/宏观事件，点击开始动态推演。')

const getBaseNodes = () => [
  { id: 1, name: '上游原材料/核心资源', layer: '上游层', category: 0 },
  { id: 2, name: '核心辅料/关键材料', layer: '上游层', category: 0 },
  { id: 3, name: '核心零部件/模组', layer: '中游层', category: 1 },
  { id: 4, name: '整机制造/集成代工', layer: '中游层', category: 1 },
  { id: 5, name: 'ToB工业应用', layer: '下游层', category: 2 },
  { id: 6, name: 'ToC终端消费', layer: '下游层', category: 2 },
  { id: 7, name: '设备/算力/渠道配套', layer: '配套层', category: 3 },
]

const getBaseLinks = () => [
  { source: 1, target: 3, value: '成本传导', elastic: 0.85 },
  { source: 2, target: 3, value: '材料支撑', elastic: 0.75 },
  { source: 3, target: 4, value: '部件供给', elastic: 0.90 },
  { source: 4, target: 5, value: '终端供货', elastic: 0.80 },
  { source: 4, target: 6, value: '消费供给', elastic: 0.82 },
  { source: 7, target: 4, value: '配套支撑', elastic: 0.70 },
]

const getBaseOption = () => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c}' },
  legend: { show: true, data: ['上游原材料', '中游制造', '下游应用', '配套服务'], bottom: 10 },
  series: [{
    type: 'graph', layout: 'force', force: { repulsion: 180, edgeLength: 120 }, roam: true,
    label: { show: true, fontSize: 11 }, edgeLabel: { show: true, fontSize: 9, formatter: '{c}' },
    categories: [{ name: '上游原材料', itemStyle: { color: '#38bdf8' } }, { name: '中游制造', itemStyle: { color: '#fbbf24' } }, { name: '下游应用', itemStyle: { color: '#34d399' } }, { name: '配套服务', itemStyle: { color: '#a78bfa' } }],
    nodes: getBaseNodes(), links: getBaseLinks(), lineStyle: { color: '#999', width: 2, curveness: 0.2 },
  }],
})

function initChart() {
  if (!chainChartRef.value) return
  chainChart = echarts.init(chainChartRef.value)
  chainChart.setOption(getBaseOption())
  chainChart.on('click', p => { if (p.dataType === 'node') { curNodeInfo.value = p.data } })
  window.addEventListener('resize', () => chainChart?.resize())
}

function pushLog(type, text) {
  traceLogList.value.push({ type, time: new Date().toLocaleTimeString(), text })
}

function updateChart(data) {
  const opt = chainChart.getOption()
  opt.series[0].nodes = data.nodes.map(n => {
    const s = n.score || 50
    return { ...n, itemStyle: { color: s > 65 ? '#67c23a' : s < 40 ? '#f56c6c' : '#909399' }, symbolSize: 20 + s / 3 }
  })
  opt.series[0].links = data.links.map(l => ({ ...l, lineStyle: { width: l.elastic > 0.7 ? 4 : 3, color: l.elastic > 0 ? '#67c23a' : '#f56c6c', curveness: 0.2 } }))
  chainChart.setOption(opt)
}

async function startChainSim() {
  if (!selectEvent.value) return
  simLoading.value = true; traceLogList.value = []; stockChainList.value = []; curNodeInfo.value = {}
  pushLog('system', '开始事件推演，启动多因子博弈计算...')

  try {
    const { data } = await axios.post('/api/v1/expert/chain/sim', { eventKey: selectEvent.value, layers: activeLayerList.value })
    pushLog('policy', '解析产业政策阶段影响：' + (data.policyDesc || ''))
    pushLog('game', '行业博弈迭代：产能/库存/价格格局发生变化')
    pushLog('sentiment', '舆情情绪边际变化：' + (data.sentimentDesc || ''))
    pushLog('capital', '大资金流向重分配：赛道资金迁移完成')
    pushLog('geo', '地缘风险冲击修正：对外依赖节点风险重定价')
    updateChart(data.graphData)
    stockChainList.value = data.stockList || []
    simulateResult.value = data.resultDesc || ''
    pushLog('success', '多因子博弈推演完成')
  } catch (e) { pushLog('error', '推演请求异常，请重试') }
  simLoading.value = false
}

function resetChart() {
  selectEvent.value = ''; traceLogList.value = []; stockChainList.value = []; curNodeInfo.value = {}
  simulateResult.value = '暂无推演数据，请选择产业/宏观事件，点击开始动态推演。'
  chainChart?.setOption(getBaseOption())
}

onMounted(() => nextTick(initChart))
</script>

<style scoped>
.control-card, .layer-card, .attr-card, .stock-chain-card, .result-card, .log-card { background: #fff; border-radius: 8px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
.control-left { display: flex; align-items: center; }
.title { font-size: 14px; font-weight: bold; margin-right: 16px; color: #333; }
.layer-title { font-size: 14px; font-weight: bold; margin-bottom: 12px; }
.chart-container { width: 100%; height: 420px; }
.chart-title { font-size: 14px; font-weight: bold; margin-bottom: 12px; color: #333; }
.log-content { height: 360px; overflow-y: auto; border: 1px solid #eee; border-radius: 6px; padding: 10px; }
.log-item { margin-bottom: 8px; font-size: 12px; line-height: 1.6; padding-bottom: 8px; border-bottom: 1px dashed #f5f5f5; }
.log-item.system { color: #409eff; } .log-item.policy { color: #67c23a; } .log-item.game { color: #e6a23c; }
.log-item.sentiment { color: #9c88ff; } .log-item.capital { color: #f56c6c; } .log-item.geo { color: #333; }
.log-item.success { color: #67c23a; font-weight: bold; } .log-item.error { color: #f56c6c; }
.log-item .time { color: #999; margin-right: 6px; }
.empty-tip { text-align: center; color: #999; font-size: 12px; padding: 20px 0; }
.attr-content, .result-text { font-size: 13px; color: #333; line-height: 1.8; }
.result-text { text-indent: 2em; }
.mt16 { margin-top: 16px; }
</style>
