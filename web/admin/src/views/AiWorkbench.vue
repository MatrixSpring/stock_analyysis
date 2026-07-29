<template>
  <el-card header="LLM智能分析工作台">
    <!-- 全局配置区 -->
    <el-row :gutter="16">
      <el-col :span="5">
        <span style="font-size:13px;color:#606266">模型选择</span>
        <el-select v-model="config.model_type">
          <el-option label="豆包 Doubao" value="doubao" />
          <el-option label="DeepSeek" value="deepseek" />
        </el-select>
      </el-col>
      <el-col :span="7">
        <span style="font-size:13px;color:#606266">随机性 Temperature</span>
        <el-slider
          v-model="config.temperature"
          :min="0" :max="1" :step="0.05"
          show-input
        />
      </el-col>
      <el-col :span="6">
        <span style="font-size:13px;color:#606266">分析模式</span>
        <el-radio-group v-model="mode">
          <el-radio label="chat">通用对话</el-radio>
          <el-radio label="capital">资金解读</el-radio>
        </el-radio-group>
      </el-col>
      <el-col :span="6">
        <el-select
          v-model="selectedCode"
          v-if="mode === 'capital'"
          placeholder="选择股票"
        >
          <el-option
            v-for="item in favList"
            :key="item.id"
            :label="`${item.stock_name}(${item.stock_code})`"
            :value="item"
          />
        </el-select>
      </el-col>
    </el-row>

    <!-- 对话输入 -->
    <el-input
      v-model="prompt"
      type="textarea"
      rows="4"
      placeholder="输入问题，Shift+Enter换行，Enter发送"
      style="margin:16px 0"
      @keyup.enter.exact="sendQuery"
    />

    <el-row style="margin-bottom:12px">
      <el-button type="primary" @click="sendQuery" :loading="loading">发起分析</el-button>
      <el-button type="danger" @click="clearAllHistory">清空全部对话</el-button>
    </el-row>

    <el-divider>对话历史（本地持久化 · {{ chatHistory.length }} 条）</el-divider>

    <!-- 对话列表 -->
    <div class="chat-container">
      <div v-for="(item, idx) in chatHistory" :key="idx" class="chat-item">
        <el-card :style="{background: item.role === 'user' ? '#ecf5ff' : '#f4f4f4'}">
          <template #header>
            <span>{{ item.role === 'user' ? '👤 用户' : '🤖 AI' }}</span>
            <el-button link type="danger" style="float:right" @click="delRecord(idx)">删除</el-button>
          </template>
          <pre style="white-space:pre-wrap;margin:0;">{{ item.content }}</pre>
        </el-card>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getFavoriteList, llmChat, getCapitalData } from '../api'

const favList = ref([])
const mode = ref('chat')
const prompt = ref('')
const loading = ref(false)
const selectedCode = ref(null)

// 模型全局配置
const config = ref({
  model_type: 'doubao',
  temperature: 0.4
})

// 对话历史
const chatHistory = ref([])
const STORAGE_KEY = 'ai_chat_history'

function loadLocalHistory() {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (raw) {
    try { chatHistory.value = JSON.parse(raw) } catch (e) { chatHistory.value = [] }
  }
}

function saveHistoryToLocal() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(chatHistory.value.slice(-50)))  // 最多保留50条
}

watch(chatHistory, () => saveHistoryToLocal(), { deep: true })

function delRecord(index) { chatHistory.value.splice(index, 1) }

function clearAllHistory() {
  chatHistory.value = []
  ElMessage.success("已清空对话记录")
}

async function sendQuery() {
  if (!prompt.value.trim()) return ElMessage.warning("请输入内容")
  loading.value = true
  try {
    chatHistory.value.push({ role: 'user', content: prompt.value.trim() })

    if (mode.value === 'chat') {
      const resp = await llmChat({
        prompt: prompt.value,
        model_type: config.value.model_type,
        temperature: config.value.temperature,
        history: chatHistory.value.slice(0, -1),
      })
      chatHistory.value.push({
        role: 'assistant',
        content: resp.data?.content || resp.data?.analysis || '无返回'
      })
    } else {
      if (!selectedCode.value) {
        ElMessage.warning("请选择股票")
        chatHistory.value.pop()
        loading.value = false
        return
      }
      const cap = await getCapitalData(selectedCode.value.stock_code, "20260101", "20260728")
      const text = JSON.stringify((cap.data || []).slice(0, 5))
      const resp = await llmChat({
        prompt: `股票：${selectedCode.value.stock_name}(${selectedCode.value.stock_code})\n资金数据：${text}\n\n用户问题：${prompt.value}`,
        model_type: config.value.model_type,
        temperature: config.value.temperature,
        system_prompt: '你是资金流向分析专家，用2-3句话精准解读资金面。',
      })
      chatHistory.value.push({
        role: 'assistant',
        content: resp.data?.content || '无返回'
      })
    }
    prompt.value = ''
  } catch (err) {
    ElMessage.error('请求失败：' + err.message)
  } finally {
    loading.value = false
  }
}

async function init() {
  const res = await getFavoriteList()
  favList.value = res.data || []
  loadLocalHistory()
}

onMounted(init)
</script>

<style scoped>
.chat-container { max-height: 600px; overflow-y: auto; padding: 4px; }
.chat-item { margin-bottom: 12px; }
pre { font-family: "Microsoft YaHei", sans-serif; }
</style>
