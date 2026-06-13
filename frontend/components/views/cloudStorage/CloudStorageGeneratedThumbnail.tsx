import React, { useId, useMemo } from 'react';
import { getGeneratedThumbPresentation, type FileKind } from './filePresentation';

interface CloudStorageGeneratedThumbnailProps
  extends Omit<React.SVGAttributes<SVGSVGElement>, 'children' | 'role'> {
  kind: FileKind;
  ext: string;
  alt: string;
}

export const CloudStorageGeneratedThumbnail: React.FC<CloudStorageGeneratedThumbnailProps> = ({
  kind,
  ext,
  alt,
  ...imgProps
}) => {
  const { bg, fg, label } = useMemo(
    () => getGeneratedThumbPresentation(kind, ext),
    [kind, ext]
  );
  const reactId = useId();
  const gradientId = `cloud-generated-thumb-${reactId.replace(/[^a-zA-Z0-9_-]/g, '')}`;

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 88 88"
      role="img"
      aria-label={alt}
      {...imgProps}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={bg} />
          <stop offset="100%" stopColor="#0f172a" />
        </linearGradient>
      </defs>
      <rect
        x="2"
        y="2"
        width="84"
        height="84"
        rx="14"
        fill={`url(#${gradientId})`}
        stroke="#1e293b"
        strokeWidth="2"
      />
      <text
        x="44"
        y="49"
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize="18"
        fontFamily="Arial, sans-serif"
        fontWeight="700"
        fill={fg}
      >
        {label}
      </text>
    </svg>
  );
};
