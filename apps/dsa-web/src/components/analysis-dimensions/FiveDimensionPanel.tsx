import React, { useState } from 'react';
import { ChevronDown, ChevronUp, TrendingUp, DollarSign, Building2, Globe, Factory } from 'lucide-react';

// ============================================================
// Types
// ============================================================

interface DimensionDetail {
  score: number;
  label: string;
  signals: string[];
  risk_flags: string[];
  summary: string;
  data_available: boolean;
  confidence: number;
  detail: Record<string, any>;
}

interface ResonanceData {
  dimensions: Record<string, DimensionDetail>;
  consensus_score: number;
  bullish_dimensions: number;
  bearish_dimensions: number;
  neutral_dimensions: number;
  dominant_dimension: string;
  divergence_warning: boolean;
}

interface FiveDimensionPanelProps {
  data: ResonanceData | null;
  loading?: boolean;
}

// ============================================================
// Dimension Icons & Colors
// ============================================================

const DIMENSION_CONFIG: Record<string, { icon: React.ReactNode; color: string }> = {
  technical:       { icon: <TrendingUp size={16} />, color: '#38bdf8' },
  capital_flow:    { icon: <DollarSign size={16} />,   color: '#34d399' },
  institutional:   { icon: <Building2 size={16} />,    color: '#a78bfa' },
  macro_geo:       { icon: <Globe size={16} />,        color: '#f472b6' },
  industry_sentiment: { icon: <Factory size={16} />,   color: '#fb923c' },
};

const ORDER = ['macro_geo', 'industry_sentiment', 'institutional', 'capital_flow', 'technical'];

// ============================================================
// Helpers
// ============================================================

function scoreColor(score: number): string {
  if (score >= 60) return '#22c55e';
  if (score <= 40) return '#ef4444';
  return '#f59e0b';
}

function scoreLabel(score: number): string {
  if (score >= 70) return '看多';
  if (score >= 55) return '偏多';
  if (score >= 45) return '中性';
  if (score >= 30) return '偏空';
  return '看空';
}

// ============================================================
// Single Dimension Row
// ============================================================

