/**
 * v2.1.0 升级版模块头部 — AI研判 + 周期选择 + 更新时间溯源 + 精简/详细切换
 * 对标 QMT/PTrade 精细化交互
 */
import type React from 'react';
import { getModuleMode, setModuleMode } from '../../utils/moduleMode';
import { PERIOD_OPTIONS } from '../../hooks/usePeriodSwitch';

interface Props {
  title: string;
  aiText?: string;
  moduleName: string;
  isDetail: boolean;
  onToggle: (v: boolean) => void;
  showPeriod?: boolean;
  period?: string;
  onPeriodChange?: (v: string) => void;
  updateTime?: string;
}

export const ModuleHeader: React.FC<Props> = ({
  title, aiText, moduleName, isDetail, onToggle,
  showPeriod = true, period, onPeriodChange, updateTime,
}) => {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
      marginBottom: 14, gap: 12, flexWrap: 'wrap',
    }}>
      <div>
        <span style={{ fontSize: 15, fontWeight: 600, color: '#fff' }}>{title}</span>
        {aiText && (
          <div style={{ fontSize: 12, color: '#86909C', marginTop: 2 }}>
            【AI研判】{aiText}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        {updateTime && (
          <span style={{ fontSize: 11, color: '#666' }}>更新：{updateTime}</span>
        )}

        {showPeriod && onPeriodChange && (
          <select
            value={period || '5'}
            onChange={e => onPeriodChange(e.target.value)}
            style={{
              padding: '2px 6px', borderRadius: 4, border: '1px solid rgba(255,255,255,0.1)',
              background: '#151A28', color: '#94A3B8', fontSize: 11, cursor: 'pointer',
            }}
          >
            {PERIOD_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        )}

        <button
          onClick={() => {
            const next = !isDetail;
            setModuleMode(moduleName, next);
            onToggle(next);
          }}
          style={{
            padding: '3px 10px', borderRadius: 4, border: '1px solid rgba(255,255,255,0.1)',
            background: isDetail ? 'rgba(22,119,255,0.1)' : 'transparent',
            color: isDetail ? '#1677FF' : '#86909C', cursor: 'pointer', fontSize: 11,
          }}
        >
          {isDetail ? '详细' : '精简'}
        </button>
      </div>
    </div>
  );
};
