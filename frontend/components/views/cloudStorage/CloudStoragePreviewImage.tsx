import React from 'react';
import { RetainedImage } from '../../common/RetainedImage';

interface CloudStoragePreviewImageProps extends Omit<React.ImgHTMLAttributes<HTMLImageElement>, 'src'> {
  src: string;
  onRecoverPreviewError: (failedSrc?: string | null) => boolean;
}

export const CloudStoragePreviewImage: React.FC<CloudStoragePreviewImageProps> = ({
  src,
  onRecoverPreviewError,
  onError,
  ...imgProps
}) => {
  return (
    <RetainedImage
      src={src}
      retainBlobUrl={false}
      onRecoverImageError={onRecoverPreviewError}
      onError={onError}
      {...imgProps}
    />
  );
};
