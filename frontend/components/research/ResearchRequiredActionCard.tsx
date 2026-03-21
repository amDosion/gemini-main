import React, { useMemo, useState } from 'react';
import { AlertTriangle, Loader2, Send } from 'lucide-react';
import { ResearchRequiredAction } from '../../types/types';

interface ResearchRequiredActionCardProps {
  requiredAction: ResearchRequiredAction;
  onSubmitAction?: (selectedInput: unknown) => Promise<void> | void;
}

const toPrettyJson = (value: unknown): string => {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const extractInputOptions = (requiredAction: ResearchRequiredAction): string[] => {
  const values: string[] = [];
  const add = (input: unknown) => {
    if (typeof input === 'string' || typeof input === 'number' || typeof input === 'boolean') {
      values.push(String(input));
      return;
    }
    if (Array.isArray(input)) {
      input.forEach(add);
      return;
    }
    if (input && typeof input === 'object') {
      const record = input as Record<string, unknown>;
      if (Array.isArray(record.options)) {
        record.options.forEach(add);
        return;
      }
      if (Array.isArray(record.choices)) {
        record.choices.forEach(add);
        return;
      }
      if (typeof record.value === 'string') {
        values.push(record.value);
      }
    }
  };

  add(requiredAction.inputs || []);
  return [...new Set(values)].slice(0, 12);
};

const ResearchRequiredActionCard: React.FC<ResearchRequiredActionCardProps> = ({
  requiredAction,
  onSubmitAction,
}) => {
  const [submittingOption, setSubmittingOption] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [customInput, setCustomInput] = useState('');
  const actionName = requiredAction.act?.name || '需要外部动作';
  const options = useMemo(() => extractInputOptions(requiredAction), [requiredAction]);

  const submitValue = async (value: unknown, optionKey: string) => {
    if (!onSubmitAction) return;
    setSubmitError(null);
    setSubmittingOption(optionKey);
    try {
      await onSubmitAction(value);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setSubmitError(message || '提交动作失败');
    } finally {
      setSubmittingOption(null);
    }
  };

  const handleCustomSubmit = async () => {
    const trimmed = customInput.trim();
    if (!trimmed) return;

    try {
      const parsed = JSON.parse(trimmed);
      await submitValue(parsed, '__custom__');
      setCustomInput('');
      return;
    } catch {
      await submitValue(trimmed, '__custom__');
      setCustomInput('');
    }
  };

  return (
    <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-amber-100">
      <div className="flex items-center gap-2 text-sm font-medium">
        <AlertTriangle size={14} />
        <span>等待动作: {actionName}</span>
      </div>

      {options.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {options.map((option) => {
            const isSubmitting = submittingOption === option;
            return (
              <button
                key={option}
                onClick={() => void submitValue(option, option)}
                disabled={!onSubmitAction || !!submittingOption}
                className="inline-flex items-center gap-1 rounded-md border border-amber-300/35 bg-amber-400/10 px-2 py-1 text-xs hover:bg-amber-400/20 disabled:cursor-not-allowed disabled:opacity-60"
                title="提交该选项并继续研究"
              >
                {isSubmitting ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
                <span className="max-w-56 truncate">{option}</span>
              </button>
            );
          })}
        </div>
      )}

      <div className="mt-2 space-y-2">
        <textarea
          value={customInput}
          onChange={(event) => setCustomInput(event.target.value)}
          placeholder="自定义输入（支持 JSON 或纯文本）"
          className="w-full rounded-md border border-amber-300/30 bg-slate-950/60 p-2 text-xs text-amber-100 outline-none focus:border-amber-200/50"
          rows={3}
        />
        <button
          onClick={() => void handleCustomSubmit()}
          disabled={!onSubmitAction || !!submittingOption || !customInput.trim()}
          className="inline-flex items-center gap-1 rounded-md border border-amber-300/35 bg-amber-400/10 px-2 py-1 text-xs hover:bg-amber-400/20 disabled:cursor-not-allowed disabled:opacity-60"
          title="提交自定义结果并继续研究"
        >
          {submittingOption === '__custom__' ? (
            <Loader2 size={12} className="animate-spin" />
          ) : (
            <Send size={12} />
          )}
          <span>提交自定义结果</span>
        </button>
      </div>

      {!onSubmitAction && (
        <div className="mt-2 text-xs text-amber-200/80">当前会话未注册动作提交通道。</div>
      )}

      {submitError && (
        <div className="mt-2 text-xs text-red-300">{submitError}</div>
      )}

      <details className="mt-2">
        <summary className="cursor-pointer text-xs text-amber-200/80">查看动作详情</summary>
        <pre className="mt-1 overflow-x-auto rounded bg-slate-950/70 p-2 text-[11px] text-amber-100/90">
          {toPrettyJson(requiredAction)}
        </pre>
      </details>
    </div>
  );
};

export default ResearchRequiredActionCard;
