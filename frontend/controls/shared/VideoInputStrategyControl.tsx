import React from 'react';
import { Route } from 'lucide-react';
import {
  getVideoInputStrategyDisplayLabel,
  type VideoInputStrategyOption,
} from '../../utils/videoSubmodeOptions';

interface VideoInputStrategyControlProps {
  strategies: VideoInputStrategyOption[];
  value: string;
  onChange: (value: string) => void;
}

const formatRequirementLabel = (strategy: VideoInputStrategyOption): string => {
  const requires = strategy.requires || [];
  if (requires.length === 0) {
    return '无需素材';
  }
  return requires
    .map((item) => {
      switch (item) {
        case 'source_image':
          return '首帧';
        case 'last_frame_image':
          return '尾帧';
        case 'source_video':
          return '视频';
        case 'reference_images':
        case 'video_edit_reference_images':
          return '参考图';
        case 'video_mask_image':
          return '遮罩';
        case 'driving_audio':
          return '音频';
        default:
          return item;
      }
    })
    .join(' + ');
};

export const VideoInputStrategyControl: React.FC<VideoInputStrategyControlProps> = ({
  strategies,
  value,
  onChange,
}) => {
  if (strategies.length === 0) {
    return null;
  }
  const selectedStrategy =
    strategies.find((strategy) => strategy.id === value) ?? strategies[0];

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Route size={12} className="text-cyan-400" />
        <span className="text-xs text-slate-300">子模式</span>
      </div>
      <select
        aria-label="子模式"
        value={selectedStrategy.id}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-200 focus:border-cyan-500 focus:outline-none"
      >
        {strategies.map((strategy) => (
          <option key={strategy.id} value={strategy.id}>
            {getVideoInputStrategyDisplayLabel(strategy)}（{formatRequirementLabel(strategy)}）
          </option>
        ))}
      </select>
    </div>
  );
};

export default VideoInputStrategyControl;
