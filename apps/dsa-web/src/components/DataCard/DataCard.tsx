import React from 'react';
import { colors, statusColors } from '../../theme/tokens';

interface DataCardProps {
  title: string;
  value: string | number;
  tagType?: 'success' | 'warning' | 'danger' | 'primary';
  tagLabel?: string;
  isBold?: boolean;
  subtitle?: string;
}

const tagColors: Record<string, string> = {
  success: statusColors.active,
  warning: colors.warning,
  danger: colors.danger,
  primary: colors.primary,
};

const DataCard: React.FC<DataCardProps> = ({ title, value, tagType, tagLabel, isBold, subtitle }) => (
  <div style={{
    background: colors.card, borderRadius: 8, padding: '20px',
    border: `1px solid ${colors.border}`, transition: 'all 0.2s',
    cursor: 'default',
  }}>
    <div style={{ fontSize: 13, color: colors.textSecondary, marginBottom: 8 }}>{title}</div>
    <div style={{
      fontSize: isBold ? 28 : 24, fontWeight: 700, color: colors.text,
      marginBottom: subtitle || tagType ? 8 : 0,
    }}>
      {value}
    </div>
    {tagType && (
      <span style={{
        padding: '2px 10px', borderRadius: 4, fontSize: 11, fontWeight: 600,
        background: (tagColors[tagType] || colors.primary) + '22',
        color: tagColors[tagType] || colors.primary,
      }}>
        {tagLabel || tagType}
      </span>
    )}
    {subtitle && (
      <div style={{ fontSize: 12, color: colors.textSecondary }}>{subtitle}</div>
    )}
  </div>
);

export default DataCard;
