import React from 'react';
import { Link as LinkIcon } from 'lucide-react';
import { GroundingChunk } from '../../types/types';
import { toSafeNewTabUrl } from '../../utils/safeOpen';

interface GroundingSourcesProps {
  chunks?: GroundingChunk[];
}

interface GroundingSourceLink {
  index: number;
  title?: string;
  uri: string;
  hostname: string;
}

/** Returns the URI and hostname only when the scheme is http or https; otherwise undefined. */
function getSafeLink(uri: string): { uri: string; hostname: string } | undefined {
  const safeUri = toSafeNewTabUrl(uri);
  if (!safeUri) return undefined;

  try {
    const { hostname } = new URL(safeUri);
    return { uri: safeUri, hostname };
  } catch {
    return undefined;
  }
}

export const GroundingSources: React.FC<GroundingSourcesProps> = ({ chunks }) => {
  const sourceLinks = React.useMemo<GroundingSourceLink[]>(
    () =>
      (chunks || []).flatMap((chunk, idx) => {
        if (!chunk.web) return [];
        const link = getSafeLink(chunk.web.uri);
        if (!link) return [];
        return [
          {
            index: idx,
            title: chunk.web.title,
            ...link,
          },
        ];
      }),
    [chunks]
  );

  if (!chunks || chunks.length === 0) return null;

  return (
    <div className="bg-slate-900/40 rounded-lg p-3 border border-slate-700/50 mt-2">
      <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-2 flex items-center gap-1.5">
        <LinkIcon size={12} />
        Sources found
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {sourceLinks.map((source) => {
          return (
            <a
              key={`${source.uri}-${source.index}`}
              href={source.uri}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 p-2 rounded-lg hover:bg-slate-700/50 transition-all border border-slate-800 hover:border-slate-600 group/link bg-slate-900/50"
            >
              <div className="w-5 h-5 rounded bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0 text-[10px] text-slate-400 font-mono group-hover/link:text-blue-400 group-hover/link:border-blue-500/30">
                {source.index + 1}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-xs text-blue-300 truncate font-medium group-hover/link:text-blue-200">
                  {source.title}
                </div>
                <div className="text-[10px] text-slate-500 truncate">{source.hostname}</div>
              </div>
            </a>
          );
        })}
      </div>
    </div>
  );
};
