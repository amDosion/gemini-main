import React from 'react';
import { ImageMaskEditControlsProps } from '../../types';
import { OpenAIImageControls } from './OpenAIImageControls';

type Props = ImageMaskEditControlsProps & React.ComponentProps<typeof OpenAIImageControls>;

export const ImageMaskEditControls: React.FC<Props> = (props) => (
  <OpenAIImageControls {...props} mode={props.mode ?? 'image-mask-edit'} />
);

export default ImageMaskEditControls;
