<template>
  <div class="macro-monitor-wrap">
    <div class="header-bar">
      <el-space size="large">
        <div class="title">全球货币稳定性与跨境流动性沙盘</div>
        <el-radio-group v-model="activeTab" size="default">
          <el-radio-button label="monitor">实时监测看板</el-radio-button>
          <el-radio-button label="simulation">宏观情景推演沙盘</el-radio-button>
        </el-radio-group>
        <el-button type="primary" @click="callAiReport">🤖 AI宏观解读</el-button>
        <el-button @click="exportReport">📥 导出情景报告</el-button>
      </el-space>
    </div>

    <div class="main-row">
      <!-- 左侧面板 -->
      <div class="left-panel">
        <template v-if="activeTab === 'monitor'">
          <div class="panel-title">经济体筛选</div>
          <el-checkbox-group v-model="selectCountryList" size="small">
            <el-checkbox v-for="c in countryList" :key="c.id" :label="c.id">{{ c.flag }} {{ c.name }}</el-checkbox>
          </el-checkbox-group>
          <el-divider/>
          <div class="panel-title">风险预警阈值</div>
          <el-slider v-model="warningThreshold" :max="100" show-input size="small"/>
          <div class="tip">高于阈值经济体自动高亮预警</div>
        </template>

        <template v-if="activeTab === 'simulation'">
          <div class="panel-title">📌 拖拽宏观冲击事件（点击目标节点投放）</div>
          <div class="drag-event-item" v-for="ev in macroEventList" :key="ev.eventId || ev.id"
               draggable="true" @dragstart="onDragEvent($event, ev)"
               :style="{borderLeft: '4px solid ' + (ev.direction === 'positive' ? '#22c55e' : '#ef4444')}">
            <el-tag :type="ev.direction === 'positive' ? 'success' : 'danger'" size="small">{{ ev.title || ev.eventName }}</el-tag>
          </div>
          <el-divider/>
          <div class="panel-title">🎮 沙盘控制</div>
          <el-button type="primary" @click="startSim" :disabled="!simRootId || simRunning" style="width:100%">▶ 开始推演</el-button>
          <el-button @click="stopSim" :disabled="!simRunning" style="width:100%;margin-top:6px">⏸ 暂停</el-button>
          <el-button type="danger" @click="resetSim" style="width:100%;margin-top:6px">🗑 清空推演</el-button>
          <el-divider/>
          <div class="panel-title">⏱ 时间轴 ({{ simProgress }}/{{ simTotalStep }})</div>
          <el-slider v-model="simProgress" :max="simTotalStep" :step="1" @change="seekStep" size="small"/>
          <div v-if="simRootId" class="tip">冲击源：{{ simRootId }}</div>
        </template>
      </div>

      <!-- 中央画布 -->
      <div class="center-container">
        <div v-if="activeTab === 'monitor'" class="monitor-view">
          <WorldMap @country-dblclick="jumpToSim" />
        </div>
        <div v-if="activeTab === 'simulation'" class="sim-view">
          <div ref="graphRef" class="g6-canvas"></div>
        </div>
      </div>

      <!-- 右侧详情抽屉 -->
      <el-drawer v-model="showDetail" direction="rtl" size="380px" title="经济体详情">
        <CountryDetail
          :entity-data="currentEntity"
          :is-simulation-mode="activeTab === 'simulation'"
          :impact-data="simImpactResult"
          @ai-analysis="handleAiCall"
          @refresh="reloadEntity"
        />
      </el-drawer>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import WorldMap from './WorldMap.vue'
import CountryDetail from './CountryDetail.vue'

const activeTab = ref('monitor')
const showDetail = ref(false)
const currentEntity = ref(null)
const warningThreshold = ref(60)
const selectCountryList = ref(['USA', 'CN', 'JP', 'DE', 'IN'])
const countryList = ref([])

// 沙盘
const graphRef = ref(null)
let graph = null, animTimer = null
const simRunning = ref(false), simRootId = ref(null), simProgress = ref(0), simTotalStep = ref(6)
const macroEventList = ref([]), simImpactResult = ref({})
let simPathList = [], dragEventData = null

async function loadCountries() {
  try { const { data } = await axios.get('/api/v1/macro/countries'); countryList.value = data.data || [] }
  catch { /* use static */ }
}
async function loadEvents() {
  try { const { data } = await axios.get('/api/v1/macro/sim/events'); macroEventList.value = Array.isArray(data) ? data : data.data || [] }
  catch { /* use static */ }
}

// G6 沙盘
function initG6() {
  import('@antv/g6').then(({ Graph }) => {
    const c = graphRef.value
    graph = new Graph({
      container: c, width: c.clientWidth, height: c.clientHeight,
      layout: { type: 'force', linkDistance: 150, preventOverlap: true, nodeSpacing: 60 },
      defaultNode: { size: 40, labelCfg: { position: 'bottom', style: { fontSize: 11, fill: '#e2e8f0' } } },
      defaultEdge: { type: 'line', style: { stroke: '#666', lineWidth: 1, endArrow: { path: 'M 0,0 L 6,3 L 6,-3 Z', fill: '#aaa' } } },
      modes: { default: ['drag-node', 'drag-canvas', 'zoom-canvas'] },
      fitView: true, animate: true,
    })
    loadGraph()
    graph.on('node:click', evt => {
      const m = evt.item.getModel()
      if (dragEventData) { simRootId.value = m.id; ElMessage.success(`冲击源：${m.label}`); dragEventData = null }
      else { currentEntity.value = countryList.value.find(c => c.id === m.id) || m; showDetail.value = true }
    })
  }).catch(() => ElMessage.warning('请 npm install @antv/g6'))
}

