import React from 'react';
import { ImageOutpaintControlsProps } from '../../types';
import { OpenAIImageControls } from './OpenAIImageControls';

type Props = ImageOutpaintControlsProps & React.ComponentProps<typeof OpenAIImageControls>;

export const ImageOutpaintControls: React.FC<Props> = (props) => (
  <OpenAIImageControls {...props} mode={props.mode ?? 'image-outpainting'} />
);

export default ImageOutpaintControls;
