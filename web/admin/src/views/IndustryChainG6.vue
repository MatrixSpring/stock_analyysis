<template>
  <div class="industry-chain-wrap">
    <!-- 顶部工具栏 -->
    <div class="graph-toolbar">
      <el-space>
        <el-radio-group v-model="viewMode" @change="switchViewMode">
          <el-radio-button label="base">基础图谱浏览</el-radio-button>
          <el-radio-button label="simulation">冲击推演沙盘</el-radio-button>
        </el-radio-group>
        <el-button @click="resetGraph">重置视图</el-button>
        <el-button @click="zoomIn">放大</el-button>
        <el-button @click="zoomOut">缩小</el-button>
        <el-select v-model="chainName" @change="loadChain" placeholder="产业链">
          <el-option v-for="c in chains" :key="c" :label="c" :value="c"/>
        </el-select>
        <el-select v-model="filterLinkType" placeholder="筛选传导" clearable @change="filterEdge">
          <el-option label="全部" value=""/>
          <el-option label="成本传导(C)" value="cost"/>
          <el-option label="需求拉动(D)" value="demand"/>
          <el-option label="替代竞争(S)" value="substitute"/>
          <el-option label="供给约束(Sup)" value="supply"/>
        </el-select>
        <el-switch v-model="showEventMark" active-text="事件" inactive-text="隐藏" @change="refreshMarks"/>
      </el-space>
    </div>

    <div class="graph-main-row">
      <!-- 🆕 沙盘左侧事件栏 -->
      <div class="sim-event-panel" v-if="viewMode === 'simulation'">
        <div class="panel-title">可投放冲击事件（拖拽后点击目标节点）</div>
        <div class="event-drag-item" v-for="ev in simulationEventList" :key="ev.eventId"
             draggable="true" @dragstart="handleDragStart($event, ev)"
             :style="{borderLeft: '4px solid ' + (ev.direction === 'positive' ? '#22c55e' : '#ef4444')}">
          <el-tag :type="eventTagColor[ev.type]" size="small">{{ eventTypeMap[ev.type] }}</el-tag>
          <div class="event-name">{{ ev.title }}</div>
          <div style="font-size:10px;color:#999">{{ ev.impactDesc }}</div>
        </div>
        <el-divider/>
        <div class="panel-title">沙盘控制</div>
        <el-button type="primary" @click="startSim" :disabled="!simRootNode || simRunning" size="small" style="width:100%">▶ 开始推演</el-button>
        <el-button @click="stopSim" :disabled="!simRunning" size="small" style="width:100%;margin-top:6px">⏸ 暂停</el-button>
        <el-button type="danger" @click="clearSimulation" size="small" style="width:100%;margin-top:6px">🗑 清空推演</el-button>
        <el-divider/>
        <div class="panel-title">时间轴</div>
        <el-slider v-model="simProgress" :max="simTotalStep" :step="1" @change="seekSimStep" size="small"/>
        <div class="tip">{{ simProgress }} / {{ simTotalStep }}</div>
        <div v-if="simRootNode" style="margin-top:8px;font-size:11px;color:#666">
          冲击源：{{ simRootNode.label || simRootNode.name }}<br/>
          {{ dragEventData?.title }}
        </div>
      </div>

      <div class="graph-container">
        <div ref="graphRef" class="canvas"></div>
        <!-- 右侧详情面板 -->
        <div class="right-panel" v-if="activeNode">
          <el-card>
            <template #header>
              <span>{{ activeNode.label || activeNode.name }}</span>
              <el-button link @click="activeNode = null" style="float:right">关闭</el-button>
            </template>
            <div class="info-item"><b>类型：</b>{{ nodeTypeMap[activeNode.nodeType || activeNode.segment] || '--' }}</div>
            <div class="info-item" v-if="activeNode.props?.stocks?.length">
              <b>成分股：</b><ul><li v-for="s in activeNode.props.stocks" :key="s">{{ s }}</li></ul>
            </div>
            <div class="info-item" v-if="activeNode.impact_score">
              <b>冲击值：</b><span :style="{color: activeNode.impact_score>0?'#22c55e':'#ef4444',fontWeight:'bold'}">{{ Number(activeNode.impact_score).toFixed(1) }}</span>
            </div>
            <div class="info-item" v-if="activeNode.events?.length">
              <b>事件：</b>
              <ul><li v-for="ev in activeNode.events" :key="ev.eventId || ev.title">
                <span :class="'tag-'+(ev.type||'')">【{{ eventTypeMap[ev.type]||ev.type }}】</span> {{ ev.title }}
              </li></ul>
            </div>
            <el-divider/>
            <el-button type="primary" size="small" @click="drillDown">下钻细分赛道</el-button>
            <el-button type="success" size="small" @click="openAiAnalyze">🤖 AI分析</el-button>
          </el-card>
        </div>
      </div>
    </div>

    <!-- 图例 -->
    <div class="graph-legend">
      <span>── C (成本) <i style="color:#6096FF">■</i></span>
      <span>── D (需求) <i style="color:#36CFC9">■</i></span>
      <span>- - S (替代) <i style="color:#FF7D00">■</i></span>
      <span>━━ Sup <i style="color:#F53F3F">■</i></span>
      <span style="margin-left:16px">🔴 事件预警</span>
      <span style="margin-left:8px">🟢 利好 / 🔴 利空</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const graphRef = ref(null)
