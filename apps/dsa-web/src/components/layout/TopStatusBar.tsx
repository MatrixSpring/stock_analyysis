import React, { useEffect, useState } from 'react';
import { RefreshCw, Download, Zap } from 'lucide-react';
import { colors, statusColors } from '../../theme/tokens';

interface StatusBarProps {
  systemOnline?: boolean;
  todayIterated?: boolean;
  schedulerActive?: boolean;
  marketCycle?: 'TREND' | 'SHAKE' | 'DROP' | 'ICE';
  riskLevel?: 'low' | 'mid' | 'high';
}

const cycleLabels: Record<string, { label: string; color: string }> = {
  TREND: { label: '主升周期', color: statusColors.bull },
  SHAKE: { label: '震荡周期', color: statusColors.shake },
  DROP: { label: '退潮周期', color: statusColors.drop },
  ICE: { label: '冰点周期', color: statusColors.ice },
};

const TopStatusBar: React.FC<StatusBarProps> = ({
  systemOnline = true,
  todayIterated = true,
  schedulerActive = true,
  marketCycle = 'SHAKE',
  riskLevel = 'low',
}) => {
  const cycle = cycleLabels[marketCycle] || cycleLabels.SHAKE;
  const [riskPulse, setRiskPulse] = useState(false);

  useEffect(() => {
    if (riskLevel === 'high') {
      const t = setInterval(() => setRiskPulse((p) => !p), 600);
      return () => clearInterval(t);
    }
  }, [riskLevel]);

  return (
    <div style={{
      height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 24px', background: colors.card, borderBottom: `1px solid ${colors.border}`,
      position: 'sticky', top: 0, zIndex: 50, backdropFilter: 'blur(8px)',
    }}>
      {/* Left: system identity + status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <span style={{ fontSize: 16, fontWeight: 700, color: colors.primary }}>
          DSA 全市场自适应博弈策略系统
        </span>
        <StatusTag on={systemOnline} onLabel="运行中" offLabel="离线" color={statusColors.active} />
        <StatusTag on={todayIterated} onLabel="今日已迭代" offLabel="待迭代" color={statusColors.active} />
        <StatusTag on={schedulerActive} onLabel="9:15调度开启" offLabel="调度关闭" color={colors.warning} />
        <span style={{
          padding: '2px 10px', borderRadius: 4, fontSize: 12, fontWeight: 600,
          background: cycle.color + '22', color: cycle.color, border: `1px solid ${cycle.color}44`,
        }}>
          {cycle.label}
        </span>
      </div>

      {/* Right: quick actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {riskLevel === 'high' && (
          <span style={{
            padding: '2px 12px', borderRadius: 4, fontSize: 12, fontWeight: 700,
            background: riskPulse ? '#F53F3F44' : '#F53F3F22',
            color: colors.danger, border: `1px solid ${colors.danger}44`,
            transition: 'all 0.3s',
          }}>
            ⚠ 高风险预警
          </span>
        )}
        <QuickBtn icon={<RefreshCw size={14} />} label="手动刷新推演" />
        <QuickBtn icon={<Zap size={14} />} label="立即参数迭代" />
        <QuickBtn icon={<Download size={14} />} label="导出日报" />
      </div>
    </div>
  );
};

const StatusTag: React.FC<{ on: boolean; onLabel: string; offLabel: string; color: string }> = ({ on, onLabel, offLabel, color }) => (
  <span style={{
    padding: '2px 8px', borderRadius: 4, fontSize: 11,
    background: on ? color + '22' : '#6B728022',
    color: on ? color : '#6B7280',
  }}>
    {on ? onLabel : offLabel}
  </span>
);

const QuickBtn: React.FC<{ icon: React.ReactNode; label: string }> = ({ icon, label }) => (
  <button style={{
    display: 'flex', alignItems: 'center', gap: 6, padding: '5px 12px',
    borderRadius: 6, border: `1px solid ${colors.border}`, background: 'transparent',
    color: colors.textSecondary, cursor: 'pointer', fontSize: 13,
  }}>
    {icon} {label}
  </button>
);

export default TopStatusBar;
