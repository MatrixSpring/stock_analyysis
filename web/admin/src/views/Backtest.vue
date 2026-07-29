<template>
  <el-card header="策略回测平台">
    <!-- 回测参数区域 -->
    <el-row :gutter="16">
      <el-col :span="5">
        <el-select v-model="form.stock_code" placeholder="选择股票">
          <el-option
            v-for="item in favList"
            :key="item.id"
            :label="`${item.stock_name}(${item.stock_code})`"
            :value="item.stock_code"
          />
        </el-select>
      </el-col>
      <el-col :span="5">
        <el-select v-model="form.strategy_name" @change="resetParams">
          <el-option label="均线策略 ma_strategy" value="ma_strategy" />
          <el-option label="主力资金策略 capital_flow_strategy" value="capital_flow_strategy" />
        </el-select>
      </el-col>
      <el-col :span="6">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          format="YYYYMMDD"
          value-format="YYYYMMDD"
        />
      </el-col>
      <el-col :span="4">
        <el-button type="primary" @click="runTest" :loading="submitting">启动回测</el-button>
      </el-col>
    </el-row>

    <!-- 动态策略参数表单 -->
    <el-row :gutter="16" style="margin-top:16px" v-if="form.strategy_name">
      <el-col :span="24">
        <el-card header="策略参数配置">
          <template v-if="form.strategy_name === 'ma_strategy'">
            <span>短期均线周期</span>
            <el-input-number v-model="form.params.fast_ma" :min="1" :max="60" />
            <span style="margin-left:20px">长期均线周期</span>
            <el-input-number v-model="form.params.slow_ma" :min="1" :max="120" />
          </template>
          <template v-if="form.strategy_name === 'capital_flow_strategy'">
            <span>连续净流入统计天数</span>
            <el-input-number v-model="form.params.roll_days" :min="1" :max="10" />
          </template>
        </el-card>
      </el-col>
    </el-row>

    <!-- 回测指标展示卡片 -->
    <el-row :gutter="16" style="margin-top:20px" v-if="currentResult">
      <el-col :span="4">
        <el-card><h4>策略总收益率</h4>
          <div :style="{fontSize:'24px', color: currentResult.total_return >=0 ? '#67C23A' : '#F56C6C'}">
            {{ (currentResult.total_return * 100).toFixed(2) }} %
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card><h4>买入持有收益(基准)</h4>
          <div :style="{fontSize:'24px', color: currentResult.bench_return >=0 ? '#409EFF' : '#F56C6C'}">
            {{ (currentResult.bench_return * 100).toFixed(2) }} %
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card><h4>超额收益</h4>
          <div :style="{fontSize:'24px', color: currentResult.excess_return >=0 ? '#67C23A' : '#F56C6C'}">
            {{ (currentResult.excess_return * 100).toFixed(2) }} %
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card><h4>最大回撤</h4>
          <div style="font-size:24px;color:#F56C6C">
            {{ (currentResult.max_drawdown * 100).toFixed(2) }} %
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card><h4>交易胜率</h4>
          <div style="font-size:24px;color:#409EFF">
            {{ (currentResult.win_rate * 100).toFixed(2) }} %
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 收益曲线图：双曲线对比 -->
    <div ref="chartRef" v-if="currentResult" style="width:100%;height:420px;margin-top:20px"></div>

    <el-divider />

    <!-- 任务列表 -->
    <h3>历史回测任务（点击行查看结果）</h3>
    <el-table
      :data="taskList" border style="margin-top:10px"
      @row-click="onRowClick" highlight-current-row
    >
      <el-table-column prop="task_id" label="任务ID" min-width="260" />
      <el-table-column prop="stock_code" label="股票代码" />
      <el-table-column prop="strategy_name" label="策略名称" />
      <el-table-column prop="total_return" label="策略收益">
        <template #default="scope">
          <span :style="{color: scope.row.total_return >=0 ? '#67C23A' : '#F56C6C'}">
            {{ (scope.row.total_return *100).toFixed(2) }}%
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="max_drawdown" label="最大回撤">
        <template #default="scope">{{ (scope.row.max_drawdown *100).toFixed(2) }}%</template>
      </el-table-column>
      <el-table-column prop="win_rate" label="胜率">
        <template #default="scope">{{ (scope.row.win_rate *100).toFixed(2) }}%</template>
      </el-table-column>
      <el-table-column prop="status" label="任务状态" />
      <el-table-column prop="create_time" label="创建时间" />
    </el-table>
  </el-card>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { getFavoriteList, runBacktest, getBacktestTaskList } from '../api'

