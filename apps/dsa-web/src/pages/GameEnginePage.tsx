import React from 'react';
import { colors } from '../theme/tokens';
import DataCard from '../components/DataCard/DataCard';
import { gameSwitchMock } from '../mock/strategy';

const GameEnginePage: React.FC = () => (
  <div style={{ padding: 24 }}>
    <h2 style={{ fontSize: 20, fontWeight: 700, color: colors.text, marginBottom: 20 }}>
      多资金博弈引擎
    </h2>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
      <DataCard title="当日主导资金" value="公募基金" tagType="primary" />
      <DataCard title="博弈策略" value="赛道主升" subtitle="李义恩流派" />
      <DataCard title="市场周期" value="主升周期" tagType="success" />
      <DataCard title="博弈开关" value="8/12 开启" tagType="warning" tagLabel="可调节" />
    </div>

    {Object.entries(gameSwitchMock).map(([group, items]) => (
      <div key={group} style={{ background: colors.card, borderRadius: 8, padding: 20,
        border: `1px solid ${colors.border}`, marginBottom: 16 }}>
        <h3 style={{ fontSize: 16, color: colors.text, marginBottom: 12 }}>
          {group === 'li' ? '李义恩流派' : group === 'bo' ? '语菠萝流派' : '公募/机构流派'}
        </h3>
        {items.map((item) => (
          <div key={item.name} style={{ display: 'flex', justifyContent: 'space-between',
            alignItems: 'center', padding: '10px 0', borderBottom: `1px solid ${colors.border}` }}>
            <span style={{ color: colors.textSecondary, fontSize: 14 }}>{item.name}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <span style={{ fontSize: 12, color: colors.textSecondary }}>胜率 {item.rate}</span>
              <span style={{
                width: 40, height: 22, borderRadius: 11, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                background: item.status ? '#00B42A33' : '#6B728033',
                color: item.status ? '#00B42A' : '#6B7280', fontSize: 11, fontWeight: 600,
                transition: 'all 0.2s',
              }}>
                {item.status ? 'ON' : 'OFF'}
              </span>
            </div>
          </div>
        ))}
      </div>
    ))}
  </div>
);

export default GameEnginePage;
