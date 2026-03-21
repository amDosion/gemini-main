import {
  getPreferredReplayAnchorId,
  type StageReplayAnchor,
  type StageReplayContext,
  type StageReplayResult,
} from './stageReplayService';

export type StageReplayStatus =
  | 'idle'
  | 'snapshot_invalid'
  | 'ready'
  | 'replaying'
  | 'succeeded'
  | 'failed';

export interface StageReplayState {
  status: StageReplayStatus;
  context: StageReplayContext | null;
  selectedAnchorId: string;
  errorMessage: string;
  result: StageReplayResult | null;
}

export type StageReplayAction =
  | { type: 'hydrate_context'; context: StageReplayContext }
  | { type: 'select_anchor'; anchorId: string }
  | { type: 'start_replay' }
  | { type: 'replay_succeeded'; result: StageReplayResult }
  | { type: 'replay_failed'; errorMessage: string }
  | { type: 'clear_feedback' };

export const createInitialStageReplayState = (): StageReplayState => ({
  status: 'idle',
  context: null,
  selectedAnchorId: '',
  errorMessage: '',
  result: null,
});

const findAnchor = (context: StageReplayContext | null, anchorId: string): StageReplayAnchor | null => {
  if (!context || !anchorId) return null;
  return context.anchors.find((anchor) => anchor.id === anchorId) || null;
};

export const selectStageReplayAnchor = (state: StageReplayState): StageReplayAnchor | null =>
  findAnchor(state.context, state.selectedAnchorId);

export const getStageReplayStatusLabel = (status: StageReplayStatus): string => {
  if (status === 'snapshot_invalid') return '快照无效';
  if (status === 'ready') return '待回放';
  if (status === 'replaying') return '回放中';
  if (status === 'succeeded') return '回放成功';
  if (status === 'failed') return '回放失败';
  return '未初始化';
};

export const stageReplayReducer = (
  prev: StageReplayState,
  action: StageReplayAction
): StageReplayState => {
  switch (action.type) {
    case 'hydrate_context': {
      const context = action.context;
      const preferredAnchorId = getPreferredReplayAnchorId(context.anchors);
      const keepSelected = findAnchor(context, prev.selectedAnchorId);
      const selectedAnchorId = keepSelected?.canReplay ? keepSelected.id : preferredAnchorId;

      if (!context.valid) {
        return {
          status: 'snapshot_invalid',
          context,
          selectedAnchorId,
          errorMessage: context.message,
          result: null,
        };
      }

      if (!selectedAnchorId) {
        return {
          status: 'snapshot_invalid',
          context,
          selectedAnchorId: '',
          errorMessage: '缺少可选回放锚点，已禁用回放。',
          result: null,
        };
      }

      const selectedAnchor = findAnchor(context, selectedAnchorId);
      if (!selectedAnchor || !selectedAnchor.canReplay) {
        return {
          status: 'snapshot_invalid',
          context,
          selectedAnchorId,
          errorMessage: selectedAnchor?.blockedReason || '缺少可回放锚点，已禁用回放。',
          result: null,
        };
      }

      return {
        status: 'ready',
        context,
        selectedAnchorId,
        errorMessage: '',
        result: null,
      };
    }

    case 'select_anchor': {
      const selectedAnchor = findAnchor(prev.context, action.anchorId);
      if (!selectedAnchor) {
        return prev;
      }

      if (!prev.context?.valid) {
        return {
          ...prev,
          status: 'snapshot_invalid',
          selectedAnchorId: selectedAnchor.id,
          errorMessage: prev.context?.message || '当前快照无效。',
          result: null,
        };
      }

      if (!selectedAnchor.canReplay) {
        return {
          ...prev,
          status: 'ready',
          selectedAnchorId: selectedAnchor.id,
          errorMessage: selectedAnchor.blockedReason,
          result: null,
        };
      }

      return {
        ...prev,
        status: 'ready',
        selectedAnchorId: selectedAnchor.id,
        errorMessage: '',
        result: null,
      };
    }

    case 'start_replay': {
      if (!prev.context?.valid) {
        return {
          ...prev,
          status: 'snapshot_invalid',
          errorMessage: prev.context?.message || '当前快照无效，无法执行回放。',
          result: null,
        };
      }

      const selectedAnchor = findAnchor(prev.context, prev.selectedAnchorId);
      if (!selectedAnchor) {
        return {
          ...prev,
          status: 'failed',
          errorMessage: '未选择 replay 锚点。',
          result: null,
        };
      }

      if (!selectedAnchor.canReplay) {
        return {
          ...prev,
          status: 'failed',
          errorMessage: selectedAnchor.blockedReason || '当前锚点不可回放。',
          result: null,
        };
      }

      return {
        ...prev,
        status: 'replaying',
        errorMessage: '',
        result: null,
      };
    }

    case 'replay_succeeded': {
      if (prev.status !== 'replaying') {
        return prev;
      }
      return {
        ...prev,
        status: 'succeeded',
        errorMessage: '',
        result: action.result,
      };
    }

    case 'replay_failed':
      return {
        ...prev,
        status: 'failed',
        errorMessage: action.errorMessage,
        result: null,
      };

    case 'clear_feedback': {
      if (!prev.context?.valid) {
        return {
          ...prev,
          status: 'snapshot_invalid',
          errorMessage: prev.context?.message || '当前快照无效。',
          result: null,
        };
      }

      return {
        ...prev,
        status: 'ready',
        errorMessage: '',
        result: null,
      };
    }

    default:
      return prev;
  }
};