let graph = null
const filterLinkType = ref('')
const activeNode = ref(null)
const showEventMark = ref(true)
const viewMode = ref('base')
const chainName = ref('AI算力')
const chains = ref(['AI算力', '机器人', '光伏', '新能源汽车', '半导体', '白酒'])

// ====== 沙盘变量 ======
let animTimer = null
const simRunning = ref(false)
const simRootNode = ref(null)
const simProgress = ref(0)
const simTotalStep = ref(8)
let simSpreadRecord = []
let dragEventData = null

const simulationEventList = [
  { eventId:'sim001', type:'geopolitics', title:'澳洲锂矿出口限制', direction:'negative', impactDesc:'上游供给收缩→成本上行' },
  { eventId:'sim002', type:'policy', title:'新能源车刺激政策落地', direction:'positive', impactDesc:'下游需求上行' },
  { eventId:'sim003', type:'liquidity', title:'市场流动性收紧', direction:'negative', impactDesc:'资本开支意愿下降' },
]

const nodeTypeMap = { upstream:'上游原材料', midstream:'中游制造', downstream:'下游终端', company:'上市公司', industry:'产业链环节' }
const eventTypeMap = { policy:'产业政策', public_opinion:'舆情', geopolitics:'地缘', liquidity:'资金' }
const eventTagColor = { policy:'', public_opinion:'warning', geopolitics:'danger', liquidity:'' }  // empty = default

const SEG_COLORS = { upstream:'#E6F7FF', midstream:'#F0FFF4', downstream:'#FFF7E6', company:'#F9E6FF' }
const SEG_STROKES = { upstream:'#1890FF', midstream:'#52C41A', downstream:'#FA8C16', company:'#722ED1' }
const edgeTypeStyle = {
  cost:{ stroke:'#6096FF', label:'C', lw:2 }, demand:{ stroke:'#36CFC9', label:'D', lw:2 },
  substitute:{ stroke:'#FF7D00', label:'S', lw:2, dash:[4,4] }, supply:{ stroke:'#F53F3F', label:'Sup', lw:3 },
}

