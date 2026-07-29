# CLAUDE.md — AI 开发强制规范

## 架构重要约束
1. src 正式后端框架**禁止导入 streamlit**；所有新代码不得依赖 Streamlit
2. OLD_ENTRY 目录为遗留历史代码，仅用于临时调试查看，**禁止新增功能**
3. 外部交互统一走 `src/api` FastAPI 接口；不再开发任何页面脚本
4. 所有可视化需求：后端只输出结构化数据，前端独立渲染图表

## 分层架构 (API ← Service ← DB/LLM)

```
src/
├── config/     ← 配置中心 (.env → settings.py)
├── core/       ← 公共组件 (异常/日志/HTTP/工具)
├── models/     ← 数据模型 (DTO/dataclass)
├── db/         ← 数据仓储 (纯 CRUD，禁止业务逻辑)
├── llm/        ← LLM 客户端 (抽象基类 + 豆包/DeepSeek)
├── service/    ← 业务服务 (组合 repo + 计算 + LLM)
└── ui/         ← Streamlit 页面 (仅交互与渲染)
```

## 强制规则

### 1. 依赖方向 (禁止反向导入)
- ✅ UI → Service → DB/LLM
- ❌ DB → Service, Service → UI, 任何反向导入

### 2. DB 层 (Repository)
- ✅ 数据库连接、单表 CRUD、建索引
- ❌ 指标计算、业务判断、调用 Service、调用 LLM
- 方法签名示例: `query_kline(code, start, end) -> List[dict]`

### 3. Service 层 (核心)
- ✅ 组合多个 repo、指标运算、数据清洗、调用 LLM
- ❌ 导入 UI 模块、直接写 SQL、渲染代码
- 未来切换 FastAPI 时 100% 复用

### 4. LLM 层
- 上层只依赖 `BaseLLMClient` 抽象接口
- 切换模型只需新增客户端实现

### 5. UI 层 (最外层)
- ✅ 接收参数、调用 Service、渲染结果
- ❌ SQL、指标计算、复杂数据处理、爬虫

### 6. 网络请求
- 所有外部 API 调用统一使用 `core/http_client.safe_request()`
- 包含: 超时 30s、重试 3 次、令牌桶限流 10 RPM

### 7. 配置
- 所有密钥/Token/URL 从 `src/config/settings.py` 读取
- settings.py 从 `.env` 加载，有合理默认值

### 8. 迁移规范（新旧共存模式）
- 新代码全部放在 src 目录；禁止修改 OLD_ENTRY 内部旧业务代码
- 模块迁移必须通过 `src/compat/adapter` 增加开关灰度切换
- 迁移完成后，对比新旧输出数据，结果一致才算验收通过
- 未验证稳定前，不能直接删除旧逻辑

### 9. 编码约束
- 所有函数使用 `@trace_cost` 增加耗时监控
- 业务异常使用自定义 BaseBusinessException，禁止裸 except
- 配置全部读取 .env，严禁硬编码 Token、路径、参数
- DataFrame 与业务对象转换统一使用 `src/core/data_convert`
- LLM 调用统一通过 `LLMFactory.get_client()` 获取客户端

### 10. 修改完成后自查
- [ ] 是否存在层间非法耦合（反向 import）
- [ ] DB 层是否混入了业务计算
- [ ] UI 层是否有 SQL、爬虫代码
- [ ] 外部请求是否经过 http_client 保护
- [ ] 新模块是否有 `@trace_cost` 耗时埋点
- [ ] 新模块是否有日志输出
- [ ] `python -m py_compile <changed>` 通过
- [ ] `python test_base.py` 通过