const favList = ref([])
const taskList = ref([])
const chartRef = ref(null)
let chartInstance = null

const submitting = ref(false)
const dateRange = ref(['20260101', '20260728'])
const form = ref({
  stock_code: '',
  strategy_name: 'ma_strategy',
  params: { fast_ma: 5, slow_ma: 20 }
})

const currentResult = ref(null)
let pollTimer = null

function resetParams() {
  if (form.value.strategy_name === 'ma_strategy') {
    form.value.params = { fast_ma: 5, slow_ma: 20 }
  } else if (form.value.strategy_name === 'capital_flow_strategy') {
    form.value.params = { roll_days: 3 }
  }
  currentResult.value = null
}

function renderChart(result) {
  if (!chartInstance) chartInstance = echarts.init(chartRef.value)
  const dataList = result.data || []
  const xData = [], equityData = [], benchEquityData = []
  const signalBuy = [], signalSell = []

  let equity = 1.0, benchEquity = 1.0

  dataList.forEach((row, index) => {
    xData.push(row.trade_date)
    equity *= (1 + (row.strategy_return || 0))
    equityData.push(+equity.toFixed(4))
    benchEquity *= (1 + (row.bench_return || 0))
    benchEquityData.push(+benchEquity.toFixed(4))

    const prevRow = index > 0 ? dataList[index - 1] : null
    if (row.signal === 1 && (!prevRow || prevRow.signal !== 1)) {
      signalBuy.push([row.trade_date, equity])
    }
    if (row.signal === 0 && prevRow && prevRow.signal === 1) {
      signalSell.push([row.trade_date, equity])
    }
  })

  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['策略净值', '买入持有基准'] },
    xAxis: { type: 'category', data: xData },
    yAxis: { name: '资产净值' },
    series: [
      { name: '策略净值', type: 'line', data: equityData, smooth: true, lineStyle: { width: 2 } },
      { name: '买入持有基准', type: 'line', data: benchEquityData, smooth: true, lineStyle: { type: 'dashed' }, itemStyle: { color: '#409EFF' } },
      { name: '买入', type: 'scatter', data: signalBuy, symbol: 'triangle', symbolSize: 10, itemStyle: { color: '#67C23A' } },
      { name: '卖出', type: 'scatter', data: signalSell, symbol: 'triangle', symbolSize: 10, itemStyle: { color: '#F56C6C' } },
    ],
  })
}

async function loadTaskList() {
  const res = await getBacktestTaskList()
  taskList.value = res.data || []
  const running = taskList.value.find(t => t.status === 'running')
  if (running && !pollTimer) {
    pollTimer = setInterval(async () => {
      await loadTaskList()
      const t = taskList.value.find(x => x.task_id === running.task_id)
      if (!t || t.status !== 'running') { clearInterval(pollTimer); pollTimer = null; ElMessage.success('回测任务执行完成！') }
    }, 2000)
  }
}

function onRowClick(row) {
  if (row.status !== 'finished') { ElMessage.warning('任务尚未完成'); currentResult.value = null; return }
  currentResult.value = typeof row.result === 'string' ? JSON.parse(row.result) : row.result
  nextTick(() => renderChart(currentResult.value))
}

async function runTest() {
  if (!form.value.stock_code) return ElMessage.warning("请先选择股票")
  if (dateRange.value.length < 2) return ElMessage.warning("请选择起止日期")
  submitting.value = true
  try {
    const [start, end] = dateRange.value
    await runBacktest({ stock_code: form.value.stock_code, start_date: start, end_date: end, strategy_name: form.value.strategy_name, params: { ...form.value.params } })
    ElMessage.success('回测任务已提交')
    currentResult.value = null
    setTimeout(loadTaskList, 1000)
  } finally { submitting.value = false }
}

async function init() {
  const res = await getFavoriteList()
  favList.value = res.data || []
  if (favList.value.length) form.value.stock_code = favList.value[0].stock_code
  await loadTaskList()
}

onMounted(init)
</script>

<style scoped>
.el-card { margin-bottom: 16px; }
</style>
