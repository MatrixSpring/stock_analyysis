<template>
  <el-container style="height: 100vh;">
    <el-aside width="240px">
      <el-menu
        router
        :default-active="$route.path"
        class="el-menu-vertical-demo"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
      >
        <el-menu-item index="/dashboard"><el-icon><House /></el-icon> 数据看板</el-menu-item>
        <el-menu-item index="/favorite"><el-icon><Collection /></el-icon> 自选股管理</el-menu-item>
        <el-menu-item index="/quote"><el-icon><TrendCharts /></el-icon> 行情资金图表</el-menu-item>
        <el-menu-item index="/news"><el-icon><Document /></el-icon> 资讯舆情</el-menu-item>
        <el-menu-item index="/ai-workbench"><el-icon><ChatDotRound /></el-icon> AI分析工作台</el-menu-item>
        <el-menu-item index="/backtest"><el-icon><DataLine /></el-icon> 策略回测</el-menu-item>
        <el-menu-item index="/industry-graph"><el-icon><Share /></el-icon> 产业链图谱</el-menu-item>
        <el-menu-item index="/industry-g6"><el-icon><Connection /></el-icon> G6产业图谱</el-menu-item>
        <el-menu-item index="/macro"><el-icon><Money /></el-icon> 宏观流动性沙盘</el-menu-item>
        <el-menu-item index="/expert-stock"><el-icon><MagicStick /></el-icon> 专家前瞻选股</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { House, Collection, TrendCharts, Document, ChatDotRound, DataLine, Share, Connection, Money, MagicStick } from '@element-plus/icons-vue'
</script>

<style>
* { margin: 0; padding: 0; }
</style>
