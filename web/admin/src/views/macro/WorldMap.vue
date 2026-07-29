<template>
  <div ref="worldMapRef" class="world-map-container"></div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'

const emit = defineEmits(['country-dblclick'])
const worldMapRef = ref(null)
let chartInstance = null

// 货币脆弱性得分（模拟数据，对接 /api/v1/macro/countries）
const mapData = [
  { name: '美国', value: 32 }, { name: '中国', value: 36 },
  { name: '日本', value: 41 }, { name: '德国', value: 44 },
  { name: '印度', value: 59 }, { name: '巴西', value: 68 },
  { name: '英国', value: 47 }, { name: '俄罗斯', value: 55 },
  { name: '韩国', value: 42 }, { name: '南非', value: 62 },
]

const nameMap = {
  'United States': '美国', China: '中国', Japan: '日本', Germany: '德国',
  India: '印度', Brazil: '巴西', 'United Kingdom': '英国', Russia: '俄罗斯',
  'South Korea': '韩国', 'South Africa': '南非', France: '法国', Italy: '意大利',
  Canada: '加拿大', Australia: '澳大利亚',
}

function initMap() {
  chartInstance = echarts.init(worldMapRef.value)

  // 用柱状图替代世界地图（echarts world map 需要额外注册）
  // 生产环境替换为真实 ECharts map + world.json 注册
  chartInstance.setOption({
    title: { text: '全球货币脆弱性热力监测', left: 'center', textStyle: { color: '#e2e8f0', fontSize: 14 } },
    tooltip: { trigger: 'axis', formatter: p => `${p[0].name}<br/>脆弱得分：${p[0].value}` },
    grid: { left: '10%', right: '10%', bottom: '15%', top: '15%' },
    xAxis: {
      type: 'category', data: mapData.map(d => d.name),
      axisLabel: { rotate: 30, color: '#94a3b8', fontSize: 10 },
    },
    yAxis: { name: '脆弱性得分', max: 100, axisLabel: { color: '#94a3b8' },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } } },
    visualMap: {
      show: true, min: 0, max: 100,
      inRange: { color: ['#22c55e', '#fbbf24', '#f97316', '#ef4444'] },
      pieces: [{ lte: 35, label: '稳定(0~35)' }, { gt: 35, lte: 60, label: '中等(35~60)' },
               { gt: 60, lte: 80, label: '高脆弱(60~80)' }, { gt: 80, label: '高危(80+)' }],
      left: 10, bottom: 10, textStyle: { color: '#94a3b8', fontSize: 10 },
    },
    series: [{
      type: 'bar', data: mapData.map(d => ({
        value: d.value,
        itemStyle: { color: d.value <= 35 ? '#22c55e' : d.value <= 60 ? '#fbbf24' : '#ef4444' }
      })),
      barWidth: '60%',
    }],
  })

  chartInstance.on('dblclick', params => {
    const cnName = nameMap[params.name] || params.name
    emit('country-dblclick', cnName)
  })

  window.addEventListener('resize', () => chartInstance?.resize())
}

onMounted(() => { initMap() })
</script>

<style scoped>
.world-map-container { width: 100%; height: 100%; min-height: 500px; }
</style>
