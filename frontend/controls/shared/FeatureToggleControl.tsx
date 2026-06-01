import React from 'react';

export interface FeatureToggleControlProps {
  enabled: boolean;
  onEnabledChange: (enabled: boolean) => void;
  icon: React.ReactNode;
  label: string;
  activeClass?: string;
  disabled?: boolean;
  disabledHint?: string;
}

export const FeatureToggleControl: React.FC<FeatureToggleControlProps> = ({
  enabled,
  onEnabledChange,
  icon,
  label,
  activeClass = 'bg-blue-600',
  disabled = false,
  disabledHint,
}) => {
  const handleToggle = () => {
    if (disabled) {
      return;
    }
    onEnabledChange(!enabled);
  };

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between py-1">
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-xs text-slate-300">{label}</span>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          aria-label={label}
          aria-disabled={disabled}
          onClick={handleToggle}
          className={`w-10 h-6 flex items-center rounded-full p-1 transition-colors duration-200 ${
            disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'
          } ${enabled ? activeClass : 'bg-slate-600'}`}
        >
          <span
            className={`w-4 h-4 bg-white rounded-full shadow-md transform transition-transform duration-200 ${
              enabled ? 'translate-x-4' : 'translate-x-0'
            }`}
          />
        </button>
      </div>
      {disabledHint ? <p className="text-[10px] text-pink-300">{disabledHint}</p> : null}
    </div>
  );
};

export default FeatureToggleControl;
