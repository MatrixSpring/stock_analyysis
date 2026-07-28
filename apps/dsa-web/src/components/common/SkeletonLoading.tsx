import React from 'react';

interface SkeletonLoadingProps {
  height?: number;
  width?: string;
  count?: number;
}

const SkeletonLoading: React.FC<SkeletonLoadingProps> = ({
  height = 180,
  width = '100%',
  count = 1,
}) => {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          style={{
            width,
            height,
            marginBottom: i < count - 1 ? '12px' : 0,
            borderRadius: '8px',
            background:
              'linear-gradient(90deg, #1e293b 25%, #334155 50%, #1e293b 75%)',
            backgroundSize: '200% 100%',
            animation: 'skeleton-shimmer 1.5s infinite',
          }}
        />
      ))}
      <style>{`
        @keyframes skeleton-shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </>
  );
};

export default SkeletonLoading;
