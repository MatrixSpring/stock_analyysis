/**
 * v2.1.0 模块标题 + AI 研判小结 + 精简/详细模式切换
 */
import type React from 'react';
import { getModuleMode, setModuleMode } from '../../utils/moduleMode';

interface Props {
  title: string;
  aiText?: string;
  moduleName: string;
  isDetail: boolean;
  onToggle: (v: boolean) => void;
}

export const ModuleHeader: React.FC<Props> = ({ title, aiText, moduleName, isDetail, onToggle }) => {
  const handleToggle = () => {
    const next = !isDetail;
    setModuleMode(moduleName, next);
    onToggle(next);
  };

  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      marginBottom: 14, gap: 12, flexWrap: 'wrap',
    }}>
      <div>
        <span style={{ fontSize: 15, fontWeight: 600, color: '#fff' }}>{title}</span>
        {aiText && (
          <span style={{ fontSize: 12, color: '#86909C', marginLeft: 8 }}>
            【AI研判】{aiText}
          </span>
        )}
      </div>
      <button
        onClick={handleToggle}
        style={{
          padding: '3px 10px', borderRadius: 4, border: '1px solid rgba(255,255,255,0.1)',
          background: isDetail ? 'rgba(22,119,255,0.1)' : 'transparent',
          color: isDetail ? '#1677FF' : '#86909C', cursor: 'pointer', fontSize: 11,
        }}
      >
        {isDetail ? '详细模式' : '精简模式'}
      </button>
    </div>
  );
};
