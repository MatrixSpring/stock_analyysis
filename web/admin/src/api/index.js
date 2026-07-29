import request from '../utils/request'

// 自选股
export const getFavoriteList = () => request.get('/favorite/list')
export const addFavorite = (data) => request.post(`/favorite/add?code=${data.code}&name=${data.name}`)
export const delFavorite = (favId) => request.delete(`/favorite/delete?fav_id=${favId}`)

// 股票K线行情
export const getStockKline = (code, start, end) => request.get(`/stock/kline?code=${code}&start_date=${start}&end_date=${end}`)

// 资金流向
export const getCapitalData = (code, start, end) => request.get(`/capital/daily?code=${code}&start_date=${start}&end_date=${end}`)

// 资讯
export const getStockNews = (code, start, end) => request.get(`/news/stock?code=${code}&start_date=${start}&end_date=${end}`)

// LLM AI — 统一接口，model_type 切换 doubao/deepseek
export const llmChat = (data) => request.post('/llm/chat', data)
export const llmNewsSummary = (data) => request.post('/llm/chat', { ...data, system_prompt: '你是资讯舆情分析专家' })
export const llmCapitalAnalyze = (data) => request.post('/llm/chat', { ...data, system_prompt: '你是资金流向分析专家' })

// 宏观流动性
export const getMacroCountries = () => request.get('/macro/countries')
export const macroCalcPath = (data) => request.post('/macro/sim/calcPath', data)
export const getMacroEvents = () => request.get('/macro/sim/events')
export const getMacroGraph = () => request.get('/macro/sim/graph')

// 策略回测
export const runBacktest = (data) => request.post('/backtest/run', data)
export const getBacktestTaskList = (code = '') => request.get(`/backtest/task/list${code ? '?code=' + code : ''}`)
