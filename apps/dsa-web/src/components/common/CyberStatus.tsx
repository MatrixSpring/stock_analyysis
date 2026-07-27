/** v3.0 科技风状态组件：加载 / 空数据 / 异常 / 计算中 */
import type React from 'react';

export const ScanLoading: React.FC<{ text?: string }> = ({ text = '加载中' }) => (
  <div className="scan-loading" style={{ display:'flex',alignItems:'center',justifyContent:'center',height:'100%',minHeight:120,color:'#86909C',fontSize:13,flexDirection:'column',gap:8 }}>
    <div style={{ width:32,height:32,border:'2px solid rgba(22,119,255,0.2)',borderTopColor:'#1677FF',borderRadius:'50%',animation:'cyber-pulse 1s linear infinite' }} />
    {text}
  </div>
);

export const EmptyState: React.FC<{ text?: string; icon?: string }> = ({ text = '暂无数据', icon = '📊' }) => (
  <div style={{ display:'flex',alignItems:'center',justifyContent:'center',height:'100%',minHeight:120,flexDirection:'column',gap:8,color:'#86909C',fontSize:13 }}>
    <span style={{ fontSize:32,opacity:0.5 }}>{icon}</span>
    <span>{text}</span>
  </div>
);

export const ErrorState: React.FC<{ text?: string; onRetry?: () => void }> = ({ text = '数据加载异常', onRetry }) => (
  <div style={{ display:'flex',alignItems:'center',justifyContent:'center',height:'100%',minHeight:120,flexDirection:'column',gap:10 }}>
    <span style={{ fontSize:13,color:'#F53F3F' }}>⚠ {text}</span>
    {onRetry && <button onClick={onRetry} style={{ padding:'4px 14px',borderRadius:4,border:'1px solid rgba(245,63,63,0.3)',background:'transparent',color:'#F53F3F',cursor:'pointer',fontSize:12 }}>重试</button>}
  </div>
);

export const ComputingState: React.FC<{ progress?: number }> = ({ progress }) => (
  <div style={{ display:'flex',alignItems:'center',justifyContent:'center',height:'100%',minHeight:120,flexDirection:'column',gap:10,color:'#86909C',fontSize:13 }}>
    <div className="scan-loading" style={{ width:'60%',height:40,background:'rgba(22,119,255,0.04)',borderRadius:6 }} />
    <span>预测模型计算中{progress !== undefined ? ` ${progress}%` : ''}</span>
  </div>
);
