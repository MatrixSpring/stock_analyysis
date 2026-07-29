import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: '看板', component: () => import('../views/Dashboard.vue') },
  { path: '/favorite', name: '自选股管理', component: () => import('../views/Favorite.vue') },
  { path: '/quote', name: '行情资金图表', component: () => import('../views/Quote.vue') },
  { path: '/news', name: '资讯舆情', component: () => import('../views/News.vue') },
  { path: '/ai-workbench', name: 'AI分析工作台', component: () => import('../views/AiWorkbench.vue') },
  { path: '/backtest', name: '策略回测', component: () => import('../views/Backtest.vue') },
  { path: '/industry-graph', name: '产业链图谱', component: () => import('../views/IndustryGraph.vue') },
  { path: '/industry-g6', name: 'G6产业图谱', component: () => import('../views/IndustryChainG6.vue') },
  { path: '/macro', name: '宏观流动性沙盘', component: () => import('../views/macro/MacroSandbox.vue') },
  { path: '/expert-chain', name: '专家产业链推演', component: () => import('../views/IndustryChainPanel.vue') },
  { path: '/expert-stock', name: '专家前瞻选股', component: () => import('../views/expert/ExpertStockAnalysis.vue') },
]

const router = createRouter({ history: createWebHashHistory(), routes })

export default router
