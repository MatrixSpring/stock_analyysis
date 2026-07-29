<template>
  <div>
    <!-- 顶部工具栏 -->
    <el-row :gutter="12" style="margin-bottom:16px">
      <el-col :span="4">
        <el-select v-model="chainName" @change="loadGraph" placeholder="选择产业链">
          <el-option label="AI算力" value="AI算力"/>
          <el-option label="光伏" value="光伏"/>
          <el-option label="新能源汽车" value="新能源汽车"/>
          <el-option label="半导体" value="半导体"/>
          <el-option label="白酒" value="白酒"/>
          <el-option label="机器人" value="机器人"/>
        </el-select>
      </el-col>
      <el-col :span="10">
        <el-radio-group v-model="viewMode" @change="renderGraph">
          <el-radio-button label="standard">标准产业链</el-radio-button>
          <el-radio-button label="impact">冲击推演</el-radio-button>
          <el-radio-button label="company">公司穿透</el-radio-button>
        </el-radio-group>
      </el-col>
      <el-col :span="6">
        <el-button size="small" @click="loadGraph">🔄 刷新</el-button>
        <el-button size="small" type="success" @click="exportSnapshot">📥 导出JSON</el-button>
      </el-col>
    </el-row>

    <el-row :gutter="12">
      <!-- 左侧面板 -->
      <el-col :span="4">
        <el-card header="外部冲击事件" style="max-height:500px;overflow-y:auto">
          <div v-for="evt in events" :key="evt.event_id" style="margin-bottom:8px;cursor:pointer"
               @click="applyEvent(evt)">
            <el-tag :type="evt.category==='地缘政治'?'danger':evt.category==='产业政策'?'warning':'info'" size="small">
              {{ evt.category }}
            </el-tag>
            <span style="font-size:12px;margin-left:4px">{{ evt.title.slice(0,12) }}</span>
          </div>
          <el-divider/>
          <el-input v-model="newEvent.title" placeholder="事件标题" size="small" style="margin-bottom:6px"/>
          <el-select v-model="newEvent.category" size="small" style="width:100%;margin-bottom:6px">
            <el-option v-for="c in ['产业政策','舆情事件','宏观资金','地缘政治']" :key="c" :label="c" :value="c"/>
          </el-select>
          <el-row :gutter="6">
            <el-col :span="12"><el-input-number v-model="newEvent.strength" :min="1" :max="10" size="small"/></el-col>
            <el-col :span="12">
              <el-select v-model="newEvent.direction" size="small">
                <el-option label="利好" value="positive"/>
                <el-option label="利空" value="negative"/>
              </el-select>
            </el-col>
          </el-row>
          <el-button type="primary" size="small" style="margin-top:8px;width:100%" @click="addImpact">投放到图谱</el-button>
        </el-card>
      </el-col>

      <!-- 中央画布 -->
      <el-col :span="16">
        <div ref="graphRef" style="width:100%;height:600px;background:#0a0e17;border-radius:8px"></div>
      </el-col>

      <!-- 右侧面板 -->
      <el-col :span="4">
        <el-card v-if="selectedNode" header="节点详情">
          <p><b>{{ selectedNode.name }}</b></p>
          <p v-if="selectedNode.props?.stocks?.length">
            成分股: {{ selectedNode.props.stocks.join(', ') }}
          </p>
          <p>影响力: <span :style="{color: selectedNode.impact_score > 1 ? '#22c55e' : selectedNode.impact_score < -1 ? '#ef4444' : '#94A3B8'}">
            {{ selectedNode.impact_score?.toFixed(1) || 0 }}
          </span></p>
          <el-button size="small" type="primary" @click="aiAnalyze">🤖 AI分析</el-button>
        </el-card>

        <el-card v-if="impactResult" header="冲击结果" style="margin-top:12px">
          <p style="color:#22c55e">受益: {{ impactResult.benefited?.length || 0 }} 节点</p>
          <p style="color:#ef4444">受损: {{ impactResult.damaged?.length || 0 }} 节点</p>
          <p style="font-size:11px;color:#94A3B8">动画帧: {{ impactResult.animation_frames?.length || 0 }}</p>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图例 -->
    <div style="display:flex;gap:16px;margin-top:8px;font-size:11px;color:#94A3B8">
      <span>── 成本传导(C) <span style="color:#6096FF">■</span></span>
      <span>── 需求拉动(D) <span style="color:#36CFC9">■</span></span>
      <span>- - 替代竞争(S) <span style="color:#FF7D00">■</span></span>
      <span>━━ 供给约束 <span style="color:#F53F3F">■</span></span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'

