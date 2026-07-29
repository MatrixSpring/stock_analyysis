<template>
  <div class="transmission-log">
    <div class="panel-title">📝 传导过程溯源日志</div>
    <el-timeline>
      <el-timeline-item
        v-for="(step, idx) in steps"
        :key="idx"
        :type="step.impact > 0 ? 'success' : step.impact < 0 ? 'danger' : 'info'"
        :hollow="step.type === 'intermediate'"
        :timestamp="step.time"
        placement="top"
      >
        <div class="step-card">
          <div class="step-title">
            <span v-if="step.type === 'event'" class="tag-event">⚡ 事件</span>
            <span v-else-if="step.type === 'factor'" class="tag-factor">📊 因子解析</span>
            <span v-else-if="step.type === 'node'" class="tag-node">🔗 节点传导</span>
            <span v-else class="tag-inter">📐 中间变量</span>
            {{ step.title }}
          </div>
          <div class="step-detail" v-if="step.detail">{{ step.detail }}</div>
          <div class="step-impact" v-if="step.impact">
            影响力: <b :style="{color: step.impact > 0 ? '#22c55e' : '#ef4444'}">{{ step.impact > 0 ? '+' : '' }}{{ step.impact }}</b>
            <span v-if="step.coeff" style="margin-left:8px;font-size:11px;color:#999">系数: {{ step.coeff }}</span>
          </div>
        </div>
      </el-timeline-item>
    </el-timeline>
    <el-empty v-if="!steps.length" description="暂无传导记录，请启动推演" :image-size="60"/>
  </div>
</template>

<script setup>
defineProps({
  steps: { type: Array, default: () => [] },
})
</script>

<style scoped>
.transmission-log { padding: 8px; max-height: 500px; overflow-y: auto; }
.panel-title { font-weight: 700; margin-bottom: 8px; font-size: 14px; }
.step-card { font-size: 13px; }
.step-title { font-weight: 600; margin-bottom: 2px; }
.step-detail { font-size: 12px; color: #666; margin: 2px 0; }
.step-impact { font-size: 12px; margin-top: 2px; }
.tag-event { color: #f5222d; font-size: 11px; }
.tag-factor { color: #1677ff; font-size: 11px; }
.tag-node { color: #52c41a; font-size: 11px; }
.tag-inter { color: #fa8c16; font-size: 11px; }
</style>
