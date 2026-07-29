<template>
<el-row :gutter="20">
  <el-col :span="8">
    <el-card header="自选股总数"><h2>{{favCount}}</h2></el-card>
  </el-col>
  <el-col :span="8">
    <el-card header="历史回测任务"><h2>{{backtestCount}}</h2></el-card>
  </el-col>
  <el-col :span="8">
    <el-card header="LLM模型"><h2>默认：豆包Doubao</h2></el-card>
  </el-col>
</el-row>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getFavoriteList, getBacktestTaskList } from '../api'

const favCount = ref(0)
const backtestCount = ref(0)

async function load() {
  const fav = await getFavoriteList()
  favCount.value = fav.data.length
  const bt = await getBacktestTaskList()
  backtestCount.value = bt.data.length
}

onMounted(load)
</script>
