<template>
  <el-card header="自选股池">
    <el-row :gutter="20" style="margin-bottom:20px">
      <el-col span="16">
        <el-input v-model="form.code" placeholder="股票代码" style="width:160px"></el-input>
        <el-input v-model="form.name" placeholder="股票名称" style="width:180px;margin-left:10px"></el-input>
        <el-button type="primary" @click="addStock" style="margin-left:10px">新增自选</el-button>
      </el-col>
    </el-row>
    <el-table :data="tableData" border>
      <el-table-column prop="id" label="ID" />
      <el-table-column prop="stock_code" label="股票代码" />
      <el-table-column prop="stock_name" label="股票名称" />
      <el-table-column prop="create_time" label="添加时间" />
      <el-table-column label="操作">
        <template #default="scope">
          <el-button type="danger" link @click="handleDel(scope.row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getFavoriteList, addFavorite, delFavorite } from '../api'
import { ElMessage } from 'element-plus'

const tableData = ref([])
const form = ref({ code: '', name: '' })

async function loadList() {
  const res = await getFavoriteList()
  tableData.value = res.data
}

async function addStock() {
  await addFavorite(form.value)
  ElMessage.success('添加成功')
  form.value = { code: '', name: '' }
  loadList()
}
async function handleDel(id) {
  await delFavorite(id)
  ElMessage.success('已删除')
  loadList()
}

onMounted(() => loadList())
</script>
