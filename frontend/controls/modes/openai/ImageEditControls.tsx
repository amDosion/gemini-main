import React from 'react';
import { ImageEditControlsProps } from '../../types';
import { OpenAIImageControls } from './OpenAIImageControls';

export const ImageEditControls: React.FC<ImageEditControlsProps> = (props) => (
  <OpenAIImageControls {...props} mode={props.mode ?? 'image-chat-edit'} />
);

export default ImageEditControls;