const API = '/api/v1/graph'
const chainName = ref('AI算力')
const viewMode = ref('standard')
const graphRef = ref(null)
let chart = null
const selectedNode = ref(null)
const impactResult = ref(null)
const events = ref([])

const newEvent = ref({ title: '', category: '产业政策', direction: 'negative', strength: 5 })

const NODE_COLOR = { upstream: '#38bdf8', midstream: '#fbbf24', downstream: '#34d399' }
const NODE_SHAPE = { industry: 'roundRect', company: 'circle', impact_factor: 'diamond' }

const segName = { upstream: '上游', midstream: '中游', downstream: '下游' }

async function loadGraph() {
  const { data } = await axios.get(`${API}/data/${chainName.value}`)
  if (!chart) chart = echarts.init(graphRef.value)
  const g = data.data

  const nodes = g.nodes.map(n => ({
    ...n, x: n.x || Math.random() * 600 + 100, y: n.y || Math.random() * 400 + 50,
    symbol: NODE_SHAPE[n.type] || 'roundRect',
    symbolSize: n.style?.size || 50,
    itemStyle: { color: n.style?.fill || NODE_COLOR[n.segment] || '#64748B' },
    label: { show: true, fontSize: 10, color: '#e2e8f0' },
    category: n.segment ? segName[n.segment] || n.segment : n.type,
  }))

  const edges = g.edges.map(e => ({
    ...e, source: e.source, target: e.target,
    lineStyle: {
      color: e.is_impact_path ? '#f472b6' : (e.style?.stroke || '#666'),
      width: (e.style?.lineWidth || 1) + (e.is_impact_path ? 2 : 0),
      type: e.style?.lineDash ? 'dashed' : 'solid',
    },
    label: { show: true, formatter: e.style?.label || '', fontSize: 9, color: '#94A3B8' }
  }))

  const categories = Object.entries(segName).map(([k, v]) => ({
    name: v, itemStyle: { color: NODE_COLOR[k] }
  }))

  chart.setOption({
    tooltip: { formatter: p => `<b>${p.name}</b><br/>影响力:${p.data.impact_score||0}` },
    legend: { data: categories.map(c => c.name), textStyle: { color: '#94A3B8' } },
    series: [{
      type: 'graph', layout: 'force', categories,
      nodes, edges, roam: true, draggable: true,
      force: { repulsion: 300, edgeLength: [100, 250] },
      lineStyle: { curveness: 0.3 },
    }],
  })

  chart.off('click')
  chart.on('click', p => { selectedNode.value = p.data })
  impactResult.value = g.benefited ? g : null
}

async function addImpact() {
  const g = (await axios.get(`${API}/data/${chainName.value}`)).data.data
  await axios.post(`${API}/impact/${chainName.value}`, {
    title: newEvent.value.title, category: newEvent.value.category,
    direction: newEvent.value.direction, strength: newEvent.value.strength,
    target_nodes: g.nodes.map(n => n.id),
  })
  loadEvents()
  loadGraph()
}

async function applyEvent(evt) {
  const g = (await axios.get(`${API}/data/${chainName.value}`)).data.data
  await axios.post(`${API}/impact/${chainName.value}`, {
    title: evt.title, category: evt.category,
    direction: evt.direction || 'negative', strength: evt.strength || 5,
    target_nodes: g.nodes.filter(n => n.segment === 'upstream').map(n => n.id),
  })
  loadGraph()
}

async function loadEvents() {
  const { data } = await axios.get(`${API}/events`)
  events.value = data.data || []
}

function renderGraph() { loadGraph() }

async function exportSnapshot() {
  const { data } = await axios.get(`${API}/snapshot/${chainName.value}`)
  const blob = new Blob([data.data.json], { type: 'application/json' })
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
  a.download = `${chainName.value}_graph.json`; a.click()
}

async function aiAnalyze() {
  const { ElMessage } = await import('element-plus')
  ElMessage.info('AI分析已触发（对接LLM工作台）')
}

onMounted(() => { loadGraph(); loadEvents() })
</script>
