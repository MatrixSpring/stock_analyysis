<template>
  <el-card>
    <div v-if="reportContent" class="report-content" v-html="renderedContent"></div>
    <el-empty v-else description="点击上方「生成专家前瞻报告」由豆包 AI 自动撰写" :image-size="80"/>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ reportContent: String })
const renderedContent = computed(() => (props.reportContent || '').replace(/\n/g, '<br/>'))
</script>

<style scoped>
.report-content { line-height: 2; font-size: 14px; color: #333; padding: 16px; white-space: pre-wrap; }
</style>
