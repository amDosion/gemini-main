import React from 'react';
import { RetainedImage } from '../../common/RetainedImage';

interface MaskPreviewImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  src: string;
}

export const MaskPreviewImage: React.FC<MaskPreviewImageProps> = ({ src, ...imgProps }) => {
  return <RetainedImage src={src} {...imgProps} />;
};
