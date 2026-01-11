import React, { useState } from 'react';

/**
 * @interface ResearchActionsProps
 * @description Props for the ResearchActions component.
 * @property {string} interactionId - The ID of the current interaction.
 * @property {(prompt: string) => void} onContinue - Callback function to continue research with a new prompt.
 * @property {(question: string) => void} onFollowup - Callback function for asking a follow-up question.
 * @property {() => void} onSummarize - Callback function to summarize the research.
 * @property {(format: string) => void} onFormat - Callback function to format the research results.
 */
interface ResearchActionsProps {
  interactionId: string;
  onContinue: (prompt: string) => void;
  onFollowup: (question: string) => void;
  onSummarize: () => void;
  onFormat: (format: string) => void;
}

/**
 * @component ResearchActions
 * @description A component that displays action buttons for completed research.
 * @param {ResearchActionsProps} props - The props for the component.
 * @returns {JSX.Element} The rendered ResearchActions component.
 */
const ResearchActions: React.FC<ResearchActionsProps> = ({
  interactionId,
  onContinue,
  onFollowup,
  onSummarize,
  onFormat,
}) => {
  const [followupQuestion, setFollowupQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFollowupSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!followupQuestion.trim()) return;

    setIsLoading(true);
    setError(null);
    try {
      await onFollowup(followupQuestion);
      setFollowupQuestion('');
    } catch (err) {
      setError('Failed to ask follow-up question. Please try again.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleActionClick = async (action: () => void) => {
    setIsLoading(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError('An error occurred. Please try again.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-lg p-4 mt-4 w-full max-w-2xl mx-auto shadow-lg">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <button
          onClick={() => handleActionClick(() => onContinue('Continue research based on the previous findings'))}
          disabled={isLoading}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-lg transition-colors duration-200 disabled:bg-gray-500 disabled:cursor-not-allowed flex items-center justify-center"
        >
          Continue Research
        </button>
        <form onSubmit={handleFollowupSubmit} className="flex gap-2">
          <input
            type="text"
            value={followupQuestion}
            onChange={(e) => setFollowupQuestion(e.target.value)}
            placeholder="Ask a follow-up question..."
            disabled={isLoading}
            className="flex-grow bg-gray-700 border border-gray-600 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-600"
          />
          <button
            type="submit"
            disabled={isLoading || !followupQuestion.trim()}
            className="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded-lg transition-colors duration-200 disabled:bg-gray-500 disabled:cursor-not-allowed"
          >
            Submit
          </button>
        </form>
        <button
          onClick={() => handleActionClick(onSummarize)}
          disabled={isLoading}
          className="bg-purple-600 hover:bg-purple-700 text-white font-bold py-2 px-4 rounded-lg transition-colors duration-200 disabled:bg-gray-500 disabled:cursor-not-allowed flex items-center justify-center"
        >
          Summarize
        </button>
        <button
          onClick={() => handleActionClick(() => onFormat('json'))}
          disabled={isLoading}
          className="bg-yellow-600 hover:bg-yellow-700 text-white font-bold py-2 px-4 rounded-lg transition-colors duration-200 disabled:bg-gray-500 disabled:cursor-not-allowed flex items-center justify-center"
        >
          Format as JSON
        </button>
      </div>
      {isLoading && (
        <div className="text-center mt-4 text-gray-300">
          <p>Processing...</p>
        </div>
      )}
      {error && (
        <div className="text-center mt-4 text-red-400">
          <p>{error}</p>
        </div>
      )}
    </div>
  );
};

export default ResearchActions;