const defaultData = {
  nodes:[
    { id:'li_ore', label:'锂矿', nodeType:'upstream', marketScale:'890亿', pricingPower:'强',
      events:[{ eventId:'ev001', type:'geopolitics', title:'澳洲锂矿出口审查收紧', impactDesc:'供给收缩→成本上行', eventTime:'2026-07-20' }] },
    { id:'cobalt', label:'钴矿', nodeType:'upstream', marketScale:'420亿', pricingPower:'中', events:[] },
    { id:'carbonate', label:'碳酸锂', nodeType:'midstream', marketScale:'2100亿', pricingPower:'强', events:[],
      middleFactor:{ name:'碳酸锂现货价格', indicator:'上涨18%' } },
    { id:'ternary', label:'三元正极', nodeType:'midstream', marketScale:'3600亿', pricingPower:'中', events:[] },
    { id:'battery', label:'动力电池', nodeType:'midstream', marketScale:'8500亿', pricingPower:'中', events:[],
      middleFactor:{ name:'电池级碳酸锂加工费', indicator:'累计上涨22%' } },
    { id:'ev', label:'新能源整车', nodeType:'downstream', marketScale:'3.2万亿', pricingPower:'分化',
      events:[{ eventId:'ev002', type:'policy', title:'购置补贴调整落地', impactDesc:'终端需求变化', eventTime:'2026-07-25' }] },
    { id:'CATL', label:'宁德时代', nodeType:'company', props:{ stocks:['300750'] },
      events:[{ eventId:'ev003', type:'public_opinion', title:'海外建厂扩产公告', impactDesc:'', eventTime:'2026-07-28' }] },
    { id:'BYD', label:'比亚迪', nodeType:'company', props:{ stocks:['002594'] }, events:[] },
  ],
  edges:[
    { id:'e1', source:'li_ore', target:'carbonate', edgeType:'cost', coeff:0.82, timeLag:'1~2月' },
    { id:'e2', source:'cobalt', target:'ternary', edgeType:'cost', coeff:0.75, timeLag:'1~2月' },
    { id:'e3', source:'carbonate', target:'ternary', edgeType:'cost', coeff:0.68, timeLag:'20~40天' },
    { id:'e4', source:'ternary', target:'battery', edgeType:'cost', coeff:0.55, timeLag:'15天' },
    { id:'e5', source:'battery', target:'ev', edgeType:'cost', coeff:0.42, timeLag:'1个月' },
    { id:'e6', source:'ev', target:'battery', edgeType:'demand', coeff:0.76, timeLag:'1~3月' },
    { id:'e7', source:'CATL', target:'battery', edgeType:'' },
    { id:'e8', source:'BYD', target:'ev', edgeType:'' },
  ]
}

const graphData = ref(JSON.parse(JSON.stringify(defaultData)))

// ====== 后端数据加载 ======
async function loadChain() {
  try {
    const { data } = await axios.get(`/api/v1/graph/data/${chainName.value}`)
    const g = data.data || { nodes:[], edges:[] }
    graphData.value = {
      nodes: g.nodes.map(n => ({ id:n.id, label:n.name, nodeType:n.segment||n.type,
        marketScale:n.props?.weight?`权重${n.props.weight}`:'', pricingPower:n.impact_score?String(n.impact_score):'--',
        props:n.props, impact_score:n.impact_score, events:n.events||[],
      })),
      edges: g.edges.map(e => ({ id:`${e.source}_${e.target}`, source:e.source, target:e.target,
        edgeType: {'成本传导':'cost','需求拉动':'demand','替代竞争':'substitute','供给约束':'supply'}[e.edge_type]||'',
        coeff:e.transmission_coeff||0.5, timeLag:e.time_lag||'--',
      })),
    }
    graph?.changeData(graphData.value); graph?.fitView()
  } catch { /* use default */ }
}

