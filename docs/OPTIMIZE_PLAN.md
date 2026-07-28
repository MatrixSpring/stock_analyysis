# stock_analyysis 全域优化实施方案

> 最后更新: 2026-07-28 | 版本: v1.0

---

## 改造原则

1. **增量迭代** — 原有业务代码全部保留，禁止直接删除函数
2. **灰度开关** — 所有新功能增加配置开关，一键启用/关闭，方便回滚
3. **向下兼容** — 接口结构体只新增字段，不删除原有字段
4. **数据兼容** — 历史 sqlite 缓存、分析报告 100% 兼容
5. **小 commit** — 每完成一个模块独立提交，方便回滚定位

---

## 阶段一｜P0 紧急缺陷修复（0~3 天）

| # | 任务 | 交付物 | 状态 |
|---|------|--------|------|
| 1 | 统一数据源适配器 | `core/data_adapter.py` | ✅ |
| 2 | 数据清洗过滤器 | `core/data_cleaner.py` | ✅ |
| 3 | LLM统一封装 | `core/llm_engine.py` | ✅ |
| 4 | 全局工具类 | `utils/time_utils.py`, `utils/exception_handler.py` | ✅ |
| 5 | 接口Pydantic校验 | `utils/exception_handler.py` | ✅ |
| 6 | Prompt配置化 | `config/prompt_config.yaml` | ✅ |
| 7 | 中心化配置 | `config/system_config.yaml` | ✅ |

## 阶段二｜P1 能力补齐（3~7 天）

| # | 任务 | 交付物 | 状态 |
|---|------|--------|------|
| 1 | 异步任务队列 | `core/task_queue.py` | ✅ |
| 2 | 系统监控采集 | `core/system_monitor.py` | ✅ |
| 3 | 监控后端接口 | `api/system/status_api.py` | ✅ |
| 4 | 监控前端页面 | `src/views/system/system-monitor.vue` | ✅ |
| 5 | 公共前端组件 | `EmptyState.vue`, `SkeletonLoading.vue` | ✅ |
| 6 | 回测升级 | 滑点、手续费、绩效指标 | ⏳ |
| 7 | 个股分析重构 | `stock-analysis.vue` 结构化展示 | ⏳ |

## 阶段三｜P2 进阶功能（中长期迭代）

- [ ] Web 可视化因子编辑器
- [ ] 行业景气度、产业链上下游分析模块
- [ ] LLM Agent 工具调用能力
- [ ] 向量数据库接入（研报舆情 Embedding 检索）

## 阶段四｜P3 架构优化（可选）

- [ ] 数据服务解耦独立部署
- [ ] 全面接入 SSE 实时日志推送
- [ ] 插件化热插拔架构
- [ ] CI 自动化单元测试

---

## 文件变更范围

### 后端新增/修改

```
core/
├── data_adapter.py          # 统一数据源适配器（新增）
├── data_cleaner.py          # 数据清洗过滤器（新增）
├── llm_engine.py            # 统一LLM引擎（新增）
├── task_queue.py            # 异步任务队列（新增）
├── system_monitor.py        # 系统状态采集（新增）
api/system/
├── status_api.py            # 监控面板后端接口（新增）
config/
├── prompt_config.yaml       # 全部提示词配置（新增）
├── system_config.yaml       # 全局中心化配置（新增）
utils/
├── exception_handler.py     # 全局统一异常（新增）
├── time_utils.py            # 时区统一工具（新增）
```

### 前端 Vue 新增/改造

```
src/views/system/system-monitor.vue     # 全局监控大盘（新增）
src/components/EmptyState.vue           # 空状态组件（新增）
src/components/SkeletonLoading.vue      # 骨架屏组件（新增）
src/utils/http/error-handle.js          # 统一异常处理（新增）
src/views/stock/stock-analysis.vue      # 重构个股分析（待实施）
```

---

## 灰度开关配置

所有新增功能在 `config/system_config.yaml` 中统一管理：

```yaml
SWITCH:
  enable_data_adapter: true      # 是否启用统一数据源适配器
  enable_data_clean: true        # 是否启用数据清洗
  enable_llm_cache: true         # 是否启用LLM推理缓存
  enable_llm_truncate: true      # 是否启用超长文本截断
  enable_async_task: false       # 是否启用异步任务队列（需Redis）
  enable_system_monitor: true    # 是否启用系统监控
```

任一模块出现问题时，将对应开关设为 `false` 即可立即回退到原有逻辑。

---

## 部署步骤

```bash
# 1. 安装新增依赖
pip install redis rq tiktoken pytz pyyaml

# 2. 启动Redis（仅异步任务需要）
redis-server &

# 3. 启动RQ worker（仅异步任务需要）
rq worker stock_task &

# 4. 启动服务
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```
