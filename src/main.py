"""FastAPI 服务启动入口 — 生产增强版 + 静态文件服务"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from src.api.middlewares import global_exception_middleware
from src.api.v1 import stock_router, capital_router, news_router, industry_router, llm_router, favorite_router, backtest_router, graph_router, simulation_router, macro_router, expert_router
from src.core.prod_logger import api_logger
from src.core.alert import alert_client

app = FastAPI(title="Stock Analysis Backend", version="1.0")

# CORS
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# 全局异常中间件
app.middleware("http")(global_exception_middleware)

# 全局异常捕获 + 告警
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    api_logger.exception("服务全局异常")
    alert_client.send_msg("API服务异常", str(exc))
    return JSONResponse(status_code=500, content={"code": 500, "msg": "server error"})

# 注册路由
API_PREFIX = "/api/v1"
app.include_router(stock_router, prefix=API_PREFIX)
app.include_router(capital_router, prefix=API_PREFIX)
app.include_router(news_router, prefix=API_PREFIX)
app.include_router(industry_router, prefix=API_PREFIX)
app.include_router(llm_router, prefix=API_PREFIX)
app.include_router(favorite_router, prefix=API_PREFIX)
app.include_router(backtest_router, prefix=API_PREFIX)
app.include_router(graph_router, prefix=API_PREFIX)
app.include_router(simulation_router, prefix=API_PREFIX)
app.include_router(macro_router, prefix=API_PREFIX)
app.include_router(expert_router, prefix=API_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0"}


@app.get("/", response_class=HTMLResponse)
async def root():
    """根路径 — API 导航 + 前端入口"""
    routes_info = []
    for r in app.routes:
        if hasattr(r, 'path') and hasattr(r, 'methods'):
            if '/api/' in r.path:
                routes_info.append(f'<tr><td>{list(r.methods)[0] if r.methods else "?"}</td><td>{r.path}</td></tr>')

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>DSA 量化投研系统</title>
<style>
  body{{font-family:Inter,sans-serif;background:#0f172a;color:#e2e8f0;padding:40px}}
  h1{{color:#38bdf8}} table{{border-collapse:collapse;width:100%;max-width:900px;margin-top:20px}}
  th,td{{text-align:left;padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.08);font-size:13px}}
  th{{color:#94a3b8;font-size:11px}} a{{color:#38bdf8}}
  .badge{{background:rgba(56,189,248,0.15);color:#38bdf8;padding:2px 8px;border-radius:10px;font-size:11px;margin-right:8px}}
  .links{{margin-top:24px}} .links a{{margin-right:16px}}
</style></head>
<body>
  <h1>📊 DSA 量化投研系统</h1>
  <p>API 服务运行中 · 版本 1.0 · 30 个端点</p>
  <div class="links">
    <a href="/docs">📖 Swagger 文档</a>
    <a href="/health">💚 健康检查</a>
    <span class="badge">🔥 FastAPI</span>
    <span class="badge">🤖 豆包 AI</span>
    <span class="badge">📊 30 APIs</span>
  </div>
  <table><tr><th>方法</th><th>路径</th></tr>
    {''.join(routes_info[:20])}
  </table>
  <p style="margin-top:16px;color:#94a3b8;font-size:12px">前端管理面板请运行: cd web/admin && npm run dev</p>
</body></html>"""


# 静态文件服务（前端构建产物 + 旧版兼容）
OLD_WEB = Path(__file__).parent / "apps" / "dsa-web" / "dist"
NEW_ADMIN = Path(__file__).parent / "web" / "admin" / "dist"

if OLD_WEB.exists():
    app.mount("/assets", StaticFiles(directory=OLD_WEB / "assets"), name="old_assets")
    app.mount("/strategy", StaticFiles(directory=OLD_WEB), name="old_pages")

if NEW_ADMIN.exists():
    app.mount("/admin", StaticFiles(directory=NEW_ADMIN, html=True), name="new_admin")


if __name__ == "__main__":
    import uvicorn
    from src.config.prod_settings import settings
    uvicorn.run(app, host=settings.SERVER_HOST, port=settings.SERVER_PORT)
