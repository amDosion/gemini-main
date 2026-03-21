export const WORKFLOW_EXECUTION_ABORT_MESSAGE = 'Request cancelled by user';

export const isWorkflowExecutionAbortError = (error: unknown): boolean => {
  if (!(error instanceof Error)) return false;
  return (
    error.name === 'AbortError' ||
    error.message === WORKFLOW_EXECUTION_ABORT_MESSAGE
  );
};
