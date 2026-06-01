import React, { useMemo } from 'react';
import { createGeneratedThumb, type FileKind } from './filePresentation';
import { RetainedImage } from '../../common/RetainedImage';

interface CloudStorageGeneratedThumbnailProps
  extends Omit<React.ImgHTMLAttributes<HTMLImageElement>, 'src'> {
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
  const src = useMemo(() => createGeneratedThumb(kind, ext), [kind, ext]);

  return <RetainedImage src={src} alt={alt} {...imgProps} />;
};
