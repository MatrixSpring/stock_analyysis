<template>
  <el-card header="行情 & 资金流向图表">
    <el-row :gutter="16">
      <el-col :span="8">
        <el-select v-model="query.code" placeholder="选择股票" @change="loadChart">
          <el-option v-for="item in favList" :key="item.id" :label="item.stock_name" :value="item.stock_code"/>
        </el-select>
      </el-col>
      <el-col :span="12">
        <el-date-picker v-model="dateRange" type="daterange" format="YYYYMMDD" value-format="YYYYMMDD"/>
        <el-button type="primary" @click="loadChart" style="margin-left:10px">查询</el-button>
      </el-col>
    </el-row>
    <div ref="klineRef" style="width:100%;height:400px;margin-top:20px"></div>
    <div ref="capitalRef" style="width:100%;height:320px;margin-top:20px"></div>
  </el-card>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getFavoriteList, getStockKline, getCapitalData } from '../api'

const klineRef = ref(null)
const capitalRef = ref(null)
let kChart, capChart

const favList = ref([])
const query = ref({ code: '' })
const dateRange = ref([])

async function init() {
  const res = await getFavoriteList()
  favList.value = res.data
  if (favList.value.length) query.value.code = favList.value[0].stock_code
  dateRange.value = ['20260101', '20260728']
  await nextTick()
  kChart = echarts.init(klineRef.value)
  capChart = echarts.init(capitalRef.value)
  loadChart()
}

async function loadChart() {
  if (!query.value.code || dateRange.value.length < 2) return
  const [start, end] = dateRange.value

  const kRes = await getStockKline(query.value.code, start, end)
  const capRes = await getCapitalData(query.value.code, start, end)

  const kData = (kRes.data || []).map(item => [item.trade_date, item.open, item.close, item.low, item.high])
  const dates = kData.map(d => d[0])
  const klineValues = kData.map(d => [d[1], d[2], d[3], d[4]])

  kChart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: dates, axisLabel: { color: '#94a3b8' } },
    yAxis: { scale: true, axisLabel: { color: '#94a3b8' } },
    series: [{ type: 'candlestick', data: klineValues, itemStyle: { color: '#ef4444', color0: '#22c55e', borderColor: '#ef4444', borderColor0: '#22c55e' } }],
  })

  const capData = (capRes.data || []).map(item => [item.trade_date, item.main_inflow || 0])
  capChart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', axisLabel: { color: '#94a3b8' } },
    yAxis: { axisLabel: { color: '#94a3b8' } },
    series: [{ name: '主力资金净额', type: 'line', data: capData.map(d => d[1]), smooth: true, itemStyle: { color: '#38bdf8' } }],
  })
}

onMounted(init)
</script>
