# 同步任务基础配置
# 需要同步的股票池
SYNC_STOCK_CODES = [
    "000001",
    "600036",
    "601318"
]

# 默认同步起止日期；为空则自动同步最近30个交易日
DEFAULT_START_DATE = ""
DEFAULT_END_DATE = ""

# 是否开启各类任务开关
TASK_SWITCH = {
    "sync_kline": True,
    "sync_capital": True,
    "sync_news": True
}

# 定时任务周期（单位：秒，示例：86400=每日一次）
CRON_INTERVAL = 86400