async function loadGraph() {
  try {
    const { data } = await axios.get('/api/v1/macro/sim/graph')
    const g = data.data || data
    const nodes = (g.nodes || []).map(n => ({
      ...n, type: n.nodeType === 'country' ? 'circle' : 'rect',
      style: { fill: n.riskScore ? (n.riskScore <= 35 ? '#22c55e' : n.riskScore <= 60 ? '#fbbf24' : '#ef4444') : '#748ffc' },
    }))
    graph?.data({ nodes, edges: g.edges || [] }); graph?.render()
  } catch {}
}

// 推演逻辑（调用后端 BFS）
async function startSim() {
  if (!simRootId.value || simRunning.value) return
  resetSim(); simRunning.value = true; simProgress.value = 0
  try {
    const { data } = await axios.post('/api/v1/macro/sim/calcPath', { rootNodeId: simRootId.value, baseStrength: 0.8, minCoeffFilter: 0.1, maxLevel: 5 })
    simPathList = Array.isArray(data) ? data : data.data || []
    simTotalStep.value = Math.max(...simPathList.map(s => s.step), 1)
  } catch { /* fallback to local BFS */ simTotalStep.value = 3 }

  const loop = () => {
    if (!simRunning.value) return
    simProgress.value += 1; applyStep(simProgress.value)
    if (simProgress.value >= simTotalStep.value) { simRunning.value = false; return }
    animTimer = setTimeout(loop, 1200)
  }
  loop()
}

function applyStep(step) {
  graph?.getNodes().forEach(n => graph.clearItemStates(n, ['active', 'impact_pos', 'impact_neg']))
  graph?.getEdges().forEach(e => graph.clearItemStates(e, ['active']))
  const active = simPathList.filter(p => p.step <= step)
  active.forEach(p => {
    graph?.setItemState(p.source_id, 'active', true)
    graph?.setItemState(p.target_id, p.final_impact > 0 ? 'impact_pos' : 'impact_neg', true)
    const edgeId = graph?.getEdges().find(e => e.getModel().source === p.source_id && e.getModel().target === p.target_id)
    if (edgeId) graph?.setItemState(edgeId, 'active', true)
  })
}

function seekStep(v) { if (!simRunning.value) applyStep(v) }
function stopSim() { simRunning.value = false; if (animTimer) clearTimeout(animTimer) }
function resetSim() { stopSim(); simProgress.value = 0; simPathList = []; simRootId.value = null; simImpactResult.value = {}
  graph?.getNodes().forEach(n => graph.clearItemStates(n)); graph?.getEdges().forEach(e => graph.clearItemStates(e)) }
function onDragEvent(e, ev) { dragEventData = ev; ElMessage.info('点击画布节点设定冲击起点') }
function jumpToSim(id) { activeTab.value = 'simulation'; nextTick(() => { simRootId.value = id }) }
function callAiReport() { ElMessage.info('AI宏观研判中...') }
function exportReport() { ElMessage.info('导出宏观情景报告...') }
function handleAiCall() { ElMessage.info('AI解读中...') }
async function reloadEntity(id) {
  try { const { data } = await axios.get(`/api/v1/macro/country/${id || currentEntity.value?.id}`); currentEntity.value = data.data }
  catch {}
}

watch(activeTab, v => { if (v === 'simulation') nextTick(() => { if (!graph) initG6(); else loadGraph() }) })

onMounted(async () => {
  await loadCountries(); await loadEvents()
  if (activeTab.value === 'simulation') nextTick(() => initG6())
})
</script>

<style scoped>
.macro-monitor-wrap { width: 100%; height: 100%; display: flex; flex-direction: column; }
.header-bar { height: 60px; line-height: 60px; padding: 0 20px; background: #fff; border-bottom: 1px solid #eee; display: flex; align-items: center; }
.title { font-size: 18px; font-weight: bold; }
.main-row { display: flex; flex: 1; height: 0; }
.left-panel { width: 260px; background: #f7f8fa; padding: 14px; border-right: 1px solid #e8e8e8; overflow-y: auto; }
.center-container { flex: 1; min-width: 0; }
.monitor-view, .sim-view { width: 100%; height: 100%; }
.g6-canvas { width: 100%; height: 100%; background: #0a0e17; }
.drag-event-item { background: #fff; padding: 10px; border-radius: 6px; border: 1px solid #ddd; margin-bottom: 8px; cursor: grab; }
.panel-title { font-weight: bold; margin: 10px 0 6px; font-size: 14px; }
.tip { font-size: 11px; color: #999; margin-top: 4px; }
</style>
