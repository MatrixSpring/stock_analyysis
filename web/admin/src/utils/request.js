import axios from 'axios'

const baseUrl = import.meta.env.VITE_API_BASE_URL
const token = import.meta.env.VITE_API_TOKEN

const service = axios.create({
  baseURL: baseUrl,
  timeout: 30000
})

// 请求拦截器：携带鉴权Token
service.interceptors.request.use(config => {
  config.headers['X-API-Token'] = token
  return config
})

// 响应拦截器统一处理
service.interceptors.response.use(
  res => {
    return res.data
  },
  err => {
    const msg = err.response?.data?.detail || '接口请求失败'
    if (typeof window !== 'undefined' && window.$message) {
      window.$message.error(msg)
    }
    return Promise.reject(err)
  }
)

export default service
