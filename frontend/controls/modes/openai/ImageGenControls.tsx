import React from 'react';
import { ImageGenControlsProps } from '../../types';
import { OpenAIImageControls } from './OpenAIImageControls';

export const ImageGenControls: React.FC<ImageGenControlsProps> = (props) => (
  <OpenAIImageControls {...props} mode="image-gen" />
);

export default ImageGenControls;