// ====== G6 初始化 ======
function initGraph() {
  import('@antv/g6').then(({ Graph }) => {
    const c = graphRef.value
    graph = new Graph({
      container:c, width:c.clientWidth, height:c.clientHeight,
      layout:{ type:'dagre', rankdir:'LR', nodesep:60, ranksep:120 },
      defaultNode:{ type:'rect', size:[130,50], style:{ fill:'#fff', stroke:'#8C8C8C', lineWidth:1, radius:4 }, labelCfg:{ style:{ fontSize:11 } } },
      defaultEdge:{ type:'polyline', style:{ stroke:'#ccc', lineWidth:1, endArrow:{ path:'M 0,0 L 8,4 L 8,-4 Z', fill:'#aaa' } } },
      modes:{ default:['drag-node','drag-canvas','zoom-canvas'] },
      animate:true, fitView:true,
      tooltip:{ enabled:true, offsetX:12, offsetY:12,
        getContent(evt){
          const m=evt.item.getModel()
          if(evt.item.getType()==='node'){
            let h=`<div style="min-width:220px;padding:6px"><b>${m.label||m.name}</b><br/>${nodeTypeMap[m.nodeType||m.segment]||''}`
            if(m.events?.length){ h+='<br/><span style="color:#d4380b">⚠ 事件：</span>'; m.events.forEach(e=>h+=`<br/>• [${eventTypeMap[e.type]||e.type}] ${e.title}`) }
            if(m.middleFactor) h+=`<br/>📊 中间指标：${m.middleFactor.name} ${m.middleFactor.indicator}`
            return h+'</div>'
          }
          const ec=edgeTypeStyle[m.edgeType]||{}
          return `<div style="min-width:180px;padding:6px"><b>传导链路</b><br/>类型：${ec.label||'关联'}<br/>系数：${m.coeff}<br/>时滞：${m.timeLag||'--'}</div>`
        }
      }
    })
    applyStyle()
    graph.data(graphData.value); graph.render()
    graph.on('node:click', evt=>{
      const m=evt.item.getModel()
      activeNode.value=m
      if(viewMode.value==='simulation'&&dragEventData){ simRootNode.value=m; ElMessage.success(`冲击源：${m.label||m.name}`); dragEventData=null }
    })
    window.addEventListener('resize',()=>graph?.changeSize(c.clientWidth,c.clientHeight))
    loadChain()
  }).catch(()=>ElMessage.warning('请 npm install @antv/g6'))
}

function applyStyle() {
  if(!graph) return
  graph.node(n=>{
    const seg=n.nodeType||n.segment||''
    let fill=SEG_COLORS[seg]||'#fff'
    if(n.simStatus==='positive') fill='#b7eb8f'
    if(n.simStatus==='negative') fill='#ffccc7'
    const cfg={ style:{ fill, stroke:SEG_STROKES[seg]||'#8C8C8C', lineWidth:2, radius:4 }, labelCfg:{ style:{ fontSize:11 } } }
    if(showEventMark.value&&n.events?.length) cfg.markers=[{ type:'circle', position:[115,8], r:6, fill:'#f5222d' }]
    return cfg
  })
  graph.edge(e=>{
    const ec=edgeTypeStyle[e.edgeType]||{}
    const anim=e.simActive?{ lineDash:[8,4], lineDashOffset:0, animate:{ type:'line-dash-offset', duration:1500 } }:{}
    return { style:{ stroke:ec.stroke||'#ccc', lineWidth:ec.lw||1, lineDash:ec.dash||[], ...anim }, label:ec.label||'', labelCfg:{ style:{ fill:ec.stroke, fontSize:10 } } }
  })
}

function refreshMarks(){ applyStyle(); graph?.refresh() }

// ====== 沙盘逻辑 (后端 Neo4j/SQLite 推演引擎) ======
function handleDragStart(e, ev){ dragEventData=ev; ElMessage.info('点击画布节点设定冲击起点') }

async function buildSpreadPath(rootId){
  try {
    const { data } = await axios.post('/api/simulation/calcPath', {
      rootNodeId: rootId, baseStrength: 0.8, minCoeffFilter: 0.15, maxLevel: 6,
    })
    simSpreadRecord = (data.data || data).map(item => {
      const tn = graphData.value.nodes.find(n => n.id === item.target_id)
      return {
        step: item.step, edgeId: `${item.source_id}-${item.target_id}`,
        nodeId: item.target_id, factor: tn?.middleFactor,
      }
    })
    simTotalStep.value = simSpreadRecord.length ? Math.max(...simSpreadRecord.map(r => r.step)) : 1
  } catch {
    // 降级：前端 BFS
    const records=[], visited=new Set(), q=[{id:rootId, step:0}]; visited.add(rootId)
    while(q.length){ const cur=q.shift()
      graphData.value.edges.filter(e=>e.source===cur.id&&!visited.has(e.target)).forEach(edge=>{
        visited.add(edge.target); const tn=graphData.value.nodes.find(n=>n.id===edge.target)
        records.push({ step:cur.step+1, edgeId:edge.id, nodeId:edge.target, factor:tn?.middleFactor })
        q.push({id:edge.target, step:cur.step+1})
      })
    }
    simSpreadRecord=records; simTotalStep.value=records.length?Math.max(...records.map(r=>r.step)):1
  }
}

