<template>
  <div>
    <el-card>
      <el-table :data="stockList" stripe size="small" max-height="400">
        <el-table-column prop="code" label="代码" width="80" align="center"/>
        <el-table-column prop="name" label="名称" width="100"/>
        <el-table-column prop="sector" label="赛道" width="90"/>
        <el-table-column label="评分" width="80" align="center">
          <template #default="{row}">
            <span :style="{color: row.score > 90 ? '#22c55e' : row.score > 80 ? '#fbbf24' : '#94a3b8', fontWeight: 700, fontSize: 16}">{{ row.score }}</span>
          </template>
        </el-table-column>
        <el-table-column label="评级" width="80" align="center">
          <template #default="{row}">
            <el-tag :type="row.rating === '强推' ? 'danger' : 'warning'" size="small">{{ row.rating }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="logic" label="核心逻辑" min-width="300"/>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
defineProps({ stockList: Array })
</script>
