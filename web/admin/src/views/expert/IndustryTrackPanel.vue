<template>
  <div>
    <el-row :gutter="12">
      <el-col :span="6" v-for="item in industryList" :key="item.rank">
        <el-card :style="{borderLeft: '4px solid ' + (item.trend === 'up' ? '#22c55e' : '#fbbf24')}">
          <div class="rank-badge">#{{ item.rank }}</div>
          <div class="sector-name">{{ item.name }}</div>
          <el-progress :percentage="item.score" :color="item.score > 85 ? '#22c55e' : item.score > 70 ? '#fbbf24' : '#ef4444'" :stroke-width="8"/>
          <div style="margin-top:8px;display:flex;gap:8px">
            <el-tag :type="item.trend === 'up' ? 'success' : 'warning'" size="small">{{ item.signal }}</el-tag>
            <span style="font-size:11px;color:#666;line-height:1.4">{{ item.reason }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>
    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="24">
        <el-card header="赛道景气对比 (近6月得分趋势)">
          <div ref="radarRef" style="width:100%;height:350px"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'

defineProps({ industryList: Array })
const radarRef = ref(null)

onMounted(() => nextTick(() => {
  const c = echarts.init(radarRef.value)
  c.setOption({
    radar: {
      indicator: [
        { name: '景气度', max: 100 },{ name: '资金面', max: 100 },{ name: '政策面', max: 100 },
        { name: '估值', max: 100 },{ name: '成长性', max: 100 },
      ],
    },
    series: [{
      type: 'radar',
      data: [
        { value: [92, 85, 88, 70, 95], name: 'AI算力', areaStyle: { color: 'rgba(56,189,248,0.2)' } },
        { value: [88, 78, 82, 65, 90], name: '机器人', areaStyle: { color: 'rgba(52,211,153,0.2)' } },
        { value: [78, 72, 68, 75, 80], name: '新能源车', areaStyle: { color: 'rgba(251,191,36,0.2)' } },
      ],
    }],
  })
}))
</script>

<style scoped>
.rank-badge { position: absolute; top: 8px; right: 12px; font-size: 20px; font-weight: 800; color: #e2e8f0; }
.sector-name { font-size: 16px; font-weight: 700; margin: 8px 0; }
</style>
