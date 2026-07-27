import React from 'react';
import { colors } from '../theme/tokens';
import DataCard from '../components/DataCard/DataCard';
import { strategyListMock } from '../mock/strategy';

const StrategyCenterPage: React.FC = () => (
  <div style={{ padding: 24 }}>
    <h2 style={{ fontSize: 20, fontWeight: 700, color: colors.text, marginBottom: 20 }}>
      全自动策略中心
    </h2>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
      <DataCard title="运行中策略" value="4/5" tagType="success" tagLabel="健康" />
      <DataCard title="今日已迭代" value="已完成" tagType="primary" tagLabel="09:15" />
      <DataCard title="最优策略" value="公募赛道" subtitle="评分 94" />
      <DataCard title="融合权重" value="3 策略" tagType="warning" tagLabel="已融合" />
    </div>

    <div style={{ background: colors.card, borderRadius: 8, padding: 20, border: `1px solid ${colors.border}` }}>
      <h3 style={{ fontSize: 16, color: colors.text, marginBottom: 12 }}>策略总览</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ background: '#273444', color: colors.text }}>
            <th style={thStyle}>策略名称</th><th style={thStyle}>状态</th><th style={thStyle}>权重</th>
            <th style={thStyle}>上次迭代</th><th style={thStyle}>评分</th>
          </tr>
        </thead>
        <tbody>
          {strategyListMock.map((s) => (
            <tr key={s.id} style={{ borderBottom: `1px solid ${colors.border}` }}>
              <td style={tdStyle}>{s.name}</td>
              <td style={tdStyle}>
                <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11,
                  background: s.status === 'run' ? '#00B42A22' : s.status === 'bad' ? '#FF7D0022' : '#F53F3F22',
                  color: s.status === 'run' ? '#00B42A' : s.status === 'bad' ? '#FF7D00' : '#F53F3F' }}>
                  {s.statusText}
                </span>
              </td>
              <td style={tdStyle}>{s.weight}</td>
              <td style={tdStyle}>{s.lastIter}</td>
              <td style={tdStyle}><strong>{s.score}</strong></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

const thStyle: React.CSSProperties = { padding: '10px 14px', textAlign: 'left', fontWeight: 600 };
const tdStyle: React.CSSProperties = { padding: '10px 14px', color: '#94A3B8' };

export default StrategyCenterPage;
