/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
*/

import React, { useState, useCallback, useEffect, useRef } from 'react';
import Header from './components/Header';
import PromptInput from './components/PromptInput';
import ClarificationCard from './components/ClarificationCard';
import BeliefGraph from './components/BeliefGraph';
import OutputDisplay from './components/OutputGallery';
import {
  parsePromptToBeliefGraph,
  generateClarifications,
  generateImagesFromPrompt,
  generateStoryFromPrompt,
  generateVideosFromPrompt,
  refinePromptWithAllUpdates,
} from './services/geminiService';
import { BeliefState, Clarification, GraphUpdate, Attribute } from './types';

// Removed duplicate global declaration for AIStudio to fix "Duplicate identifier" errors.
// Accessing window.aistudio via (window as any) to bypass type check if global type is missing or conflicting.

type Mode = 'image' | 'story' | 'video';
type ToolTab = 'clarify' | 'graph' | 'attributes';
type MobileView = 'editor' | 'preview';

function App() {
  const [prompt, setPrompt] = useState('a cat hosting a party for its animal friends');
  
  const [isGraphLoading, setIsGraphLoading] = useState(false);
  const [isAttributesLoading, setIsAttributesLoading] = useState(false);
  const [isClarificationsLoading, setIsClarificationsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isUpdatingPrompt, setIsUpdatingPrompt] = useState(false);
  
  const [isOutdated, setIsOutdated] = useState(false); 
  const [showModeChangePopup, setShowModeChangePopup] = useState(false);
  const [showInfoModal, setShowInfoModal] = useState(false);
  const [mode, setMode] = useState<Mode>('image');
  
  // Ref to track the current mode synchronously for async cancellation
  const modeRef = useRef<Mode>(mode);
  
  // Refs to track request IDs to prevent race conditions
  const analysisRequestIdRef = useRef(0);
  const generationRequestIdRef = useRef(0);

  const [images, setImages] = useState<string[]>([]);
  const [story, setStory] = useState<string | null>(null);
  const [video, setVideo] = useState<string | null>(null);
  const [galleryErrors, setGalleryErrors] = useState<Record<Mode, string | null>>({ image: null, story: null, video: null });
  const [requiresApiKey, setRequiresApiKey] = useState(false);
  
  const [beliefGraph, setBeliefGraph] = useState<BeliefState | null>(null);
  const [clarifications, setClarifications] = useState<Clarification[]>([]);
  const [answeredQuestions, setAnsweredQuestions] = useState<string[]>([]);
  const [skippedQuestions, setSkippedQuestions] = useState<string[]>([]); 
  const [hasGenerated, setHasGenerated] = useState(false);

  // --- OPTIMIZATION STATE ---
  const [lastAnalyzedPrompt, setLastAnalyzedPrompt] = useState<string | null>(null);
  const [lastAnalyzedMode, setLastAnalyzedMode] = useState<Mode | null>(null);

  // --- LIFTED STATE FOR PERSISTENCE ---
  const [pendingAttributeUpdates, setPendingAttributeUpdates] = useState<Record<string, string>>({});
  const [pendingRelationshipUpdates, setPendingRelationshipUpdates] = useState<Record<string, string>>({});
  const [pendingClarificationAnswers, setPendingClarificationAnswers] = useState<{[key: string]: string}>({});
  
  const [activeToolTab, setActiveToolTab] = useState<ToolTab>('clarify');
  const [mobileView, setMobileView] = useState<MobileView>('editor');

  const [isDarkMode, setIsDarkMode] = useState(false);
  const [statusNotification, setStatusNotification] = useState<string | null>(null);

  useEffect(() => {
    if (isGenerating) {
        setMobileView('preview');
    }
  }, [isGenerating]);

  // Sync modeRef with mode state
  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  // Sync Dark Mode to Body to prevent background mismatch during overscroll
  useEffect(() => {
      if (isDarkMode) {
          document.documentElement.classList.add('dark');
          document.body.style.backgroundColor = '#111827'; // gray-900
      } else {
          document.documentElement.classList.remove('dark');
          document.body.style.backgroundColor = '#f3f4f6'; // gray-100
      }
  }, [isDarkMode]);

  const clearPendingUpdates = () => {
    setPendingAttributeUpdates({});
    setPendingRelationshipUpdates({});
    setPendingClarificationAnswers({});
  };

  const handleStatusUpdate = useCallback((msg: string) => {
    setStatusNotification(msg);
  }, []);

  const handleModeChange = (newMode: Mode) => {
    if (newMode === mode) return;
    
    // Invalidate pending requests by incrementing IDs
    analysisRequestIdRef.current += 1;
    generationRequestIdRef.current += 1;
    
    setMode(newMode);
    
    // Interrupt active operations by resetting loading states immediately
    setIsGraphLoading(false);
    setIsAttributesLoading(false);
    setIsClarificationsLoading(false);
    setIsGenerating(false);
    setIsUpdatingPrompt(false);
    
    // Preserve Data & Mark Outdated
    // We no longer clear beliefGraph, clarifications, pending updates, or output data here.
    // We do NOT set isOutdated(true) here, as we want the previous results to be visible without overlay.
    setShowModeChangePopup(true);
    
    // Reset key requirement as it depends on the specific generation trigger
    setRequiresApiKey(false); 
  };

  const refreshAnalysis = useCallback(async (currentPrompt: string, currentAnsweredQuestions: string[], currentMode: Mode) => {
    // Generate a new request ID for this run
    const requestId = ++analysisRequestIdRef.current;

    // Helper to check if we should process results (only if mode hasn't changed AND this is the latest request)
    const isCurrent = () => modeRef.current === currentMode && analysisRequestIdRef.current === requestId;
    const safeStatusUpdate = (msg: string) => { if (isCurrent()) handleStatusUpdate(msg); };

    setIsGraphLoading(true);
    setIsAttributesLoading(true);
    setIsClarificationsLoading(true);

    // 1. Graph & Attributes Generation
    const graphPromise = parsePromptToBeliefGraph(currentPrompt, currentMode, safeStatusUpdate)
        .then(graphStructure => {
            if (isCurrent()) {
                if (graphStructure) setBeliefGraph(graphStructure);
            }
        })
        .catch(error => {
            console.error("Failed to parse belief graph:", error);
        })
        .finally(() => {
            if (isCurrent()) {
                setIsGraphLoading(false);
                setIsAttributesLoading(false);
            }
        });

    // 2. Clarifications Generation
    const clarificationPromise = generateClarifications(currentPrompt, currentAnsweredQuestions, currentMode, safeStatusUpdate)
        .then(generatedClarifications => {
            if (isCurrent()) setClarifications(generatedClarifications);
        })
        .catch(error => {
            console.error("Failed to generate clarifications:", error);
        })
        .finally(() => {
             if (isCurrent()) setIsClarificationsLoading(false);
        });

    if (isCurrent()) {
         // Optimization: Mark this prompt as analyzed immediately
         setLastAnalyzedPrompt(currentPrompt);
         setLastAnalyzedMode(currentMode);
    }
    
    // Return a promise that resolves when both tasks are complete (for processRequest await)
    return Promise.all([graphPromise, clarificationPromise]);
  }, [handleStatusUpdate]);

  const handleRefreshClarifications = useCallback(() => {
    // Increment analysis ID because clarifications are part of the analysis state
    const requestId = ++analysisRequestIdRef.current;
    
    const requestMode = mode;
    const isCurrent = () => modeRef.current === requestMode && analysisRequestIdRef.current === requestId;
    const safeStatusUpdate = (msg: string) => { if (isCurrent()) handleStatusUpdate(msg); };

    setIsClarificationsLoading(true);
    setPendingClarificationAnswers({});
    setStatusNotification(null);
    
    const currentQuestions = clarifications.map(c => c.question);
    const newSkipped = [...skippedQuestions, ...currentQuestions];
    setSkippedQuestions(newSkipped);

    // Use current prompt state to ensure we get questions relevant to user edits
    const currentPrompt = prompt;
    const excludeList = [...answeredQuestions, ...newSkipped];

    generateClarifications(currentPrompt, excludeList, requestMode, safeStatusUpdate)
        .then(newClarifications => {
            if (isCurrent()) setClarifications(newClarifications);
        })
        .catch(error => console.error("Failed to refresh clarifications:", error))
        .finally(() => {
             if (isCurrent()) {
                 setIsClarificationsLoading(false);
                 setStatusNotification(null);
             }
        });
  }, [prompt, answeredQuestions, mode, clarifications, skippedQuestions, handleStatusUpdate]);

  const processRequest = useCallback(async (
    currentPrompt: string, 
    currentAnsweredQuestions: string[], 
    currentMode: Mode,
    skipAnalysis: boolean = false,
    skipGeneration: boolean = false
  ) => {
    // Generate IDs
    const genRequestId = ++generationRequestIdRef.current;
    
    const requestMode = currentMode;
    const isGenCurrent = () => modeRef.current === requestMode && generationRequestIdRef.current === genRequestId;
    const safeGenStatusUpdate = (msg: string) => { if (isGenCurrent()) handleStatusUpdate(msg); };

    setGalleryErrors(prev => ({ ...prev, [requestMode]: null }));
    setRequiresApiKey(false);

    if (!skipGeneration) {
        // Clear ONLY the current mode's output and start loading
        if (requestMode === 'image') setImages([]);
        else if (requestMode === 'story') setStory(null);
        else if (requestMode === 'video') setVideo(null);
    }
    
    setIsOutdated(false); 
    setStatusNotification(null);
    setShowModeChangePopup(false); // Clear popup on new generation
    
    if (!skipAnalysis) {
        setBeliefGraph(null); 
        setClarifications([]);
        clearPendingUpdates();
        setSkippedQuestions([]); 
    }
    
    // --- Analysis Phase ---
    const analysisPromise = !skipAnalysis 
        ? refreshAnalysis(currentPrompt, currentAnsweredQuestions, currentMode)
        : Promise.resolve();

    // --- Generation Phase ---
    let generationPromise = Promise.resolve();

    if (!skipGeneration) {
        setIsGenerating(true);
        generationPromise = (async () => {
            try {
                if (requestMode === 'image') {
                    const generatedImages = await generateImagesFromPrompt(currentPrompt, safeGenStatusUpdate);
                    if (isGenCurrent()) setImages(generatedImages);
                } else if (requestMode === 'story') {
                    const generatedStory = await generateStoryFromPrompt(currentPrompt, safeGenStatusUpdate);
                    if (isGenCurrent()) setStory(generatedStory);
                } else if (requestMode === 'video') {
                    // Check for API Key first (Veo requirement)
                    const win = window as any;
                    if (win.aistudio && win.aistudio.hasSelectedApiKey) {
                        const hasKey = await win.aistudio.hasSelectedApiKey();
                        if (!hasKey) {
                            if (isGenCurrent()) {
                                setRequiresApiKey(true);
                                setIsGenerating(false);
                                return;
                            }
                        }
                    }

                    const generatedVideo = await generateVideosFromPrompt(currentPrompt, safeGenStatusUpdate);
                    if (isGenCurrent()) setVideo(generatedVideo);
                }
            } catch (error: any) {
                if (isGenCurrent()) {
                    console.error(`${requestMode} generation failed:`, error);
                    const message = error?.error?.message || error.message || `An unknown error occurred during ${requestMode} generation.`;
                    setGalleryErrors(prev => ({ ...prev, [requestMode]: message }));
                }
            } finally {
                if (isGenCurrent()) {
                    setIsGenerating(false);
                    setStatusNotification(null);
                }
            }
        })();
    }

    await Promise.all([analysisPromise, generationPromise]).finally(() => {
        if (isGenCurrent() && !isGenerating) setStatusNotification(null);
    });

  }, [refreshAnalysis, handleStatusUpdate]);

  const handlePromptSubmit = useCallback(() => {
    setHasGenerated(true);

    // Check if prompt is identical to what we last analyzed.
    // If so, we can skip regenerating the graph and clarifications.
    const shouldSkipAnalysis = prompt === lastAnalyzedPrompt && mode === lastAnalyzedMode;

    if (shouldSkipAnalysis) {
        // Reuse existing analysis state, preserve answered questions
        processRequest(prompt, answeredQuestions, mode, true, false);
    } else {
        // Full reset
        const newAnsweredQuestions: string[] = [];
        setAnsweredQuestions(newAnsweredQuestions);
        setClarifications([]); 
        processRequest(prompt, newAnsweredQuestions, mode, false, false);
    }
  }, [prompt, mode, lastAnalyzedPrompt, lastAnalyzedMode, answeredQuestions, processRequest]);

  const handleAnalyzeOnly = useCallback(() => {
     // Force a fresh analysis but skip generation
     const newAnsweredQuestions: string[] = [];
     setAnsweredQuestions(newAnsweredQuestions);
     setClarifications([]);
     processRequest(prompt, newAnsweredQuestions, mode, false, true); // skipGeneration = true
  }, [prompt, mode, processRequest]);

  const handleSelectApiKey = async () => {
      const win = window as any;
      if (win.aistudio && win.aistudio.openSelectKey) {
          await win.aistudio.openSelectKey();
          // After selecting, try generating again if we are still in the same context
          if (requiresApiKey) {
             setRequiresApiKey(false);
             // Re-trigger the generation part only? Or just let user click generate again.
             // Best UX: let them click generate again to avoid race conditions or auto-starting unexpectedly.
          }
      }
  };

  const handleApplyAllUpdates = async () => {
    if (isUpdatingPrompt) return;
    
    const requestMode = mode;
    // Note: We don't use analysisRequestId here for the refinement step itself, 
    // but we check mode to ensure we haven't switched context.
    const isCurrent = () => modeRef.current === requestMode;
    const safeStatusUpdate = (msg: string) => { if (isCurrent()) handleStatusUpdate(msg); };

    setIsUpdatingPrompt(true);
    setStatusNotification(null);

    const qaPairs: {question: string, answer: string}[] = Object.entries(pendingClarificationAnswers).map(([q, a]) => ({question: q, answer: a as string}));
    
    const graphUpdates: GraphUpdate[] = [];
    Object.entries(pendingAttributeUpdates).forEach(([key, value]) => {
        const [entity, attribute] = key.split(':');
        graphUpdates.push({ type: 'attribute', entity, attribute, value: value as string });
    });
    Object.entries(pendingRelationshipUpdates).forEach(([key, value]) => {
        const [source, target] = key.split(':');
        const originalRel = beliefGraph?.relationships.find(r => r.source === source && r.target === target);
        if (originalRel) {
            graphUpdates.push({ type: 'relationship', source, target, oldLabel: originalRel.label, newLabel: value as string });
        }
    });

    const newAnsweredQuestions = [...answeredQuestions, ...qaPairs.map(a => a.question)];
    setAnsweredQuestions(newAnsweredQuestions);

    try {
        // Use current prompt state to ensure we incorporate user manual edits
        const newRefinedPrompt = await refinePromptWithAllUpdates(prompt, qaPairs, graphUpdates, safeStatusUpdate);
        
        if (!isCurrent()) return;

        setPrompt(newRefinedPrompt);
        setIsOutdated(true); 
        
        clearPendingUpdates(); 
        setSkippedQuestions([]); 

        // This will update the graph/clarifications and setLastAnalyzedPrompt
        // It generates a new analysisRequestId internally, invalidating any previous racing analysis requests.
        refreshAnalysis(newRefinedPrompt, newAnsweredQuestions, requestMode);
        
    } catch(error) {
        console.error("Failed to handle updates:", error);
        if (isCurrent()) setGalleryErrors(prev => ({ ...prev, [requestMode]: "Failed to refine prompt based on your changes." }));
    } finally {
        if (isCurrent()) {
            setIsUpdatingPrompt(false);
            setStatusNotification(null);
        }
    }
  };
  
  const ToolTabButton = ({ label, tab, current }: { label: string, tab: ToolTab, current: ToolTab }) => (
      <button 
        onClick={() => setActiveToolTab(tab)}
        className={`flex-1 py-3 text-xs sm:text-sm font-semibold text-center transition-colors relative focus:outline-none ${current === tab ? 'text-blue-600 dark:text-blue-400 bg-white dark:bg-gray-800 border-b-2 border-blue-600 dark:border-blue-400' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 border-b border-gray-200 dark:border-gray-700'}`}
      >
        {label}
      </button>
  );

  const pendingClarificationCount = Object.keys(pendingClarificationAnswers).length;
  const pendingGraphUpdatesCount = Object.keys(pendingAttributeUpdates).length + Object.keys(pendingRelationshipUpdates).length;
  const totalUpdateCount = pendingClarificationCount + pendingGraphUpdatesCount;

  return (
    <div className={`${isDarkMode ? 'dark' : ''} font-sans h-screen flex flex-col bg-gray-100 dark:bg-gray-900 text-gray-800 dark:text-gray-100 transition-colors duration-200 overflow-hidden`}>
        <Header 
            isDarkMode={isDarkMode} 
            toggleDarkMode={() => setIsDarkMode(!isDarkMode)} 
            onShowInfo={() => setShowInfoModal(true)}
        />

        {/* Retry/Status Notification */}
        {statusNotification && (
            <div className="fixed top-20 left-1/2 transform -translate-x-1/2 z-[2000] animate-fade-in-down px-4 w-full max-w-md">
                <div className="bg-amber-100 dark:bg-amber-900/90 border border-amber-300 dark:border-amber-700 text-amber-900 dark:text-amber-100 px-4 py-3 rounded-lg shadow-lg flex items-center gap-3 backdrop-blur-sm">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 animate-pulse text-amber-600 dark:text-amber-400 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                    <span className="text-sm font-medium flex-1">{statusNotification}</span>
                    <button 
                        onClick={() => setStatusNotification(null)} 
                        className="ml-auto text-amber-600 dark:text-amber-300 hover:text-amber-800 dark:hover:text-white flex-shrink-0 p-1 hover:bg-amber-200 dark:hover:bg-amber-800 rounded-full transition-colors flex items-center justify-center"
                        aria-label="Close notification"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                           <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                        </svg>
                    </button>
                </div>
            </div>
        )}

        {/* Removed pb-14 from main on mobile to allow background to extend fully. Added pb to inner containers. */}
        <main className="flex-1 flex flex-col w-full max-w-screen-2xl mx-auto xl:p-6 xl:pt-4 xl:pb-6 overflow-hidden min-h-0">
            <div className="flex-1 flex flex-col xl:grid xl:grid-cols-2 xl:gap-6 min-h-0">
            
            {/* Left Column (Editor) */}
            <div className={`flex flex-col gap-0 bg-white dark:bg-gray-800 xl:rounded-lg xl:border border-gray-200 dark:border-gray-700 shadow-sm transition-colors duration-200 ${mobileView === 'editor' ? 'flex flex-1' : 'hidden xl:flex'} h-full overflow-y-auto`}>
                
                {/* 1. Prompt Input Area */}
                <div className="flex-shrink-0 z-10 border-b border-gray-200 dark:border-gray-700">
                    <PromptInput
                        prompt={prompt}
                        setPrompt={setPrompt}
                        onSubmit={handlePromptSubmit}
                        onAnalyze={handleAnalyzeOnly}
                        isLoading={isGenerating}
                        isGenerating={isGenerating}
                        isFirstRun={!hasGenerated}
                        mode={mode}
                        setMode={handleModeChange}
                    />
                </div>

                {/* 2. Tool Tabs */}
                <div className="flex flex-shrink-0 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 justify-between items-center pr-2">
                    <div className="flex flex-1">
                        <ToolTabButton label="Clarifications" tab="clarify" current={activeToolTab} />
                        <ToolTabButton label="Belief Graph" tab="graph" current={activeToolTab} />
                        <ToolTabButton 
                            label={mode === 'image' ? 'Image Attributes' : (mode === 'video' ? 'Video Attributes' : 'Story Attributes')} 
                            tab="attributes" 
                            current={activeToolTab} 
                        />
                    </div>
                </div>

                {/* 3. Tool Content - Added pb-14 for mobile footer spacing */}
                <div className="relative bg-gray-50/30 dark:bg-gray-900/30 flex-1 overflow-hidden flex flex-col min-h-[450px] pb-[3.5rem] xl:pb-0">

                    {totalUpdateCount > 0 && (
                        <div className="flex-shrink-0 bg-blue-50 dark:bg-blue-900/20 border-b border-blue-100 dark:border-blue-800 p-3 flex justify-between items-center animate-fade-in z-20">
                            <div className="text-xs text-blue-800 dark:text-blue-200 font-medium flex items-center gap-2">
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                <span>{totalUpdateCount} pending change{totalUpdateCount !== 1 ? 's' : ''}</span>
                            </div>
                            <button 
                                onClick={handleApplyAllUpdates}
                                disabled={isUpdatingPrompt}
                                className={`bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold py-1.5 px-4 rounded-md shadow-sm flex items-center gap-2 transition-all ${isUpdatingPrompt ? 'opacity-70 cursor-wait' : 'hover:shadow-md'}`}
                                title={isUpdatingPrompt ? "Updating prompt..." : "Apply all changes from Clarifications and Belief Graph"}
                            >
                                {isUpdatingPrompt ? (
                                    <>
                                    <svg className="animate-spin h-3 w-3 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    <span>Updating...</span>
                                    </>
                                ) : (
                                    <span>Update Prompt</span>
                                )}
                            </button>
                        </div>
                    )}

                    {/* Clarifications - Updated to use flex/overflow-hidden for internal scrolling */}
                    <div className={`p-4 ${activeToolTab === 'clarify' ? 'flex flex-col' : 'hidden'} h-full overflow-hidden`}>
                        <ClarificationCard
                            clarifications={clarifications}
                            onRefresh={handleRefreshClarifications}
                            isLoading={isClarificationsLoading} 
                            pendingAnswers={pendingClarificationAnswers}
                            setPendingAnswers={setPendingClarificationAnswers}
                            prompt={prompt}
                        />
                    </div>

                    {/* Belief Graph / Attributes - Graph now fills the flex container */}
                    <div className={`flex-1 w-full min-h-0 ${activeToolTab !== 'clarify' ? 'flex flex-col' : 'hidden'}`}>
                        <BeliefGraph 
                            data={beliefGraph} 
                            isLoading={isGraphLoading} 
                            mode={mode} // Remove the ternary check
                            view={activeToolTab === 'attributes' ? 'attributes' : 'graph'}
                            isVisible={activeToolTab !== 'clarify'}
                            pendingAttributeUpdates={pendingAttributeUpdates}
                            setPendingAttributeUpdates={setPendingAttributeUpdates}
                            pendingRelationshipUpdates={pendingRelationshipUpdates}
                            setPendingRelationshipUpdates={setPendingRelationshipUpdates}
                            pendingClarificationCount={pendingClarificationCount}
                            currentPrompt={prompt}
                        />
                    </div>
                </div>
            </div>
            
            {/* Right Column (Preview) - Added pb-14 for mobile footer spacing */}
            <div className={`flex flex-col xl:flex ${mobileView === 'preview' ? 'flex' : 'hidden mt-4 xl:mt-0'} flex-1 h-full min-h-0 pb-[3.5rem] xl:pb-0`}>
                <OutputDisplay
                    images={images}
                    story={story}
                    video={video}
                    mode={mode}
                    isLoading={isGenerating}
                    error={galleryErrors[mode]}
                    isOutdated={isOutdated}
                    requiresApiKey={requiresApiKey}
                    onSelectKey={handleSelectApiKey}
                />
            </div>

            </div>
        </main>

        {/* Mobile Bottom Navigation - Fixed */}
        <div 
            className="xl:hidden bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 flex justify-around p-2 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)] z-[200] fixed bottom-0 left-0 right-0"
            style={{ paddingBottom: 'max(0.5rem, env(safe-area-inset-bottom))' }}
        >
            <button 
                onClick={() => setMobileView('editor')}
                className={`flex-1 flex flex-col items-center justify-center py-1 rounded-lg transition-colors ${mobileView === 'editor' ? 'text-blue-600 dark:text-blue-400' : 'text-gray-500 dark:text-gray-400'}`}
            >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mb-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
                <span className="text-[10px] font-bold uppercase tracking-wide">Editor</span>
            </button>
            
            <button 
                onClick={() => setMobileView('preview')}
                className={`flex-1 flex flex-col items-center justify-center py-1 rounded-lg transition-colors ${mobileView === 'preview' ? 'text-blue-600 dark:text-blue-400' : 'text-gray-500 dark:text-gray-400'}`}
            >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mb-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <span className="text-[10px] font-bold uppercase tracking-wide">Preview</span>
            </button>
        </div>

        {/* Info Modal */}
        {showInfoModal && (
          <div 
            className="fixed inset-0 z-[3000] bg-black/50 flex items-center justify-center p-4 backdrop-blur-sm animate-fade-in" 
            onClick={() => setShowInfoModal(false)}
          >
            <div 
              className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-lg w-full p-6 relative border border-gray-200 dark:border-gray-700" 
              onClick={e => e.stopPropagation()}
            >
              <button 
                onClick={() => setShowInfoModal(false)} 
                className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                aria-label="Close"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
              
              <div className="text-center mb-6">
                 <h2 className="text-2xl font-bold text-gray-800 dark:text-gray-100 mb-2">Proactive Co-Creator</h2>
                 <p className="text-gray-600 dark:text-gray-400">Thanks for using our app!</p>
              </div>
              
              <div className="grid gap-4">
                  <a 
                    href="https://zi-wang.com/co-creator-feedback" 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className="flex items-center justify-between p-4 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800 hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-all group"
                  >
                      <div className="flex items-center gap-3">
                          <div className="bg-blue-100 dark:bg-blue-800 p-2 rounded-full text-blue-600 dark:text-blue-200">
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                              </svg>
                          </div>
                          <div className="text-left">
                              <h3 className="font-semibold text-gray-900 dark:text-gray-100">Give Feedback</h3>
                              <p className="text-sm text-gray-500 dark:text-gray-400">Help us improve the experience</p>
                          </div>
                      </div>
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-gray-400 group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                  </a>

                  <a 
                    href="https://zi-wang.com/human-ai" 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className="flex items-center justify-between p-4 rounded-lg bg-purple-50 dark:bg-purple-900/20 border border-purple-100 dark:border-purple-800 hover:bg-purple-100 dark:hover:bg-purple-900/40 transition-all group"
                  >
                      <div className="flex items-center gap-3">
                          <div className="bg-purple-100 dark:bg-purple-800 p-2 rounded-full text-purple-600 dark:text-purple-200">
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                              </svg>
                          </div>
                          <div className="text-left">
                              <h3 className="font-semibold text-gray-900 dark:text-gray-100">Our Research</h3>
                              <p className="text-sm text-gray-500 dark:text-gray-400">Learn about the human-AI alignment</p>
                          </div>
                      </div>
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-gray-400 group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                  </a>
              </div>
            </div>
          </div>
        )}

        {/* Mode Change Popup */}
        {showModeChangePopup && (
            <div className="fixed bottom-4 right-4 z-[2000] animate-fade-in-up max-w-sm w-full mx-auto px-4 sm:px-0">
                <div className="bg-white dark:bg-gray-800 border-l-4 border-amber-400 rounded-r shadow-2xl p-4 relative flex flex-col gap-1 border border-gray-200 dark:border-gray-700">
                     <button 
                        onClick={() => setShowModeChangePopup(false)}
                        className="absolute top-2 right-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
                        aria-label="Close"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                        </svg>
                    </button>
                    <div className="flex items-start">
                        <div className="flex-shrink-0 pt-0.5">
                             <svg className="h-5 w-5 text-amber-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                            </svg>
                        </div>
                        <div className="ml-3 pr-6">
                            <h3 className="text-sm font-bold text-gray-900 dark:text-gray-100">Mode Changed</h3>
                            <p className="mt-1 text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
                                The belief graph and clarifications are from the previous mode. They are preserved for reference but may be outdated.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        )}
    </div>
  );
}

export default App;
