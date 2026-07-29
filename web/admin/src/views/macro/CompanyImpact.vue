<template>
  <div class="company-impact">
    <div class="panel-title">🏢 三级公司传导穿透</div>

    <!-- 一级: 行业景气 -->
    <div class="tier tier-1">
      <div class="tier-header">一级传导 · 行业景气变动</div>
      <div class="tier-body">
        <el-tag v-for="n in tier1Nodes" :key="n.id" :type="n.impact > 0 ? 'success' : 'danger'" size="small" style="margin:2px">
          {{ n.name }} {{ n.impact > 0 ? '↑' : '↓' }}{{ Math.abs(n.impact) }}
        </el-tag>
        <span v-if="!tier1Nodes.length" style="color:#999;font-size:12px">待推演</span>
      </div>
    </div>

    <!-- 二级: 赛道估值 -->
    <div class="tier tier-2">
      <div class="tier-header">二级传导 · 赛道估值修正</div>
      <div class="tier-body">
        <div v-for="s in tier2Sectors" :key="s.name" class="sector-row">
          <span>{{ s.name }}</span>
          <el-progress :percentage="Math.abs(s.score)" :color="s.score > 0 ? '#22c55e' : '#ef4444'" :stroke-width="6" style="flex:1;margin:0 8px"/>
          <span :style="{color: s.score > 0 ? '#22c55e' : '#ef4444', fontSize: '12px'}">{{ s.score > 0 ? '+' : '' }}{{ s.score }}%</span>
        </div>
      </div>
    </div>

    <!-- 三级: 个股影响 -->
    <div class="tier tier-3">
      <div class="tier-header">三级传导 · 个股影响打分</div>
      <el-table :data="tier3Stocks" size="small" max-height="200" style="background:transparent">
        <el-table-column prop="name" label="标的" width="80"/>
        <el-table-column prop="code" label="代码" width="70"/>
        <el-table-column label="传导" width="60">
          <template #default="{row}">
            <el-tag :type="row.level === '强' ? 'danger' : row.level === '中' ? 'warning' : 'info'" size="small">{{ row.level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="影响">
          <template #default="{row}">
            <span :style="{color: row.impact > 0 ? '#22c55e' : '#ef4444'}">{{ row.impact > 0 ? '+' : '' }}{{ row.impact }}%</span>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="逻辑" width="120"/>
      </el-table>
    </div>
  </div>
</template>

<script setup>
defineProps({
  tier1Nodes: { type: Array, default: () => [] },
  tier2Sectors: { type: Array, default: () => [] },
  tier3Stocks: { type: Array, default: () => [] },
})
</script>

<style scoped>
.company-impact { padding: 8px; }
.panel-title { font-weight: 700; margin-bottom: 12px; font-size: 14px; }
.tier { margin-bottom: 12px; border: 1px solid #e5e7eb; border-radius: 6px; padding: 8px; }
.tier-header { font-weight: 600; font-size: 12px; margin-bottom: 6px; color: #333; }
.tier-body { font-size: 12px; }
.sector-row { display: flex; align-items: center; margin: 4px 0; font-size: 12px; }
</style>