async function startSim(){
  if(!simRootNode.value||simRunning.value) return
  clearSimulation(); simRunning.value=true; simProgress.value=0
  buildSpreadPath(simRootNode.value.id)
  const loop=()=>{ if(!simRunning.value) return; simProgress.value+=1; applyStep(simProgress.value); if(simProgress.value>=simTotalStep.value){ simRunning.value=false; return }; animTimer=setTimeout(loop,1200) }
  loop()
}

function applyStep(step){
  graphData.value.nodes.forEach(n=>delete n.simStatus)
  graphData.value.edges.forEach(e=>delete e.simActive)
  simSpreadRecord.filter(r=>r.step<=step).forEach(item=>{
    const e=graphData.value.edges.find(x=>x.id===item.edgeId); if(e) e.simActive=true
    const n=graphData.value.nodes.find(x=>x.id===item.nodeId); if(n) n.simStatus=dragEventData?.direction||'negative'
    if(item.factor) ElMessage.info(`📊 中间指标【${item.factor.name}】：${item.factor.indicator}`)
  })
  applyStyle(); graph?.refresh()
}

function seekSimStep(v){ if(!simRunning.value) applyStep(v) }
function stopSim(){ simRunning.value=false; if(animTimer) clearTimeout(animTimer) }
function clearSimulation(){ stopSim(); simProgress.value=0; simSpreadRecord=[]; graphData.value.nodes.forEach(n=>delete n.simStatus); graphData.value.edges.forEach(e=>delete e.simActive); applyStyle(); graph?.refresh() }
function switchViewMode(){ activeNode.value=null; clearSimulation() }

function filterEdge(){
  if(!graph) return
  const t=filterLinkType.value
  graph.getEdges().forEach(e=>{ const m=e.getModel(); t&&m.edgeType!==t?e.hide():e.show() })
}

function resetGraph(){ graph?.fitView() }
function zoomIn(){ graph?.zoom(1.1) }
function zoomOut(){ graph?.zoom(0.9) }
function drillDown(){ ElMessage.info(`下钻：${activeNode.value?.label||activeNode.value?.name}`) }
function openAiAnalyze(){ const n=activeNode.value; if(n) ElMessage.success(`AI分析【${n.label||n.name}】传导`) }

onMounted(()=>{ setTimeout(initGraph,150) })
onUnmounted(()=>{ if(animTimer) clearTimeout(animTimer); graph?.destroy() })
</script>

<style scoped>
.industry-chain-wrap { width:100%; height:100%; display:flex; flex-direction:column; }
.graph-toolbar { padding:10px 16px; background:#fff; border:1px solid #e8e8e8; border-bottom:none; }
.graph-main-row { display:flex; flex:1; height:0; min-height:600px; }
.sim-event-panel { width:220px; background:#f7f8fa; border:1px solid #e8e8e8; border-top:none; padding:12px; overflow-y:auto; flex-shrink:0; }
.panel-title { font-weight:700; margin:8px 0 6px; font-size:13px; }
.event-drag-item { background:#fff; border:1px solid #dcdcdc; border-radius:6px; padding:8px; margin-bottom:8px; cursor:grab; }
.event-name { font-size:12px; margin-top:4px; }
.graph-container { display:flex; flex:1; border:1px solid #e8e8e8; border-top:none; min-width:0; }
.canvas { flex:1; min-width:0; }
.right-panel { width:320px; background:#fff; border-left:1px solid #e8e8e8; padding:8px; overflow-y:auto; flex-shrink:0; }
.info-item { margin:8px 0; font-size:13px; }
.info-item ul { padding-left:16px; margin:4px 0; }
.graph-legend { display:flex; gap:16px; padding:8px 16px; font-size:11px; color:#666; background:#fafafa; border:1px solid #e8e8e8; border-top:none; flex-wrap:wrap; }
.graph-legend i { font-style:normal; }
.tip { font-size:11px; color:#999; margin-top:4px; }
:deep(.tag-policy) { color:#1677ff;font-weight:600 }
:deep(.tag-opinion) { color:#fa8c16;font-weight:600 }
:deep(.tag-geo) { color:#f5222d;font-weight:600 }
:deep(.tag-fund) { color:#722ed1;font-weight:600 }
</style>
