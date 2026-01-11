import React, { useEffect, useState } from 'react';

/**
 * @interface ResearchProgressProps
 * @description Props for the ResearchProgress component.
 * @property {'in_progress' | 'completed' | 'failed'} status - The current status of the research.
 * @property {string} [thoughtSummary] - A summary of the research agent's current "thought" or step.
 * @property {number} [progress] - The overall progress of the research, from 0 to 100.
 */
interface ResearchProgressProps {
  status: 'in_progress' | 'completed' | 'failed';
  thoughtSummary?: string;
  progress?: number;
}

/**
 * @component ResearchProgress
 * @description Displays the progress of a deep research task, including status, a thought summary, and a progress bar.
 * @param {ResearchProgressProps} props - The props for the component.
 * @returns {JSX.Element} The rendered ResearchProgress component.
 */
const ResearchProgress: React.FC<ResearchProgressProps> = ({
  status,
  thoughtSummary,
  progress = 0,
}) => {
  const [animatedProgress, setAnimatedProgress] = useState(0);

  useEffect(() => {
    // Animate the progress bar width change
    const timeout = setTimeout(() => setAnimatedProgress(progress), 300);
    return () => clearTimeout(timeout);
  }, [progress]);

  const getStatusInfo = () => {
    switch (status) {
      case 'in_progress':
        return {
          text: 'Research in progress...',
          color: 'text-blue-400',
          bgColor: 'bg-blue-500',
        };
      case 'completed':
        return {
          text: 'Research Completed',
          color: 'text-green-400',
          bgColor: 'bg-green-500',
        };
      case 'failed':
        return {
          text: 'Research Failed',
          color: 'text-red-400',
          bgColor: 'bg-red-500',
        };
      default:
        return {
          text: 'Initializing...',
          color: 'text-gray-400',
          bgColor: 'bg-gray-500',
        };
    }
  };

  const statusInfo = getStatusInfo();

  return (
    <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-lg p-4 my-4 w-full max-w-2xl mx-auto shadow-lg animate-fade-in">
      <div className="flex justify-between items-center mb-2">
        <h3 className={`text-lg font-semibold ${statusInfo.color}`}>
          {statusInfo.text}
        </h3>
        <span className="text-sm font-medium text-gray-300">{Math.round(animatedProgress)}%</span>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-gray-700 rounded-full h-2.5 mb-4">
        <div
          className={`h-2.5 rounded-full ${statusInfo.bgColor} transition-all duration-500 ease-out`}
          style={{ width: `${animatedProgress}%` }}
          role="progressbar"
          aria-valuenow={animatedProgress}
          aria-valuemin={0}
          aria-valuemax={100}
        ></div>
      </div>

      {/* Thought Summary */}
      {thoughtSummary && (
        <div className="mt-3 pt-3 border-t border-gray-700">
          <div className="flex items-start">
            <span className="text-xl mr-3 pt-1">💡</span>
            <div className="flex-grow">
              <p className="text-sm text-gray-300 italic">{thoughtSummary}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ResearchProgress;
