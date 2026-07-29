<template>
  <div class="factor-panel">
    <div class="panel-title">🎛 五大外部因子控制</div>
    <div class="factor-item" v-for="f in factors" :key="f.key">
      <div class="factor-header">
        <span>{{ f.icon }} {{ f.label }}</span>
        <el-tag :type="f.value > 6 ? 'danger' : f.value > 3 ? 'warning' : 'info'" size="small">{{ levelText(f.value) }}</el-tag>
      </div>
      <el-slider v-model="f.value" :min="0" :max="10" :step="0.5" show-input @change="onChange"/>
      <div class="factor-desc">{{ f.desc }}</div>
    </div>
    <el-divider/>
    <div class="factor-summary">
      <div>综合影响强度: <b :style="{color: totalImpact > 0 ? '#22c55e' : '#ef4444'}">{{ totalImpact > 0 ? '+' : '' }}{{ totalImpact.toFixed(1) }}</b></div>
      <div>主导因子: <b>{{ dominantFactor }}</b></div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const emit = defineEmits(['factor-change'])

const factors = ref([
  { key: 'policy', icon: '📋', label: '产业政策', value: 3, desc: '补贴/限产/关税/准入新规', direction: 1 },
  { key: 'game', icon: '⚔️', label: '行业博弈', value: 4, desc: '产能投放/价格战/库存周期', direction: -1 },
  { key: 'sentiment', icon: '📰', label: '舆情情绪', value: 5, desc: '预期差/发酵/反转', direction: 1 },
  { key: 'capital', icon: '💰', label: '资金流向', value: 4, desc: '机构加仓/北向/筹码', direction: 1 },
  { key: 'geo', icon: '🌍', label: '地缘政治', value: 2, desc: '关税/制裁/区域冲突', direction: -1 },
])

const totalImpact = computed(() => factors.value.reduce((s, f) => s + f.value * f.direction * 0.2, 0))
const dominantFactor = computed(() => {
  const top = [...factors.value].sort((a, b) => Math.abs(b.value * b.direction) - Math.abs(a.value * a.direction))[0]
  return top.label
})

const levelText = (v) => v > 7 ? '强影响' : v > 4 ? '中等' : '弱'
const onChange = () => emit('factor-change', Object.fromEntries(factors.value.map(f => [f.key, f.value])))
</script>

<style scoped>
.factor-panel { padding: 8px; }
.panel-title { font-weight: 700; margin-bottom: 12px; font-size: 14px; }
.factor-item { margin-bottom: 12px; }
.factor-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; font-size: 13px; }
.factor-desc { font-size: 11px; color: #999; margin-top: 2px; }
.factor-summary { font-size: 13px; }
.factor-summary b { font-size: 15px; }
</style>