const DimensionRow: React.FC<{ dimKey: string; data: DimensionDetail }> = ({ dimKey, data }) => {
  const [expanded, setExpanded] = useState(false);
  const config = DIMENSION_CONFIG[dimKey] ?? { icon: null, color: '#94a3b8' };

  return (
    <div style={{
      marginBottom: 8, borderRadius: 8, overflow: 'hidden',
      border: `1px solid ${data.data_available ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.04)'}`,
      background: data.data_available ? 'rgba(255,255,255,0.02)' : 'rgba(255,255,255,0.01)',
      opacity: data.data_available ? 1 : 0.5,
    }}>
      {/* Header row */}
      <div
        onClick={() => data.data_available && setExpanded(!expanded)}
        style={{
          display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px',
          cursor: data.data_available ? 'pointer' : 'default',
        }}
      >
        <span style={{ color: config.color, display: 'flex' }}>{config.icon}</span>
        <span style={{ flex: 1, fontSize: 13, fontWeight: 600, color: '#e2e8f0' }}>
          {data.label}
        </span>
        {!data.data_available && (
          <span style={{ fontSize: 11, color: '#64748B' }}>无数据</span>
        )}
        {data.data_available && (
          <>
            <span style={{
              fontSize: 12, fontWeight: 700, color: scoreColor(data.score),
              minWidth: 36, textAlign: 'right',
            }}>
              {data.score.toFixed(0)}
            </span>
            <span style={{
              fontSize: 10, padding: '1px 6px', borderRadius: 10,
              background: `${scoreColor(data.score)}20`,
              color: scoreColor(data.score),
            }}>
              {scoreLabel(data.score)}
            </span>
            {expanded ? <ChevronUp size={14} color="#64748B" /> : <ChevronDown size={14} color="#64748B" />}
          </>
        )}
      </div>

      {/* Expanded content */}
      {expanded && data.data_available && (
        <div style={{ padding: '8px 14px 14px 14px', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          {/* Summary */}
          {data.summary && (
            <p style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.6, margin: '0 0 8px' }}>
              {data.summary}
            </p>
          )}

          {/* Signals */}
          {data.signals.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
              {data.signals.map((s, i) => (
                <span key={i} style={{
                  fontSize: 10, padding: '2px 6px', borderRadius: 4,
                  background: 'rgba(34, 197, 94, 0.1)', color: '#22c55e',
                }}>
                  {s}
                </span>
              ))}
            </div>
          )}

          {/* Risk flags */}
          {data.risk_flags.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
              {data.risk_flags.map((s, i) => (
                <span key={i} style={{
                  fontSize: 10, padding: '2px 6px', borderRadius: 4,
                  background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444',
                }}>
                  {s}
                </span>
              ))}
            </div>
          )}

          {/* Detail fields */}
          {Object.keys(data.detail).length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: 4 }}>
              {Object.entries(data.detail).slice(0, 6).map(([k, v]) => (
                <div key={k} style={{ fontSize: 10, color: '#64748B' }}>
                  {k}: <span style={{ color: '#CBD5E1' }}>{typeof v === 'number' ? Number(v).toFixed(2) : String(v)}</span>
                </div>
              ))}
            </div>
          )}

          {/* Confidence */}
          <div style={{ marginTop: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 10, color: '#475569' }}>置信度</span>
              <div style={{
                flex: 1, height: 3, borderRadius: 2, background: 'rgba(255,255,255,0.06)',
              }}>
                <div style={{
                  width: `${(data.confidence * 100).toFixed(0)}%`, height: '100%',
                  borderRadius: 2, background: config.color,
                  transition: 'width 0.3s',
                }} />
              </div>
              <span style={{ fontSize: 10, color: '#64748B' }}>{(data.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================
// Main Panel
// ============================================================

const FiveDimensionPanel: React.FC<FiveDimensionPanelProps> = ({ data, loading }) => {
  if (loading) {
    return (
      <div style={{
        padding: 24, textAlign: 'center', color: '#94a3b8', fontSize: 13,
        borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)',
        background: 'rgba(255,255,255,0.02)',
      }}>
        正在加载五维分析...
      </div>
    );
  }

  if (!data || Object.keys(data.dimensions).length === 0) {
    return (
      <div style={{
        padding: 24, textAlign: 'center', color: '#64748B', fontSize: 13,
        borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)',
        background: 'rgba(255,255,255,0.02)',
      }}>
        暂无五维分析数据。运行个股分析后自动生成。
      </div>
    );
  }

  return (
    <div style={{
      borderRadius: 10, border: '1px solid rgba(255,255,255,0.08)',
      background: 'rgba(15, 23, 42, 0.6)', padding: 16,
    }}>
      {/* Consensus header */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: '#e2e8f0', margin: 0 }}>
            五维共振分析
          </h3>
          <span style={{
            fontSize: 14, fontWeight: 700, color: scoreColor(data.consensus_score),
          }}>
            综合 {data.consensus_score.toFixed(0)}/100
          </span>
        </div>
        <div style={{ display: 'flex', gap: 16, fontSize: 11, color: '#64748B' }}>
          <span>🟢 看多 {data.bullish_dimensions}</span>
          <span>🔴 看空 {data.bearish_dimensions}</span>
          <span>⚪ 中性 {data.neutral_dimensions}</span>
          {data.divergence_warning && (
            <span style={{ color: '#f59e0b' }}>⚠️ 维度背离</span>
          )}
        </div>
      </div>

      {/* Dimension rows */}
      {ORDER.map((dimKey) => {
        const dim = data.dimensions[dimKey];
        if (!dim) return null;
        return <DimensionRow key={dimKey} dimKey={dimKey} data={dim} />;
      })}
    </div>
  );
};

export default FiveDimensionPanel;
export type { ResonanceData, DimensionDetail };
