import React from 'react';
import { Brain } from 'lucide-react';
import FeatureToggleControl from './FeatureToggleControl';

export interface ThinkingControlProps {
  enabled: boolean;
  onEnabledChange: (enabled: boolean) => void;
  disabled?: boolean;
  disabledHint?: string;
}

export const ThinkingControl: React.FC<ThinkingControlProps> = ({
  enabled,
  onEnabledChange,
  disabled = false,
  disabledHint,
}) => {
  return (
    <FeatureToggleControl
      enabled={enabled}
      onEnabledChange={onEnabledChange}
      icon={<Brain size={12} className="text-cyan-400" />}
      label="显示思考过程"
      activeClass="bg-cyan-600"
      disabled={disabled}
      disabledHint={disabledHint}
    />
  );
};

export default ThinkingControl;
