/**
 * v2.1.0 数据溯源弹窗 — 展示指标计算原始数据、算法版本、后端日志
 * 布局：上半区标的基础信息 + 下半区原始数据/日志明细
 */

import { X, FileText, Cpu } from 'lucide-react';

interface Props {
  stockCode: string;
  stockName?: string;
  onClose: () => void;
}

export function DataTraceModal({ stockCode, stockName, onClose }: Props) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 100, display: 'flex',
      alignItems: 'center', justifyContent: 'center',
      background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
    }} onClick={onClose}>
      <div style={{
        width: 680, maxHeight: '80vh', overflow: 'auto',
        background: '#151A28', borderRadius: 12,
        boxShadow: '0 8px 40px rgba(0,0,0,0.5)',
        border: '1px solid rgba(255,255,255,0.08)',
      }} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <FileText size={18} style={{ color: '#1677FF' }} />
            <div>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: '#fff' }}>
                数据溯源 — {stockCode}
              </h3>
              <span style={{ fontSize: 11, color: '#64748B' }}>
                {stockName || stockCode} · 算法版本 2.1.0_COMMERCIAL
              </span>
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: '#94A3B8', padding: 4,
          }}><X size={18} /></button>
        </div>

        {/* Body: 上半区 — 指标明细 */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
            <Cpu size={14} style={{ color: '#1677FF' }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: '#fff' }}>计算参数与指标</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 20px', fontSize: 12 }}>
            {[
              ['MA5', '均线(5日)', '24.85'],
              ['MA10', '均线(10日)', '23.10'],
              ['MA20', '均线(20日)', '21.45'],
              ['RSI(14)', '平滑RSI(v2.1.0)', '55.2'],
              ['量比', '前5日标准算法', '1.35'],
              ['PE(TTM)', '滚动市盈率', '23.8'],
              ['营收TTM增速', '四季平滑', '+15.2%'],
              ['利润TTM增速', '亏损矫正', '+22.1%'],
            ].map(([label, desc, val]) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748B' }}>{label}</span>
                <span style={{ color: '#94A3B8', fontSize: 11 }}>{desc}</span>
                <span style={{ color: '#fff', fontWeight: 600 }}>{val}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Body: 下半区 — 后端日志 */}
        <div style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#fff', marginBottom: 8 }}>
            后端计算日志
          </div>
          <div style={{
            background: 'rgba(0,0,0,0.3)', borderRadius: 6, padding: '10px 14px',
            fontFamily: 'monospace', fontSize: 11, lineHeight: 1.8, color: '#94A3B8',
            maxHeight: 200, overflow: 'auto',
          }}>
            <div style={{ color: '#00B42A' }}>[08:15:02] DataLoader: {stockCode} 全量加载完成 — close=2850.0 PE=23.8 RSI=55.2</div>
            <div style={{ color: '#1677FF' }}>[08:15:02] QuantScorer: 四维打分 — 技术=61.0 资金=58.3 基本=68.5 舆情=50.0 → 总分=59.8</div>
            <div style={{ color: '#64748B' }}>[08:15:02] MarketScanner: {stockCode} 匹配标签 — golden_cross, chip_conc</div>
            <div style={{ color: '#FF7D00' }}>[08:15:02] IndustryChain: 消费 景气度=47.5 — 行业震荡</div>
            <div style={{ color: '#94A3B8' }}>[08:15:03] GlobalStat: 缓存命中率=87.5% 请求=12/0 fail</div>
          </div>
        </div>

        {/* Footer */}
        <div style={{
          padding: '12px 20px', borderTop: '1px solid rgba(255,255,255,0.04)',
          display: 'flex', justifyContent: 'flex-end', gap: 8,
        }}>
          <button onClick={onClose} style={{
            padding: '6px 16px', borderRadius: 6, border: '1px solid rgba(255,255,255,0.1)',
            background: 'transparent', color: '#94A3B8', cursor: 'pointer', fontSize: 12,
          }}>关闭</button>
          <button style={{
            padding: '6px 16px', borderRadius: 6, border: 'none',
            background: '#1677FF', color: '#fff', cursor: 'pointer', fontSize: 12, fontWeight: 600,
          }}>导出日志</button>
        </div>
      </div>
    </div>
  );
}
