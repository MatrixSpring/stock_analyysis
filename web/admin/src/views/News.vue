<template>
<el-card header="个股资讯">
  <el-row>
    <el-select v-model="code" placeholder="选择股票" @change="loadNews">
      <el-option v-for="item in favList" :key="item.id" :label="item.stock_name" :value="item.stock_code"/>
    </el-select>
    <el-button type="primary" @click="loadNews" style="margin-left:10px">刷新资讯</el-button>
    <el-button type="success" @click="aiSummary" style="margin-left:10px">AI舆情总结</el-button>
  </el-row>
  <el-table :data="newsList" border style="margin-top:20px">
    <el-table-column prop="title" label="标题"/>
    <el-table-column prop="publish_time" label="发布时间"/>
  </el-table>
  <el-divider/>
  <el-card v-if="aiResult" header="AI舆情分析结果">
    <p style="white-space:pre-wrap">{{aiResult}}</p>
  </el-card>
</el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getFavoriteList, getStockNews, llmNewsSummary } from '../api'

const favList = ref([])
const code = ref('')
const newsList = ref([])
const aiResult = ref('')

async function init() {
  const res = await getFavoriteList()
  favList.value = res.data
  if (favList.value.length) code.value = favList.value[0].stock_code
  loadNews()
}

async function loadNews() {
  const res = await getStockNews(code.value, '20260101', '20260728')
  newsList.value = res.data?.list || []
}

async function aiSummary() {
  const text = newsList.value.map(i => i.title).join("\n")
  const res = await llmNewsSummary({ prompt: `请用2-3句话总结以下新闻舆情：\n${text}` })
  aiResult.value = res.data?.content || '无结果'
}

onMounted(init)
</script>
