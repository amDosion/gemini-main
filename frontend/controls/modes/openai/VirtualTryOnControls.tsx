import React from 'react';
import { VirtualTryOnControlsProps } from '../../types';
import { OpenAIImageControls } from './OpenAIImageControls';

type Props = VirtualTryOnControlsProps & React.ComponentProps<typeof OpenAIImageControls>;

export const VirtualTryOnControls: React.FC<Props> = (props) => (
  <OpenAIImageControls {...props} mode={props.mode ?? 'virtual-try-on'} />
);

export default VirtualTryOnControls;
