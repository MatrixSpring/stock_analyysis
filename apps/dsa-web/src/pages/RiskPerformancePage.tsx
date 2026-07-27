import React from 'react';
import { colors } from '../theme/tokens';
import DataCard from '../components/DataCard/DataCard';
import { performanceMock, riskLogMock } from '../mock/strategy';

const RiskPerformancePage: React.FC = () => (
  <div style={{ padding: 24 }}>
    <h2 style={{ fontSize: 20, fontWeight: 700, color: colors.text, marginBottom: 20 }}>
      智能风控绩效台
    </h2>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
      <DataCard title="黑天鹅熔断" value="未触发" tagType="success" />
      <DataCard title="连续亏损" value="0 次" isBold />
      <DataCard title="最大回撤" value="3.2%" tagType="warning" />
      <DataCard title="动态仓位" value="65%" subtitle="基准65%→矫正58%" />
    </div>

    <div style={{ background: colors.card, borderRadius: 8, padding: 20, border: `1px solid ${colors.border}`, marginBottom: 16 }}>
      <h3 style={{ fontSize: 16, color: colors.text, marginBottom: 12 }}>策略绩效排行</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ background: '#273444', color: colors.text }}>
            <th style={th}>策略</th><th style={th}>评分</th><th style={th}>胜率</th><th style={th}>盈亏比</th><th style={th}>回撤</th><th style={th}>状态</th>
          </tr>
        </thead>
        <tbody>
          {performanceMock.map((p) => (
            <tr key={p.name} style={{ borderBottom: `1px solid ${colors.border}` }}>
              <td style={td}>{p.name}</td><td style={td}><strong>{p.score}</strong></td>
              <td style={td}>{p.winRate}</td><td style={td}>{p.ratio}</td><td style={td}>{p.draw}</td>
              <td style={td}>
                <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11,
                  background: p.tag === 'success' ? '#00B42A22' : p.tag === 'warning' ? '#FF7D0022' : '#F53F3F22',
                  color: p.tag === 'success' ? '#00B42A' : p.tag === 'warning' ? '#FF7D00' : '#F53F3F' }}>
                  {p.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>

    <div style={{ background: colors.card, borderRadius: 8, padding: 20, border: `1px solid ${colors.border}` }}>
      <h3 style={{ fontSize: 16, color: colors.text, marginBottom: 12 }}>风控日志</h3>
      {riskLogMock.map((r, i) => (
        <div key={i} style={{ padding: '8px 0', borderBottom: `1px solid ${colors.border}`,
          display: 'flex', gap: 16, fontSize: 13 }}>
          <span style={{ color: colors.textSecondary, minWidth: 120 }}>{r.time}</span>
          <span style={{ color: colors.warning, minWidth: 80 }}>[{r.type}]</span>
          <span style={{ color: colors.textSecondary }}>{r.desc} → {r.action}</span>
        </div>
      ))}
    </div>
  </div>
);

const th: React.CSSProperties = { padding: '10px 14px', textAlign: 'left', fontWeight: 600 };
const td: React.CSSProperties = { padding: '10px 14px', color: '#94A3B8' };

export default RiskPerformancePage;
