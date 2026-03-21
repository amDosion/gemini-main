/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
*/

import React from 'react';

interface PromptInputProps {
  prompt: string;
  setPrompt: (prompt: string) => void;
  onSubmit: () => void;
  onAnalyze: () => void; // New prop for analysis only
  isLoading: boolean; // General loading state (disables inputs)
  isGenerating: boolean; // Specific generation state (shows spinner)
  isFirstRun: boolean;
  mode: 'image' | 'story' | 'video';
  setMode: (mode: 'image' | 'story' | 'video') => void;
}

const PromptInput: React.FC<PromptInputProps> = ({ 
  prompt, 
  setPrompt, 
  onSubmit,
  onAnalyze,
  isLoading, 
  isGenerating, 
  isFirstRun, 
  mode, 
  setMode 
}) => {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden flex flex-col transition-colors duration-200">
      <div className="px-4 py-2 md:py-3 border-b border-gray-100 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-900/50 flex justify-between items-center">
        <h2 className="text-base md:text-lg font-semibold text-gray-700 dark:text-gray-200">Prompt</h2>
      </div>
      
      <div className="p-3 md:p-5 flex flex-col gap-3 md:gap-4">
        <div 
          className={`w-full relative ${isLoading ? 'cursor-not-allowed' : ''}`} 
          title={isLoading ? "Input is disabled while processing your request. Please wait." : "Edit your prompt here."}
        >
            <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="an image of a large homemade breakfast..."
            className="w-full h-16 md:h-24 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg p-3 text-gray-800 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 focus:outline-none resize-none text-sm md:text-base leading-relaxed shadow-sm transition-all disabled:opacity-50 disabled:pointer-events-none"
            disabled={isLoading}
            />
        </div>
        
        <div className="flex flex-col sm:flex-row justify-between items-center gap-2">
            <div 
                className={`flex bg-gray-100 dark:bg-gray-700 p-1 rounded-lg transition-colors overflow-x-auto max-w-full ${isLoading ? 'cursor-not-allowed opacity-75' : ''}`} 
                title={isLoading ? "Mode selection is disabled while processing" : "Select generation mode"}
            >
                <button 
                    onClick={() => setMode('image')}
                    disabled={isLoading}
                    className={`flex items-center space-x-1 px-3 py-1.5 rounded-md transition-all text-xs md:text-sm font-medium disabled:pointer-events-none whitespace-nowrap ${
                        mode === 'image' 
                        ? 'bg-white dark:bg-gray-600 text-blue-600 dark:text-blue-400 shadow-sm ring-1 ring-black/5 dark:ring-white/5' 
                        : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-200/50 dark:hover:bg-gray-600/50'
                    }`}
                >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <span>Image</span>
                </button>
                <button 
                    onClick={() => setMode('story')}
                    disabled={isLoading}
                    className={`flex items-center space-x-1 px-3 py-1.5 rounded-md transition-all text-xs md:text-sm font-medium disabled:pointer-events-none whitespace-nowrap ${
                        mode === 'story' 
                        ? 'bg-white dark:bg-gray-600 text-blue-600 dark:text-blue-400 shadow-sm ring-1 ring-black/5 dark:ring-white/5' 
                        : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-200/50 dark:hover:bg-gray-600/50'
                    }`}
                >
                     <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                    </svg>
                    <span>Story</span>
                </button>
                 <button 
                    onClick={() => setMode('video')}
                    disabled={isLoading}
                    className={`flex items-center space-x-1 px-3 py-1.5 rounded-md transition-all text-xs md:text-sm font-medium disabled:pointer-events-none whitespace-nowrap ${
                        mode === 'video' 
                        ? 'bg-white dark:bg-gray-600 text-blue-600 dark:text-blue-400 shadow-sm ring-1 ring-black/5 dark:ring-white/5' 
                        : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-200/50 dark:hover:bg-gray-600/50'
                    }`}
                >
                     <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                       <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                     </svg>
                    <span>Video</span>
                </button>
            </div>

            <div 
                className={`flex gap-2 ${isLoading || !prompt ? "cursor-not-allowed" : ""}`}
                title={isLoading ? "Please wait for current operation to finish" : (!prompt ? "Please enter a prompt first" : "")}
            >
                <button
                onClick={(e) => {
                    e.preventDefault();
                    onAnalyze();
                }}
                disabled={isLoading || !prompt}
                className="bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-400 text-gray-700 dark:text-gray-200 font-semibold py-1.5 md:py-2 px-3 md:px-4 rounded-lg flex items-center justify-center transition-all shadow-sm text-sm md:text-base disabled:pointer-events-none"
                >
                    <span>Analyze Prompt</span>
                </button>

                <button
                onClick={(e) => {
                    e.preventDefault();
                    onSubmit();
                }}
                disabled={isLoading || !prompt}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-700 disabled:text-gray-500 dark:disabled:text-gray-600 disabled:pointer-events-none text-white font-semibold py-1.5 md:py-2 px-4 md:px-6 rounded-lg flex items-center justify-center space-x-2 transition-all shadow-sm hover:shadow hover:-translate-y-0.5 active:translate-y-0 text-sm md:text-base"
                >
                {isGenerating && (
                    <svg className="animate-spin h-4 w-4 md:h-5 md:w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                )}
                <span>{isFirstRun ? "Generate" : "Regenerate"}</span>
                </button>
            </div>
        </div>
      </div>
    </div>
  );
};

export default PromptInput;
