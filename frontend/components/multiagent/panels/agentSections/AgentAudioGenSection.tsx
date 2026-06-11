/**
 * Agent 节点音频生成参数面板。
 *
 * 1:1 抽离自 `AgentNodeConfigPanel.tsx` 音频生成 IIFE
 * （< 800 行合规拆分）。
 */

import React from 'react';
import { CustomNodeData } from '../../CustomNode';

export interface AgentAudioGenSectionProps {
  nodeData: CustomNodeData;
  updateNodeData: (patch: Partial<CustomNodeData>) => void;
}

export const AgentAudioGenSection: React.FC<AgentAudioGenSectionProps> = ({
  nodeData,
  updateNodeData,
}) => {
  const audioFormat = nodeData.agentAudioFormat || 'mp3';
  const audioSpeed = nodeData.agentSpeechSpeed ?? 1;
  return (
    <div className="space-y-3 p-2.5 rounded-lg border border-sky-500/20 bg-sky-500/5">
      <div className="text-xs text-sky-300 font-medium">音频生成参数</div>
      <div>
        <label className="block text-xs text-slate-500 mb-1">音色</label>
        <input
          type="text"
          value={nodeData.agentVoice || ''}
          onChange={(e) => updateNodeData({ agentVoice: e.target.value })}
          data-field-key="agentVoice"
          className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
          placeholder="留空时使用 provider 默认音色"
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-xs text-slate-500 mb-1">输出格式</label>
          <select
            value={audioFormat}
            onChange={(e) => updateNodeData({ agentAudioFormat: e.target.value })}
            data-field-key="agentAudioFormat"
            className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
          >
            <option value="mp3">MP3</option>
            <option value="wav">WAV</option>
            <option value="opus">OPUS</option>
            <option value="aac">AAC</option>
            <option value="flac">FLAC</option>
            <option value="pcm">PCM</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">语速</label>
          <input
            type="number"
            min={0.25}
            max={4}
            step={0.25}
            value={audioSpeed}
            onChange={(e) => {
              const raw = Number(e.target.value);
              const safe = Number.isFinite(raw) ? Math.max(0.25, Math.min(4, raw)) : 1;
              updateNodeData({ agentSpeechSpeed: safe });
            }}
            data-field-key="agentSpeechSpeed"
            className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
          />
        </div>
      </div>
    </div>
  );
};
