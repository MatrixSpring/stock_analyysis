import React, { useState, useEffect, useCallback } from 'react';
import { dashboardRequest } from '../../api/dashboardRequest';
import SkeletonLoading from '../../components/common/SkeletonLoading';
import EmptyState from '../../components/common/EmptyState';
import './SystemMonitor.css';

interface DataSourceStatus {
  status: string;
  msg: string;
  last_check: number;
}

interface TaskStat {
  total: number;
  pending: number;
  running: number;
  success: number;
  failed: number;
}

interface MonitorData {
  datasource_status: Record<string, DataSourceStatus>;
  llm_model_status: Record<string, { configured: boolean; status: string }>;
  llm_stats: Record<string, number>;
  task_stat: TaskStat;
  system_info: Record<string, number>;
  last_refresh: number;
  uptime_seconds: number;
}

const SystemMonitor: React.FC = () => {
  const [monitor, setMonitor] = useState<MonitorData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch('/api/system/monitor');
      const json = await res.json();
      if (json.code === 0) {
        setMonitor(json.data);
        setError(null);
      } else {
        setError(json.msg);
      }
    } catch (e) {
      setError('监控数据加载失败，请检查服务状态');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const timer = setInterval(fetchData, 60000);
    return () => clearInterval(timer);
  }, [fetchData]);

  if (loading) return <SkeletonLoading height={400} />;
  if (error) return <EmptyState tip={error} icon="⚠️" />;
  if (!monitor) return <EmptyState tip="暂无监控数据" />;

  const formatUptime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  };

  return (
    <div className="monitor-page">
      <div className="page-header fin-card">
        <h2>📊 系统全局监控大盘</h2>
        <p className="subtitle">
          运行时间: {formatUptime(monitor.uptime_seconds)} |
          最后刷新: {new Date(monitor.last_refresh * 1000).toLocaleTimeString()}
        </p>
      </div>

      <div className="card-grid">
        {/* 数据源状态 */}
        <div className="fin-card stat-card">
          <h3>🔌 数据源健康状态</h3>
          {Object.entries(monitor.datasource_status).map(([name, info]) => (
            <div key={name} className="status-row">
              <span className="source-name">{name}</span>
              <span className={`tag ${info.status}`}>
                {info.status === 'ok' ? '✅ 正常' : '❌ 异常'}
              </span>
              {info.msg && info.status !== 'ok' && (
                <span className="error-msg">{info.msg}</span>
              )}
            </div>
          ))}
          {Object.keys(monitor.datasource_status).length === 0 && (
            <EmptyState tip="暂无数据源状态" compact />
          )}
        </div>

        {/* LLM 模型状态 */}
        <div className="fin-card stat-card">
          <h3>🤖 LLM 模型状态</h3>
          {Object.entries(monitor.llm_model_status).map(([model, info]) => (
            <div key={model} className="status-row">
              <span className="source-name">{model}</span>
              <span className={`tag ${info.configured ? 'ok' : 'warn'}`}>
                {info.configured ? '✅ 已配置' : '⚠️ 未配置'}
              </span>
            </div>
          ))}
          {monitor.llm_stats && (
            <div className="llm-stats">
              <p>调用次数: {monitor.llm_stats.call_count || 0}</p>
              <p>成功率: {((monitor.llm_stats.success_rate || 0) * 100).toFixed(1)}%</p>
              <p>缓存命中: {monitor.llm_stats.cache_hits || 0}</p>
            </div>
          )}
        </div>

        {/* 任务统计 */}
        <div className="fin-card stat-card">
          <h3>📋 任务队列统计</h3>
          <div className="task-grid">
            <div className="task-item pending"><span className="num">{monitor.task_stat?.pending || 0}</span><span>排队</span></div>
            <div className="task-item running"><span className="num">{monitor.task_stat?.running || 0}</span><span>运行中</span></div>
            <div className="task-item success"><span className="num">{monitor.task_stat?.success || 0}</span><span>成功</span></div>
            <div className="task-item failed"><span className="num">{monitor.task_stat?.failed || 0}</span><span>失败</span></div>
          </div>
        </div>

        {/* 系统资源 */}
        <div className="fin-card stat-card">
          <h3>💻 系统资源</h3>
          {monitor.system_info?.note ? (
            <p className="note">{monitor.system_info.note}</p>
          ) : (
            <>
              <div className="resource-bar">
                <span>CPU</span>
                <div className="bar">
                  <div className="fill cpu" style={{ width: `${monitor.system_info?.cpu_percent || 0}%` }} />
                </div>
                <span>{monitor.system_info?.cpu_percent || 0}%</span>
              </div>
              <div className="resource-bar">
                <span>内存</span>
                <div className="bar">
                  <div className="fill memory" style={{ width: `${monitor.system_info?.memory_percent || 0}%` }} />
                </div>
                <span>{monitor.system_info?.memory_percent || 0}%</span>
              </div>
              <div className="resource-bar">
                <span>磁盘</span>
                <div className="bar">
                  <div className="fill disk" style={{ width: `${monitor.system_info?.disk_percent || 0}%` }} />
                </div>
                <span>{monitor.system_info?.disk_percent || 0}%</span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default SystemMonitor;
