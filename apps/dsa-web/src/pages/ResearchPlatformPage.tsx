import React from 'react';
import { colors } from '../theme/tokens';

const ResearchPlatformPage: React.FC = () => (
  <div style={{ padding: 24 }}>
    <h2 style={{ fontSize: 20, fontWeight: 700, color: colors.text, marginBottom: 20 }}>
      分层投研分析台
    </h2>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
      <div style={cardStyle('#165DFF')}>
        <h3 style={{ color: '#165DFF', marginBottom: 8 }}>短线前瞻（1-7日）</h3>
        <p style={{ color: colors.textSecondary, fontSize: 13, lineHeight: 1.8 }}>
          市场情绪偏暖，题材轮动加速。优先关注政策利好题材、低位补涨板块。推荐：消费复苏、科技细分题材。
        </p>
      </div>
      <div style={cardStyle('#00B42A')}>
        <h3 style={{ color: '#00B42A', marginBottom: 8 }}>中线前瞻（1-3月）</h3>
        <p style={{ color: colors.textSecondary, fontSize: 13, lineHeight: 1.8 }}>
          赛道景气度持续修复，机构中线布局意愿提升。推荐：AI算力、储能、机器人、高端制造赛道。
        </p>
      </div>
      <div style={cardStyle('#FF7D00')}>
        <h3 style={{ color: '#FF7D00', marginBottom: 8 }}>长线前瞻（季度）</h3>
        <p style={{ color: colors.textSecondary, fontSize: 13, lineHeight: 1.8 }}>
          产业政策持续落地，基本面拐点明确。推荐：国产替代、硬核科技、医疗创新、新能源产业链。
        </p>
      </div>
    </div>

    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <div style={{ background: colors.card, borderRadius: 8, padding: 20, border: `1px solid ${colors.border}` }}>
        <h3 style={{ color: colors.text, marginBottom: 12 }}>合规选股池</h3>
        {['高景气赛道龙头', '业绩预增核心标的', '国产替代硬核企业'].map((s) => (
          <div key={s} style={{ padding: '8px 0', borderBottom: `1px solid ${colors.border}`, color: colors.textSecondary, fontSize: 13 }}>✅ {s}</div>
        ))}
      </div>
      <div style={{ background: colors.card, borderRadius: 8, padding: 20, border: `1px solid ${colors.border}` }}>
        <h3 style={{ color: colors.danger, marginBottom: 12 }}>避雷清单</h3>
        {['高位纯炒作杂毛', '无业绩支撑题材股', '估值透支高位股'].map((s) => (
          <div key={s} style={{ padding: '8px 0', borderBottom: `1px solid ${colors.border}`, color: colors.textSecondary, fontSize: 13 }}>⚠️ {s}</div>
        ))}
      </div>
    </div>
  </div>
);

const cardStyle = (accent: string): React.CSSProperties => ({
  background: colors.card, borderRadius: 8, padding: 20,
  border: `1px solid ${colors.border}`, borderTop: `3px solid ${accent}`,
});

export default ResearchPlatformPage;
