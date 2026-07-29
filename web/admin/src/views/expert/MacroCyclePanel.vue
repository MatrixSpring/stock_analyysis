<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="6" v-for="card in cards" :key="card.key">
        <el-card :style="{borderTop: '3px solid ' + card.color}">
          <div class="card-label">{{ card.label }}</div>
          <div class="card-value" :style="{color: card.color}">{{ card.value }}</div>
          <div class="card-desc">{{ card.desc }}</div>
        </el-card>
      </el-col>
    </el-row>
    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12">
        <el-card header="宏观择时综合评分">
          <div ref="gaugeRef" style="width:100%;height:260px"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="流动性 & 风险偏好趋势">
          <div ref="trendRef" style="width:100%;height:260px"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ macroData: Object })

const cards = computed(() => [
  { key:'liquidity', label:'流动性环境', value: props.macroData?.liquidity || '--', desc: '央行政策基调', color:'#38bdf8' },
  { key:'risk', label:'风险偏好', value: props.macroData?.riskAppetite || '--', desc: '资金情绪指标', color:'#34d399' },
  { key:'rate', label:'利率趋势', value: props.macroData?.rateTrend || '--', desc: '10Y国债方向', color:'#fbbf24' },
  { key:'flow', label:'资金流向', value: props.macroData?.fundFlow || '--', desc: '北向+两融', color:'#a78bfa' },
])

const gaugeRef = ref(null), trendRef = ref(null)

onMounted(() => {
  nextTick(() => {
    const g = echarts.init(gaugeRef.value)
    g.setOption({
      series: [{
        type: 'gauge', startAngle: 200, endAngle: -20, min: 0, max: 100,
        progress: { show: true, width: 12, itemStyle: { color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0,
          colorStops: [{ offset: 0, color: '#ef4444' },{ offset: 0.5, color: '#fbbf24' },{ offset: 1, color: '#22c55e' }] } } },
        detail: { valueAnimation: true, formatter: '{value}分', fontSize: 18, color: '#e2e8f0' },
        data: [{ value: props.macroData?.cycleScore || 72, name: '择时评分' }],
      }],
    })
    const t = echarts.init(trendRef.value)
    t.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { data: ['1月','2月','3月','4月','5月','6月'], axisLabel: { color: '#94a3b8' } },
      yAxis: { axisLabel: { color: '#94a3b8' } },
      series: [
        { name: '流动性指数', type: 'line', data: [45,52,58,62,68,65], smooth: true, itemStyle: { color: '#38bdf8' } },
        { name: '风险偏好', type: 'line', data: [30,38,42,55,60,72], smooth: true, itemStyle: { color: '#34d399' } },
      ],
    })
  })
})
</script>

<style scoped>
.card-label { font-size: 12px; color: #94a3b8; margin-bottom: 8px; }
.card-value { font-size: 22px; font-weight: 700; }
.card-desc { font-size: 11px; color: #666; margin-top: 4px; }
</style>
