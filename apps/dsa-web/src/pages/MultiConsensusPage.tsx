/**
 * 多模型共识预测系统 — React 版
 * 融合时序、因子、资金、舆情、产业五大模型，动态加权共识
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { TrendingUp, RefreshCw, Shield } from 'lucide-react';
import { getMultiModelChartOption } from '../utils/echartsTechOptions';

interface ModelWeight { name: string; weight: number; win_rate: number }
interface ConsensusData { consensus_score: number; trend: string; confidence: number; valid_model_count: number; total_model_count: number }

const DEFAULT_WEIGHTS: ModelWeight[] = [
  { name: '时序预测模型', weight: 25, win_rate: 68 },
  { name: '多因子估值模型', weight: 25, win_rate: 72 },
  { name: '资金博弈模型', weight: 20, win_rate: 65 },
  { name: '舆情地缘模型', weight: 15, win_rate: 62 },
  { name: '产业景气模型', weight: 15, win_rate: 70 },
];

const DEFAULT_CONSENSUS: ConsensusData = { consensus_score: 0.5, trend: 'oscillation', confidence: 0, valid_model_count: 0, total_model_count: 5 };

export default function MultiConsensusPage() {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartIns = useRef<any>(null);
  const [loading, setLoading] = useState(false);
  const [consensus, setConsensus] = useState<ConsensusData>(DEFAULT_CONSENSUS);
  const [weights, setWeights] = useState<ModelWeight[]>([...DEFAULT_WEIGHTS]);
  const [details, setDetails] = useState<any[]>([]);

  const renderChart = useCallback(async (modelData: any[], consensusData: number[]) => {
    if (!chartRef.current) return;
    const echarts = (await import('echarts')).default;
    if (chartIns.current) chartIns.current.dispose();
    chartIns.current = echarts.init(chartRef.current);
    const opt = getMultiModelChartOption(
      modelData.map((m: any, i: number) => ({ name: DEFAULT_WEIGHTS[i]?.name ?? `Model ${i}`, data: m.data ?? [] })),
      consensusData,
    );
    chartIns.current.setOption(opt, true);
  }, []);

  const calcConsensus = useCallback(async () => {
    setLoading(true);
    try {
      // Demo: compute from weights (production: POST /api/forecast/multi-consensus)
      const wSum = weights.reduce((s, w) => s + w.weight, 0) || 1;
      const scores = weights.map((w, i) => ({
        name: w.name,
        score: +(0.45 + (w.win_rate / 200) + Math.random() * 0.1).toFixed(4),
        confidence: +(0.5 + w.win_rate / 200).toFixed(2),
        dynamic_weight: +((w.weight / wSum) * 100).toFixed(1),
        status: w.win_rate > 60 ? 'normal' : 'degraded',
      }));
      const totalScore = scores.reduce((s, m) => s + m.score * m.dynamic_weight, 0) / 100;
      setConsensus({
        consensus_score: +totalScore.toFixed(4),
        trend: totalScore > 0.55 ? 'up' : totalScore < 0.45 ? 'down' : 'oscillation',
        confidence: +(scores.reduce((s, m) => s + m.confidence, 0) / scores.length).toFixed(2),
        valid_model_count: scores.filter(m => m.status === 'normal').length,
        total_model_count: weights.length,
      });
      setDetails(scores);
      await renderChart(
        scores.map(m => ({ name: m.name, data: Array.from({ length: 20 }, (_, j) => +(m.score * 0.8 + Math.random() * 0.2 * m.score).toFixed(3)) })),
        Array.from({ length: 20 }, (_, j) => +(totalScore * 0.85 + Math.random() * 0.15).toFixed(3)),
      );
    } catch { setConsensus(DEFAULT_CONSENSUS); }
    finally { setLoading(false); }
  }, [weights, renderChart]);

  useEffect(() => { calcConsensus(); return () => { chartIns.current?.dispose(); }; }, []);

  useEffect(() => { const onResize = () => chartIns.current?.resize(); window.addEventListener('resize', onResize); return () => window.removeEventListener('resize', onResize); }, []);

  const trendColor = consensus.trend === 'up' ? '#36C9A8' : consensus.trend === 'down' ? '#F85454' : '#FFB845';
  const trendText = consensus.trend === 'up' ? '看多上涨' : consensus.trend === 'down' ? '看空下跌' : '震荡整理';

  return (
    <div style={{ padding: 20, maxWidth: 1600, margin: '0 auto' }}>
      {/* Header */}
      <div className="glass-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 20, marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 20, color: '#fff', marginBottom: 6 }}>多模型共识预测系统</h2>
          <p style={{ fontSize: 13, color: '#86909C' }}>融合时序、因子、资金、舆情、产业五大模型，动态加权共识，规避单模型偏差</p>
        </div>
        <button className={`dsa-btn ${loading ? 'dsa-btn-disabled' : ''}`} onClick={calcConsensus} disabled={loading}>
          {loading ? <span className="scan-line" style={{ display: 'inline-block', width: 100, height: 20 }} /> : <><RefreshCw size={14} style={{ marginRight: 6 }} />重新计算共识</>}
        </button>
      </div>

      {/* Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 20 }}>
        {[
          { label: '共识趋势判定', value: trendText, color: trendColor, glow: consensus.trend !== 'oscillation' },
          { label: '共识置信得分', value: consensus.consensus_score.toFixed(4), color: '#2388FF', glow: false },
          { label: '模型置信度', value: consensus.confidence.toFixed(2), color: '#86909C', glow: false },
          { label: '有效/总模型', value: `${consensus.valid_model_count} / ${consensus.total_model_count}`, color: '#36C9A8', glow: false },
        ].map(c => (
          <div key={c.label} className="glass-card" style={{ textAlign: 'center', padding: '20px 10px', borderColor: c.glow ? trendColor : undefined, boxShadow: c.glow ? `0 0 20px ${trendColor}20` : undefined }}>
            <div style={{ fontSize: 13, color: '#86909C', marginBottom: 8 }}>{c.label}</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: c.color }}>{c.value}</div>
          </div>
        ))}
      </div>

      {/* Main: Weights + Chart */}
      <div style={{ display: 'flex', gap: 20, marginBottom: 20 }}>
        {/* Left: Weight panel */}
        <div className="glass-card" style={{ width: 320, flexShrink: 0, padding: 20 }}>
          <h3 style={{ fontSize: 16, color: '#fff', marginBottom: 6, borderLeft: '3px solid #2388FF', paddingLeft: 8 }}>模型动态权重</h3>
          <p style={{ fontSize: 12, color: '#86909C', marginBottom: 20 }}>基于近期胜率自适应，支持手动微调</p>
          {weights.map((w, i) => (
            <div key={w.name} style={{ marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 14, color: '#E5E6EB' }}>{w.name}</span>
                <span style={{ fontSize: 12, color: '#FFB845' }}>胜率：{w.win_rate}%</span>
              </div>
              <input type="range" min={1} max={50} value={w.weight}
                onChange={e => { const nw = [...weights]; nw[i] = { ...nw[i], weight: +e.target.value }; setWeights(nw); }}
                style={{ width: '100%', accentColor: '#2388FF' }} />
              <div style={{ fontSize: 12, color: '#86909C', marginTop: 4 }}>权重：{w.weight}%</div>
            </div>
          ))}
          <button className="dsa-btn dsa-btn-success" onClick={() => { setWeights([...DEFAULT_WEIGHTS]); setTimeout(calcConsensus, 100); }} style={{ marginTop: 10, width: '100%' }}>
            <RefreshCw size={14} style={{ marginRight: 6 }} />恢复自适应权重
          </button>
        </div>

        {/* Right: Chart */}
        <div className="glass-card" style={{ flex: 1, padding: 20, minHeight: 480 }}>
          <h3 style={{ fontSize: 16, color: '#fff', marginBottom: 12, borderLeft: '3px solid #2388FF', paddingLeft: 8 }}>多模型走势对比 & 共识拟合曲线</h3>
          <div ref={chartRef} style={{ height: 420 }} />
        </div>
      </div>

      {/* Model Details Table */}
      <div className="glass-card" style={{ padding: 20 }}>
        <h3 style={{ fontSize: 16, color: '#fff', marginBottom: 12, borderLeft: '3px solid #2388FF', paddingLeft: 8 }}>模型打分明细</h3>
        <table className="dsa-tech-table">
          <thead><tr><th>模型名称</th><th>得分</th><th>置信度</th><th>动态权重</th><th>状态</th></tr></thead>
          <tbody>
            {details.map((d, i) => (
              <tr key={i}><td>{d.name}</td><td>{d.score}</td><td>{d.confidence}</td><td>{d.dynamic_weight}%</td>
                <td><span style={{ color: d.status === 'normal' ? '#36C9A8' : '#F85454', background: d.status === 'normal' ? 'rgba(54,201,168,0.1)' : 'rgba(248,84,84,0.1)', padding: '2px 8px', borderRadius: 4, fontSize: 12 }}>
                  {d.status === 'normal' ? '正常参与' : '数据异常降级'}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
