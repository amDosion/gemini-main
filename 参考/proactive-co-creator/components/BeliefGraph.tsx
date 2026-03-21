/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
*/

import React, { useState, useMemo, useEffect, useRef, useCallback, useLayoutEffect } from 'react';
import { BeliefState, Entity, Attribute, Relationship, Candidate, GraphUpdate } from '../types';

interface BeliefGraphProps {
  data: BeliefState | null;
  isLoading: boolean;
  mode: 'image' | 'story' | 'video';
  view: 'graph' | 'attributes';
  isVisible?: boolean;
  pendingAttributeUpdates: Record<string, string>;
  setPendingAttributeUpdates: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  pendingRelationshipUpdates: Record<string, string>;
  setPendingRelationshipUpdates: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  pendingClarificationCount: number;
  currentPrompt: string;
}

const getHighestProbabilityValue = (attribute: Attribute): string => {
    if (!attribute.value || attribute.value.length === 0) return 'Unknown';
    // With strict schema output, the first item is generally the model's top choice
    return attribute.value[0].name;
};

// --- Thinking Process Component ---
const ThinkingProcess = ({ prompt }: { prompt: string }) => {
    const [step, setStep] = useState(0);

    const steps = useMemo(() => {
        const cleanPrompt = prompt.toLowerCase().replace(/[^\w\s]/g, '');
        const words = cleanPrompt.split(/\s+/).filter(w => w.length > 0);
        
        // Context detection
        const hasHuman = words.some(w => ['man', 'woman', 'boy', 'girl', 'person', 'people', 'child', 'kid', 'guy', 'lady', 'friends', 'family', 'couple'].includes(w));
        const hasAction = words.some(w => w.endsWith('ing')); 
        
        // Find a significant noun-like word (longer than 3 chars, not common stop words)
        const stopWords = ['about', 'after', 'before', 'their', 'where', 'which', 'there', 'could', 'would', 'with', 'from', 'that', 'this', 'some', 'what'];
        const significantWord = words.find(w => w.length > 3 && !stopWords.includes(w)) || 'entities';
        const truncatedKeyword = significantWord.length > 10 ? significantWord.substring(0, 9) + '...' : significantWord;

        const generatedSteps = [
            "Parsing prompt syntax...",
            `Identifying key concepts like '${truncatedKeyword}'...`,
        ];

        if (hasHuman) {
            generatedSteps.push("Analyzing poses and expressions...");
        } else {
            generatedSteps.push("Analyzing object attributes...");
        }

        generatedSteps.push("Deducing implicit surroundings...");
        
        if (hasAction) {
            generatedSteps.push("Mapping interaction dynamics...");
        }

        return generatedSteps;
    }, [prompt]);

    useEffect(() => {
        const interval = setInterval(() => {
            setStep((s) => (s + 1) % steps.length);
        }, 2200); // 2.2 seconds per step
        return () => clearInterval(interval);
    }, [steps]);

    return (
        <span className="text-sm font-medium text-gray-600 dark:text-gray-300 animate-pulse min-w-[240px] text-center transition-all duration-300">
            {steps[step]}
        </span>
    );
};

// --- Styles Placeholder Component ---
const EmptyStatePlaceholder = ({ text }: { text: string }) => (
    <div className="bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700 rounded-lg flex flex-col items-center justify-center text-center text-gray-400 dark:text-gray-500 p-8 max-w-lg w-full shadow-sm mx-auto my-auto">
        <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 mb-3 text-gray-300 dark:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
        </svg>
        <p className="text-sm font-medium">{text}</p>
    </div>
);

interface AttributeEditorProps {
    attribute: Attribute;
    entity: Entity;
    onChange: (entityName: string, attributeName: string, newValue: string) => void;
    isLoading: boolean;
    pendingValue?: string;
}

const AttributeEditor: React.FC<AttributeEditorProps> = ({ attribute, entity, onChange, isLoading, pendingValue }) => {
    const [isCustomMode, setIsCustomMode] = useState(false);
    const [customValue, setCustomValue] = useState("");
    
    // Check if this is an existence attribute (supports legacy 'existence_in_image' and new 'existence')
    const isExistence = attribute.name === 'existence' || attribute.name === 'existence_in_image';

    // Determine the value to show
    let currentValue = pendingValue;
    
    if (currentValue === undefined) {
        if (isExistence) {
             // For existence, we look at the candidates. Usually [ {name: 'true', ...}, {name: 'false', ...} ]
             currentValue = getHighestProbabilityValue(attribute);
             if (currentValue === 'Unknown') currentValue = 'true'; // Default to true if missing for existence
        } else {
             // For standard attributes:
             // If explicitly in prompt, show the inferred value.
             // If not in prompt, show 'Unknown' to allow user to explicitly select the inferred value later.
             currentValue = attribute.presence_in_prompt ? getHighestProbabilityValue(attribute) : 'Unknown';
        }
    }

    const isModified = pendingValue !== undefined;

    // Reset custom mode when attribute changes (e.g. after a refresh)
    useEffect(() => {
        setIsCustomMode(false);
        setCustomValue("");
    }, [attribute]);

    // --- Existence Toggle (Available for all entities) ---
    if (isExistence) {
        const isPresent = currentValue === 'true';
        
        return (
            <div key={attribute.name} className="grid grid-cols-[100px_1fr] sm:grid-cols-[120px_1fr] gap-4 items-center py-3 border-b border-gray-100 dark:border-gray-700 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors px-2 rounded-lg">
                <label className="text-gray-600 dark:text-gray-400 font-medium text-xs sm:text-sm">Existence</label>
                <div className={`flex rounded-md border overflow-hidden w-full ${isModified ? 'border-blue-500 ring-1 ring-blue-200 dark:ring-blue-900' : 'border-gray-300 dark:border-gray-600'}`}>
                     <button
                        onClick={() => onChange(entity.name, attribute.name, 'true')}
                        disabled={isLoading}
                        title={isLoading ? "Loading..." : "Set existence to Present"}
                        className={`w-1/2 text-xs font-semibold py-1.5 px-2 transition-colors truncate disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-500 ${
                            isPresent
                                ? 'bg-green-600 text-white'
                                : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                        }`}
                    >
                        Present
                    </button>
                    <button
                        onClick={() => onChange(entity.name, attribute.name, 'false')}
                        disabled={isLoading}
                        title={isLoading ? "Loading..." : "Set existence to Absent"}
                        className={`w-1/2 text-xs font-semibold py-1.5 px-2 transition-colors truncate disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-500 ${
                            !isPresent
                                ? 'bg-red-600 text-white'
                                : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                        }`}
                    >
                        Absent
                    </button>
                </div>
            </div>
        );
    }

    // --- Standard Attribute Editor ---
    return (
        <div key={attribute.name} className="grid grid-cols-[100px_1fr] sm:grid-cols-[120px_1fr] gap-4 items-center py-3 border-b border-gray-100 dark:border-gray-700 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors px-2 rounded-lg">
            <label className="text-gray-600 dark:text-gray-400 font-medium text-xs sm:text-sm flex items-center gap-1.5 capitalize leading-tight">
                {attribute.name.replace(/_/g, ' ')}
                {isModified && <span className="h-2 w-2 rounded-full bg-blue-500 shadow-sm ring-1 ring-blue-200 dark:ring-blue-900 flex-shrink-0" title="Modified"></span>}
            </label>
            <div className="w-full">
                {isCustomMode ? (
                    <div className="flex gap-1">
                        <input
                            type="text"
                            autoFocus
                            value={customValue}
                            onChange={(e) => setCustomValue(e.target.value)}
                            placeholder="Type value..."
                            className="w-full bg-white dark:bg-gray-700 border border-blue-500 text-gray-800 dark:text-gray-200 text-sm rounded px-2 py-1.5 focus:outline-none shadow-sm"
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && customValue.trim()) {
                                    onChange(entity.name, attribute.name, customValue.trim());
                                    setIsCustomMode(false);
                                } else if (e.key === 'Escape') {
                                    setIsCustomMode(false);
                                }
                            }}
                            disabled={isLoading}
                        />
                        <button
                            onClick={() => {
                                if (customValue.trim()) {
                                    onChange(entity.name, attribute.name, customValue.trim());
                                    setIsCustomMode(false);
                                }
                            }}
                            disabled={isLoading || !customValue.trim()}
                            className="bg-blue-600 text-white hover:bg-blue-700 text-xs font-semibold px-2 rounded disabled:bg-gray-300"
                        >
                            Save
                        </button>
                        <button
                            onClick={() => setIsCustomMode(false)}
                            className="text-gray-400 hover:text-gray-600 px-1"
                            title="Cancel"
                            disabled={isLoading}
                        >
                            &times;
                        </button>
                    </div>
                ) : (
                    <div className="relative">
                        <select 
                            value={currentValue} 
                            onChange={(e) => {
                                if (e.target.value === '__custom__') {
                                    setIsCustomMode(true);
                                } else {
                                    onChange(entity.name, attribute.name, e.target.value);
                                }
                            }} 
                            disabled={isLoading} 
                            className={`w-full text-gray-800 dark:text-gray-200 text-sm rounded-md shadow-sm px-3 py-2 pr-8 appearance-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent cursor-pointer transition-colors ${
                                isModified 
                                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 border' 
                                : 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 border hover:border-gray-400 dark:hover:border-gray-500'
                            }`}
                        >
                            <option value="Unknown" disabled={currentValue !== 'Unknown'}>Unknown</option>
                            {attribute.value.map(v => (
                                <option key={v.name} value={v.name}>{v.name}</option>
                            ))}
                            {isModified && currentValue !== 'Unknown' && !attribute.value.some(v => v.name === currentValue) && (
                                <option value={currentValue}>{currentValue}</option>
                            )}
                            <option value="__custom__" className="font-bold text-blue-600 dark:text-blue-400 bg-gray-50 dark:bg-gray-800">
                                + Type custom...
                            </option>
                        </select>
                        <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-gray-500 dark:text-gray-400">
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                            </svg>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

const RelationshipEditor: React.FC<{
  rel: Relationship;
  position: { x: number; y: number };
  containerDimensions: { width: number; height: number };
  onChange: (newLabel: string) => void;
  onClose: () => void;
  isLoading: boolean;
}> = ({ rel, position, containerDimensions, onChange, onClose, isLoading }) => {
  const editorRef = useRef<HTMLDivElement>(null);
  const [customLabel, setCustomLabel] = useState("");
  const [adjustedStyle, setAdjustedStyle] = useState<React.CSSProperties>({
      left: position.x,
      top: position.y,
      opacity: 0, 
      transform: 'translate(-50%, 8px)'
  });

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (editorRef.current && !editorRef.current.contains(event.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  useLayoutEffect(() => {
      if (editorRef.current && containerDimensions.width > 0) {
          const { width, height } = editorRef.current.getBoundingClientRect();
          const padding = 20; 
          
          let top = position.y + 12;
          let left = position.x;
          let transformX = '-50%';

          // Vertical check: if bottom overflows
          if (top + height > containerDimensions.height - padding) {
              top = position.y - height - 12; // Flip to above
              if (top < padding) top = padding; // Clamp top
          }

          // Horizontal check
          const halfWidth = width / 2;
          
          if (left + halfWidth > containerDimensions.width - padding) {
               // Overflow Right -> Anchor to the left of the click
               left = position.x - 12;
               transformX = '-100%';
          } else if (left - halfWidth < padding) {
               // Overflow Left -> Anchor to the right of the click
               left = position.x + 12;
               transformX = '0%';
          }

          setAdjustedStyle({
              left,
              top,
              transform: `translate(${transformX}, 0)`,
              opacity: 1,
              transition: 'opacity 0.2s ease-out',
              touchAction: 'pan-y'
          });
      }
  }, [position, containerDimensions, rel.label]);

  const allOptions: Candidate[] = [
    { name: rel.label },
    ...(rel.alternatives || [])
  ].filter((v, i, a) => a.findIndex(t => t.name === v.name) === i);

  const handleCustomSubmit = () => {
    if (customLabel.trim()) {
        onChange(customLabel.trim());
        onClose();
    }
  };

  return (
    <div
      ref={editorRef}
      className="absolute bg-white/95 dark:bg-gray-800/95 backdrop-blur-sm p-3 rounded-lg border border-gray-300 dark:border-gray-600 shadow-xl z-40 w-64 max-h-[300px] overflow-y-auto flex flex-col"
      style={adjustedStyle}
      onPointerDown={(e) => e.stopPropagation()}
      onWheel={(e) => e.stopPropagation()}
    >
      <div className="flex justify-between items-center mb-2 flex-shrink-0">
          <h4 className="font-bold text-sm text-gray-800 dark:text-gray-100">Edit Relationship</h4>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xl leading-none">&times;</button>
      </div>
      <div className="flex flex-col space-y-1 mb-3 flex-grow">
        {allOptions.map(alt => (
            <button
                key={alt.name}
                disabled={isLoading}
                onClick={() => { onChange(alt.name); onClose(); }}
                className={`text-left text-sm p-1 px-2 rounded transition-colors w-full ${rel.label === alt.name ? 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-100 font-semibold' : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'} disabled:opacity-50`}
            >
                {alt.name}
            </button>
        ))}
      </div>
      <div className="pt-2 border-t border-gray-200 dark:border-gray-700 flex-shrink-0">
          <div className="flex gap-2">
              <input 
                  type="text"
                  value={customLabel}
                  onChange={(e) => setCustomLabel(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleCustomSubmit()}
                  placeholder="Type custom label..."
                  className="flex-grow text-xs border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded p-1.5 focus:outline-none focus:border-blue-500"
                  disabled={isLoading}
              />
              <button 
                  onClick={handleCustomSubmit}
                  disabled={isLoading || !customLabel.trim()}
                  className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold px-2 rounded disabled:bg-gray-300"
              >
                  Save
              </button>
          </div>
      </div>
    </div>
  );
};

const getIntersection = (x1: number, y1: number, x2: number, y2: number, w: number, h: number, gap: number = 0) => {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const dist = Math.sqrt(dx*dx + dy*dy);
    if (dist === 0) return { x: x1, y: y1 };

    const halfW = w / 2;
    const halfH = h / 2;

    const tanTheta = Math.abs(dy / dx);
    const tanCorner = halfH / halfW;
    
    let ix, iy;
    
    if (tanTheta < tanCorner) {
        const sign = Math.sign(dx);
        ix = x1 + (halfW + gap) * sign;
        iy = y1 + (halfW + gap) * sign * (dy / dx);
    } else {
        const sign = Math.sign(dy);
        iy = y1 + (halfH + gap) * sign;
        ix = x1 + (halfH + gap) * sign * (dx / dy);
    }
    return { x: ix, y: iy };
}

const getEdgePath = (
    x1: number, y1: number, 
    x2: number, y2: number, 
    sourceW: number, sourceH: number,
    targetW: number, targetH: number
) => {
    const start = getIntersection(x1, y1, x2, y2, sourceW, sourceH, 0); 
    const end = getIntersection(x2, y2, x1, y1, targetW, targetH, 5); // 5px gap for arrowhead

    const path = `M ${start.x} ${start.y} L ${end.x} ${end.y}`;
    const labelX = (start.x + end.x) / 2;
    const labelY = (start.y + end.y) / 2;

    return { path, labelX, labelY };
};

const truncate = (str: string, maxLength: number) => {
    if (str.length <= maxLength) return str;
    return str.substring(0, maxLength) + '...';
};

const BeliefGraph: React.FC<BeliefGraphProps> = ({ 
    data, 
    isLoading, 
    mode, 
    view, 
    isVisible = true,
    pendingAttributeUpdates,
    setPendingAttributeUpdates,
    pendingRelationshipUpdates,
    setPendingRelationshipUpdates,
    pendingClarificationCount,
    currentPrompt
}) => {
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [hoveredEntity, setHoveredEntity] = useState<string | null>(null);
  const [hoveredRel, setHoveredRel] = useState<Relationship | null>(null);
  const [selectedRel, setSelectedRel] = useState<{rel: Relationship, position: {x: number, y: number}} | null>(null);
  const [nodePositions, setNodePositions] = useState<{[key: string]: {x: number, y: number}}>({});
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  
  const stablePositions = useRef<{[key: string]: {x: number, y: number}}>({});
  
  // Pan and Zoom State
  const [viewTransform, setViewTransform] = useState({ x: 0, y: 0, k: 1 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef<{ x: number, y: number } | null>(null);
  const activePointersRef = useRef<Map<number, {x: number, y: number}>>(new Map());
  const prevPinchDistRef = useRef<number | null>(null);

  const measureRef = useCallback((node: HTMLDivElement | null) => {
    if (node !== null) {
      const resizeObserver = new ResizeObserver((entries) => {
          for (let entry of entries) {
              const { width, height } = entry.contentRect;
              if (width > 0 && height > 0) {
                   setDimensions(prev => {
                       if (Math.abs(prev.width - width) > 2 || Math.abs(prev.height - height) > 2) {
                           return { width, height };
                       }
                       return prev;
                   });
              }
          }
      });
      resizeObserver.observe(node);
      const rect = node.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
          setDimensions({ width: rect.width, height: rect.height });
      }
      return () => resizeObserver.disconnect();
    }
  }, []);

  useEffect(() => {
      setSelectedEntity(null);
      setSelectedRel(null);
      setViewTransform({ x: 0, y: 0, k: 1 });
  }, [data]);

  const handleAttributeChange = (entityName: string, attributeName: string, newValue: string) => {
      const key = `${entityName}:${attributeName}`;
      setPendingAttributeUpdates(prev => ({ ...prev, [key]: newValue }));
  };

  const handleRelationshipChange = (source: string, target: string, newLabel: string) => {
      const key = `${source}:${target}`;
      setPendingRelationshipUpdates(prev => ({ ...prev, [key]: newLabel }));
  };

  const sceneEntityNames = ['image', 'the image', 'story', 'the story', 'video', 'the video'];
  const sceneEntity = useMemo(() => data?.entities.find(e => sceneEntityNames.includes(e.name.toLowerCase())), [data]);
  const objectEntities = useMemo(() => data?.entities.filter(e => !sceneEntityNames.includes(e.name.toLowerCase())) || [], [data]);
  const nodeDimensions = useMemo(() => {
    const dimensions: {[key: string]: {width: number, height: number}} = {};
    if (data) {
        objectEntities.forEach(entity => {
          const textWidth = entity.name.length * 8 + 20; 
          dimensions[entity.name] = { width: Math.max(50, textWidth), height: 36 }; 
        });
    }
    return dimensions;
  }, [objectEntities, data]);

  const getCanonicalName = useCallback((name: string) => {
    if (!name) return null;
    const lowerName = name.toLowerCase();
    const cleanName = lowerName.replace(/^(the|a|an)\s+/, '').trim();
    let match = objectEntities.find(e => e.name.toLowerCase() === lowerName);
    if (!match) match = objectEntities.find(e => e.name.toLowerCase().replace(/^(the|a|an)\s+/, '').trim() === cleanName);
    if (!match && cleanName.length > 2) {
         match = objectEntities.find(e => {
             const cleanEntity = e.name.toLowerCase().replace(/^(the|a|an)\s+/, '').trim();
             return cleanEntity.includes(cleanName);
         });
         if (!match) {
             match = objectEntities.find(e => {
                 const cleanEntity = e.name.toLowerCase().replace(/^(the|a|an)\s+/, '').trim();
                 return cleanName.includes(cleanEntity) && cleanEntity.length > 2;
             });
         }
    }
    return match ? match.name : null;
  }, [objectEntities]);

  const relationships = useMemo(() => {
    if (!data?.relationships) return [];
    const validRels = data.relationships.filter(r =>
        !sceneEntityNames.includes(r.source.toLowerCase()) &&
        !sceneEntityNames.includes(r.target.toLowerCase())
    );
    const uniqueRels: Relationship[] = [];
    const pairSet = new Set<string>();
    validRels.forEach(rel => {
        const canonicalSource = getCanonicalName(rel.source);
        const canonicalTarget = getCanonicalName(rel.target);
        if (!canonicalSource || !canonicalTarget) return;
        const normalizedRel = { ...rel, source: canonicalSource, target: canonicalTarget };
        const [k1, k2] = [canonicalSource, canonicalTarget].sort();
        const pairKey = `${k1}:${k2}`;
        if (!pairSet.has(pairKey)) {
            pairSet.add(pairKey);
            uniqueRels.push(normalizedRel);
        }
    });
    return uniqueRels;
  }, [data, getCanonicalName]);

  const neighborsOfSelected = useMemo(() => {
    if (!selectedEntity) return null;
    const neighbors = new Set<string>();
    relationships.forEach(rel => {
        if (rel.source === selectedEntity.name) neighbors.add(rel.target);
        if (rel.target === selectedEntity.name) neighbors.add(rel.source);
    });
    return neighbors;
  }, [selectedEntity, relationships]);

  const neighborsOfHovered = useMemo(() => {
    if (!hoveredEntity) return new Set();
    const neighbors = new Set<string>();
    relationships.forEach(rel => {
      if (rel.source === hoveredEntity) neighbors.add(rel.target);
      if (rel.target === hoveredEntity) neighbors.add(rel.source);
    });
    return neighbors;
  }, [hoveredEntity, relationships]);

  useEffect(() => {
    const containerWidth = dimensions.width || 600;
    const containerHeight = dimensions.height || 400;

    if (objectEntities.length > 0) {
        const SIMULATION_TICKS = 800; 
        const REPULSION_STRENGTH = 60000; 
        const LINK_STRENGTH = 0.2; 
        const CENTER_GRAVITY = 0.002; 
        const COLLISION_PADDING = 70; 
        const DAMPING = 0.8;

        const initRadius = Math.min(containerWidth, containerHeight) * 0.4;
        let nodes = objectEntities.map((entity, i) => {
            const prev = stablePositions.current[entity.name];
            if (prev && !isNaN(prev.x) && !isNaN(prev.y)) {
                return {
                    id: entity.name,
                    width: nodeDimensions[entity.name]?.width || 90, 
                    height: nodeDimensions[entity.name]?.height || 36, 
                    x: prev.x, y: prev.y, vx: 0, vy: 0, fx: 0, fy: 0,
                };
            }
            const angle = (i / objectEntities.length) * 2 * Math.PI;
            return {
                id: entity.name,
                width: nodeDimensions[entity.name]?.width || 90, 
                height: nodeDimensions[entity.name]?.height || 36, 
                x: containerWidth / 2 + initRadius * Math.cos(angle),
                y: containerHeight / 2 + initRadius * Math.sin(angle),
                vx: 0, vy: 0, fx: 0, fy: 0,
            };
        });

        const nodeMap = new Map(nodes.map(n => [n.id, n]));
        const links = relationships.map(rel => ({
            source: nodeMap.get(rel.source), 
            target: nodeMap.get(rel.target),
            label: rel.label
        })).filter(r => r.source && r.target);

        for (let tick = 0; tick < SIMULATION_TICKS; tick++) {
            nodes.forEach(node => { node.fx = 0; node.fy = 0; });
            for (let i = 0; i < nodes.length; i++) {
                for (let j = i + 1; j < nodes.length; j++) {
                    const nodeA = nodes[i], nodeB = nodes[j];
                    const dx = nodeB.x - nodeA.x, dy = nodeB.y - nodeA.y;
                    let distanceSq = dx * dx + dy * dy;
                    if (distanceSq === 0) distanceSq = 1;
                    const distance = Math.sqrt(distanceSq);
                    const force = REPULSION_STRENGTH / distanceSq;
                    nodeA.fx -= (dx / distance) * force; nodeA.fy -= (dy / distance) * force;
                    nodeB.fx += (dx / distance) * force; nodeB.fy += (dy / distance) * force;
                }
            }
            links.forEach(link => {
                const midX = (link.source.x + link.target.x) / 2;
                const midY = (link.source.y + link.target.y) / 2;
                const labelWidth = (link.label || "").length * 6 + 10; 
                nodes.forEach(node => {
                    if (node === link.source || node === link.target) return;
                    const dx = node.x - midX, dy = node.y - midY;
                    let dist = Math.sqrt(dx*dx + dy*dy);
                    if (dist === 0) dist = 1;
                    const threshold = (labelWidth / 2) + (Math.max(node.width, node.height) / 2) + 20;
                    if (dist < threshold) {
                        const forceStrength = (threshold - dist) * 1.5; 
                        node.fx += (dx / dist) * forceStrength; node.fy += (dy / dist) * forceStrength;
                    }
                });
            });
            for (let i = 0; i < links.length; i++) {
                for (let j = i + 1; j < links.length; j++) {
                     const l1 = links[i], l2 = links[j];
                     const m1x = (l1.source.x + l1.target.x) / 2, m1y = (l1.source.y + l1.target.y) / 2;
                     const m2x = (l2.source.x + l2.target.x) / 2, m2y = (l2.source.y + l2.target.y) / 2;
                     const dx = m1x - m2x, dy = m1y - m2y;
                     let dist = Math.sqrt(dx*dx + dy*dy);
                     if (dist === 0) dist = 0.1;
                     const minDist = ((l1.label?.length || 0)*9+50 + (l2.label?.length || 0)*9+50) / 2 + 30; 
                     if (dist < minDist) {
                         const force = (minDist - dist) * 1.0; 
                         l1.source.fx += (dx / dist) * force * 0.5; l1.source.fy += (dy / dist) * force * 0.5;
                         l1.target.fx += (dx / dist) * force * 0.5; l1.target.fy += (dy / dist) * force * 0.5;
                         l2.source.fx -= (dx / dist) * force * 0.5; l2.source.fy -= (dy / dist) * force * 0.5;
                         l2.target.fx -= (dx / dist) * force * 0.5; l2.target.fy -= (dy / dist) * force * 0.5;
                     }
                }
            }
            links.forEach(link => {
                const dx = link.target.x - link.source.x, dy = link.target.y - link.source.y;
                const distance = Math.sqrt(dx*dx + dy*dy);
                const sourceR = link.source.width / 2, targetR = link.target.width / 2;
                const idealVisibleLength = (link.label || "").length * 8 + 50; 
                const targetDist = sourceR + targetR + idealVisibleLength;
                if (distance > 0) {
                    const diff = distance - targetDist;
                    const force = LINK_STRENGTH * diff;
                    link.source.fx += (dx / distance) * force; link.source.fy += (dy / distance) * force;
                    link.target.fx -= (dx / distance) * force; link.target.fy -= (dy / distance) * force;
                }
            });
            nodes.forEach(node => {
                const dx = containerWidth / 2 - node.x, dy = containerHeight / 2 - node.y;
                node.fx += dx * CENTER_GRAVITY; node.fy += dy * CENTER_GRAVITY;
            });
            nodes.forEach(node => {
                node.vx = (node.vx + node.fx) * DAMPING; node.vy = (node.vy + node.fy) * DAMPING;
                node.x += node.vx; node.y += node.vy;
            });
            for(let k = 0; k < 3; k++) {
                for (let i = 0; i < nodes.length; i++) {
                    for (let j = i + 1; j < nodes.length; j++) {
                        const nodeA = nodes[i], nodeB = nodes[j];
                        const dx = nodeB.x - nodeA.x, dy = nodeB.y - nodeA.y;
                        const overlapX = (nodeA.width/2 + nodeB.width/2 + COLLISION_PADDING) - Math.abs(dx);
                        const overlapY = (nodeA.height/2 + nodeB.height/2 + COLLISION_PADDING) - Math.abs(dy);
                        if (overlapX > 0 && overlapY > 0) {
                            if (overlapX < overlapY) {
                                const sign = Math.sign(dx || (Math.random() - 0.5));
                                nodeA.x -= overlapX / 2 * sign; nodeB.x += overlapX / 2 * sign;
                            } else {
                                const sign = Math.sign(dy || (Math.random() - 0.5));
                                nodeA.y -= overlapY / 2 * sign; nodeB.y += overlapY / 2 * sign;
                            }
                        }
                    }
                }
            }
        }
        if (nodes.length > 0) {
            let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
            nodes.forEach(n => {
                minX = Math.min(minX, n.x); maxX = Math.max(maxX, n.x); minY = Math.min(minY, n.y); maxY = Math.max(maxY, n.y);
            });
            const offsetX = (containerWidth / 2) - (minX + maxX) / 2;
            const offsetY = (containerHeight / 2) - (minY + maxY) / 2;
            nodes.forEach(n => { n.x += offsetX; n.y += offsetY; });
        }
        const finalPositions = nodes.reduce((acc, node) => {
            acc[node.id] = { x: node.x, y: node.y }; return acc;
        }, {} as {[key: string]: {x: number, y: number}});
        stablePositions.current = finalPositions;
        setNodePositions(finalPositions);
    }
  }, [objectEntities, relationships, nodeDimensions, dimensions]);

  const handleRelationshipClick = (rel: Relationship, event: React.MouseEvent) => {
    if (selectedRel?.rel === rel) { setSelectedRel(null); } 
    else {
        const container = event.currentTarget.closest('div.relative');
        if (container) {
            const svgRect = container.getBoundingClientRect();
            setSelectedRel({ rel, position: { x: event.clientX - svgRect.left, y: event.clientY - svgRect.top } });
        }
    }
    setSelectedEntity(null);
  };
  const handlePointerDown = (e: React.PointerEvent) => {
    e.preventDefault(); activePointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (activePointersRef.current.size === 1) { setIsDragging(true); dragStartRef.current = { x: e.clientX, y: e.clientY }; }
    if (activePointersRef.current.size === 2) { prevPinchDistRef.current = null; }
    setSelectedRel(null);
  };
  const handlePointerMove = (e: React.PointerEvent) => {
    if (!activePointersRef.current.has(e.pointerId)) return;
    e.preventDefault(); activePointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const pointers: {x: number, y: number}[] = Array.from(activePointersRef.current.values());
    if (pointers.length === 2) {
        const dist = Math.sqrt(Math.pow(pointers[1].x - pointers[0].x, 2) + Math.pow(pointers[1].y - pointers[0].y, 2));
        if (prevPinchDistRef.current !== null) {
            const zoomFactor = dist / prevPinchDistRef.current;
            setViewTransform(prev => ({ ...prev, k: Math.min(4, Math.max(0.2, prev.k * zoomFactor)) }));
        }
        prevPinchDistRef.current = dist;
    } else if (pointers.length === 1 && isDragging && dragStartRef.current) {
        const dx = pointers[0].x - dragStartRef.current.x, dy = pointers[0].y - dragStartRef.current.y;
        setViewTransform(prev => ({ ...prev, x: prev.x + dx, y: prev.y + dy }));
        dragStartRef.current = { x: pointers[0].x, y: pointers[0].y };
    }
  };
  const handlePointerUp = (e: React.PointerEvent) => {
      activePointersRef.current.delete(e.pointerId);
      if (activePointersRef.current.size < 2) prevPinchDistRef.current = null;
      if (activePointersRef.current.size === 0) { setIsDragging(false); dragStartRef.current = null; }
      else if (activePointersRef.current.size === 1) {
          const p = activePointersRef.current.values().next().value as {x: number, y: number};
          dragStartRef.current = { x: p.x, y: p.y };
      }
  };
  const handleWheel = (e: React.WheelEvent) => {
      e.preventDefault(); const delta = -e.deltaY * 0.001;
      setViewTransform(prev => ({ ...prev, k: Math.min(4, Math.max(0.2, prev.k * Math.exp(delta))) }));
  };
  const zoomIn = () => setViewTransform(prev => ({ ...prev, k: Math.min(4, prev.k * 1.2) }));
  const zoomOut = () => setViewTransform(prev => ({ ...prev, k: Math.max(0.2, prev.k / 1.2) }));
  const resetView = () => setViewTransform({ x: 0, y: 0, k: 1 });

  const cardStyle = useMemo(() => {
    if (dimensions.width >= 768 && selectedEntity && nodePositions[selectedEntity.name]) {
        const pos = nodePositions[selectedEntity.name];
        const x = pos.x * viewTransform.k + viewTransform.x;
        const y = pos.y * viewTransform.k + viewTransform.y;
        
        const CARD_WIDTH = 384; 
        const PADDING = 20;
        const SAFE_MARGIN = 40; // Extra safety buffer to ensure we don't hit the container edge

        const dims = nodeDimensions[selectedEntity.name];
        const nodeHalfWidth = (dims?.width / 2 || 45) * viewTransform.k;
        
        const isLeftHalf = x < dimensions.width / 2;
        let left;
        if (isLeftHalf) {
            left = x + nodeHalfWidth + PADDING;
            if (left + CARD_WIDTH > dimensions.width - PADDING) {
                 const altLeft = x - nodeHalfWidth - PADDING - CARD_WIDTH;
                 if (altLeft > PADDING) left = altLeft;
            }
        } else {
            left = x - nodeHalfWidth - PADDING - CARD_WIDTH;
            if (left < PADDING) {
                const altLeft = x + nodeHalfWidth + PADDING;
                if (altLeft + CARD_WIDTH < dimensions.width - PADDING) left = altLeft;
            }
        }
        if (left < PADDING) left = PADDING;
        if (left + CARD_WIDTH > dimensions.width - PADDING) left = dimensions.width - CARD_WIDTH - PADDING;

        const isBottomHalf = y > dimensions.height / 2;
        let style: React.CSSProperties = { 
            position: 'absolute', 
            left: left, 
            right: 'auto', // Reset class right-4
            width: CARD_WIDTH, 
            display: 'flex', 
            flexDirection: 'column' 
        };
        
        if (isBottomHalf) {
            const bottomOffset = dimensions.height - y - 20; 
            const bottom = Math.max(PADDING, bottomOffset);
            style.bottom = bottom;
            style.top = 'auto'; // Reset potential class top
            // Cap height to available space above the anchor point minus safety margin
            const availableHeight = dimensions.height - bottom - SAFE_MARGIN;
            style.maxHeight = Math.max(100, availableHeight);
        } else {
            let top = y - 20; 
            if (top < PADDING) top = PADDING;
            style.top = top;
            style.bottom = 'auto'; // Reset potential class bottom
            // Cap height to available space below the anchor point minus safety margin
            const availableHeight = dimensions.height - top - SAFE_MARGIN;
            style.maxHeight = Math.max(100, availableHeight);
        }
        return style;
    }
    return undefined; 
  }, [selectedEntity, nodePositions, viewTransform, nodeDimensions, dimensions]);

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 w-full flex flex-col flex-1 min-h-0 relative transition-colors duration-200 shadow-sm">
      
      {isLoading && (
        <div className="absolute inset-0 bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm flex items-center justify-center z-50 rounded-lg transition-opacity duration-300">
            <div className="flex flex-col items-center p-8 bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-100 dark:border-gray-700 max-w-sm w-full mx-4">
                <div className="relative mb-4">
                     <svg className="animate-spin h-10 w-10 text-blue-500 dark:text-blue-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                </div>
                <ThinkingProcess prompt={currentPrompt} />
            </div>
        </div>
      )}

      {/* Attributes View */}
      <div style={{ display: view === 'attributes' ? 'flex' : 'none' }} className="flex-col overflow-y-auto flex-grow w-full h-full bg-white dark:bg-gray-800 scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600 rounded-lg">
        <div className={`p-6 space-y-2 flex-grow ${(!sceneEntity || sceneEntity.attributes.length === 0) ? 'flex flex-col' : ''}`}>
          {isLoading && (!sceneEntity || sceneEntity.attributes.length === 0) && (
              <div className="space-y-4">
                  {[...Array(8)].map((_, i) => (
                      <div key={i} className="h-10 bg-gray-100 dark:bg-gray-700 rounded-lg animate-pulse" />
                  ))}
              </div>
          )}
          {sceneEntity && sceneEntity.attributes.length > 0 ? (
            sceneEntity.attributes
            .filter(attr => attr.name !== 'existence' && attr.name !== 'existence_in_image')
            .map(attr => (
              <AttributeEditor 
                key={`${sceneEntity.name}-${attr.name}`} 
                attribute={attr} 
                entity={sceneEntity} 
                onChange={handleAttributeChange} 
                isLoading={isLoading}
                pendingValue={pendingAttributeUpdates[`${sceneEntity.name}:${attr.name}`]}
              />
            ))
          ) : (
             !isLoading && <EmptyStatePlaceholder text="Attributes will appear here after generation." />
          )}
        </div>
      </div>

      {/* Graph View */}
      <div 
        style={{ display: view === 'graph' ? 'flex' : 'none', touchAction: 'none' }} 
        className="flex-col flex-grow w-full h-full cursor-move active:cursor-grabbing relative group rounded-lg"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
        onWheel={handleWheel}
      >
        <div 
          className={`relative bg-gray-50/50 dark:bg-gray-900/50 w-full h-full overflow-hidden rounded-lg ${!data && !isLoading ? 'flex items-center justify-center p-6' : ''}`} 
          ref={measureRef}
        >
            {data && (
                <div className="absolute top-4 left-4 flex flex-col gap-2 z-40">
                    <button onClick={zoomIn} className="bg-white dark:bg-gray-700 p-2 rounded shadow text-gray-600 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600 focus:outline-none" title="Zoom In">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clipRule="evenodd" /></svg>
                    </button>
                    <button onClick={zoomOut} className="bg-white dark:bg-gray-700 p-2 rounded shadow text-gray-600 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600 focus:outline-none" title="Zoom Out">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M5 10a1 1 0 011-1h8a1 1 0 110 2H6a1 1 0 01-1-1z" clipRule="evenodd" /></svg>
                    </button>
                    <button onClick={resetView} className="bg-white dark:bg-gray-700 p-2 rounded shadow text-gray-600 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600 focus:outline-none" title="Reset View">
                         <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" /></svg>
                    </button>
                </div>
            )}

            {!data && !isLoading && (
               <EmptyStatePlaceholder text="The belief graph will visualize entities and relationships after generation." />
            )}

            {data && (
              <svg width="100%" height="100%" viewBox={`0 0 ${dimensions.width || 600} ${dimensions.height || 400}`} className="overflow-hidden select-none">
                  <defs><marker id="arrowhead" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#a0aec0" /></marker></defs>
                  
                  <g transform={`translate(${viewTransform.x}, ${viewTransform.y}) scale(${viewTransform.k})`}>
                    {relationships.map((rel, i) => {
                        const sourcePos = nodePositions[rel.source];
                        const targetPos = nodePositions[rel.target];
                        
                        if (!sourcePos || !targetPos) return null;
                        const sourceDims = nodeDimensions[rel.source];
                        const targetDims = nodeDimensions[rel.target];
                        if (!sourceDims || !targetDims) return null;

                        const { path, labelX, labelY } = getEdgePath(
                            sourcePos.x, sourcePos.y, 
                            targetPos.x, targetPos.y, 
                            sourceDims.width, sourceDims.height,
                            targetDims.width, targetDims.height
                        );

                        let opacity = 1;
                        if (hoveredRel) opacity = (rel === hoveredRel) ? 1 : 0.1;
                        else if (hoveredEntity) opacity = (rel.source === hoveredEntity || rel.target === hoveredEntity) ? 1 : 0.1;
                        else if (selectedEntity) opacity = (rel.source === selectedEntity.name || rel.target === selectedEntity.name) ? 1 : 0.1;

                        const isSelected = selectedRel?.rel.source === rel.source && selectedRel?.rel.target === rel.target && selectedRel?.rel.label === rel.label;
                        const isModified = pendingRelationshipUpdates[`${rel.source}:${rel.target}`] !== undefined;
                        const currentLabel = pendingRelationshipUpdates[`${rel.source}:${rel.target}`] || rel.label;

                        return (
                        <g key={`rel-${i}`} style={{ opacity, transition: 'opacity 0.3s ease-in-out' }}
                            className="cursor-pointer"
                            onMouseEnter={() => setHoveredRel(rel)}
                            onMouseLeave={() => setHoveredRel(null)}
                            onPointerDown={(e) => { e.stopPropagation(); }} 
                            onClick={(e) => { e.stopPropagation(); handleRelationshipClick(rel, e); }}
                        >
                            <path d={path} stroke={isModified ? '#3b82f6' : (isSelected ? '#3b82f6' : '#a0aec0')} strokeWidth={isModified ? "3" : "2"} fill="none" markerEnd="url(#arrowhead)" />
                            <text 
                                x={labelX} y={labelY + 4} 
                                textAnchor="middle" 
                                fontSize="10" 
                                fill={isModified ? '#1d4ed8' : (isSelected ? '#1e40af' : '#2d3748')} 
                                fontWeight="bold" 
                                stroke="white" 
                                strokeWidth="8px" 
                                strokeLinejoin="round" 
                                paintOrder="stroke"
                            >
                            {truncate(currentLabel, 16)}
                            </text>
                        </g>
                        );
                    })}
                    {objectEntities.map(entity => {
                        const pos = nodePositions[entity.name];
                        if (!pos) return null;
                        const isSelected = selectedEntity?.name === entity.name;
                        const dims = nodeDimensions[entity.name];
                        const hasModifiedAttr = Object.keys(pendingAttributeUpdates).some(k => k.startsWith(`${entity.name}:`));

                        let opacity = 1;
                        if (hoveredRel) opacity = (entity.name === hoveredRel.source || entity.name === hoveredRel.target) ? 1 : 0.1;
                        else if (hoveredEntity) opacity = (entity.name === hoveredEntity || neighborsOfHovered.has(entity.name)) ? 1 : 0.1;
                        else if (selectedEntity) opacity = (entity.name === selectedEntity.name || (neighborsOfSelected && neighborsOfSelected.has(entity.name))) ? 1 : 0.1;

                        return (
                        <g key={entity.name} transform={`translate(${pos.x || 0}, ${pos.y || 0})`}
                            onClick={(e) => { e.stopPropagation(); setSelectedEntity(entity); setSelectedRel(null); }}
                            onMouseEnter={() => setHoveredEntity(entity.name)} 
                            onMouseLeave={() => setHoveredEntity(null)}
                            style={{ opacity, transition: 'opacity 0.3s ease-in-out' }}>
                            <rect x={-(dims?.width || 90) / 2} y={-(dims?.height || 36) / 2} width={dims?.width || 90} height={dims?.height || 36} rx="8"
                            fill={isSelected ? '#fefcbf' : (hasModifiedAttr ? '#eff6ff' : '#ffffff')} 
                            stroke={isSelected ? '#f6e05e' : (hasModifiedAttr ? '#3b82f6' : '#cbd5e0')}
                            strokeWidth={hasModifiedAttr ? "2" : "2"} strokeDasharray={entity.presence_in_prompt ? 'none' : '4 2'} />
                            <text textAnchor="middle" dy="0.3em" fill="#2d3748" fontSize="12" fontWeight="600">{entity.name}</text>
                        </g>
                        );
                    })}
                  </g>
              </svg>
            )}

            {data && objectEntities.length === 0 && !isLoading && (
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <div className="text-center text-gray-500 bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm p-4 rounded-lg pointer-events-auto">
                      <p className="font-semibold">No objects found to display.</p>
                      <p className="text-sm mt-1">Check the attributes tab.</p>
                    </div>
                  </div>
            )}
        </div>

        {selectedRel && (
            <RelationshipEditor
            rel={selectedRel.rel}
            position={selectedRel.position}
            containerDimensions={dimensions}
            onClose={() => setSelectedRel(null)}
            isLoading={isLoading}
            onChange={(newLabel) => handleRelationshipChange(selectedRel.rel.source, selectedRel.rel.target, newLabel)}
            />
        )}

        {selectedEntity && (
            <div 
            className={`absolute bottom-4 left-4 right-4 md:w-96 bg-white/95 dark:bg-gray-800/95 backdrop-blur-sm rounded-lg border border-gray-200 dark:border-gray-700 shadow-xl animate-fade-in z-[100] flex flex-col overflow-hidden ${cardStyle ? '' : 'md:right-4 md:top-4 md:bottom-auto md:left-auto md:max-h-[60vh]'}`}
            style={{...cardStyle, touchAction: 'pan-y'}}
            onClick={(e) => e.stopPropagation()}
            onPointerDown={(e) => e.stopPropagation()} // Stop panning when interacting with box
            onWheel={(e) => e.stopPropagation()} // Stop zooming when scrolling box
            >
            {/* Absolute Close Button */}
            <button 
                onClick={() => setSelectedEntity(null)} 
                className="absolute top-3 right-3 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 z-10 bg-white/50 dark:bg-gray-800/50 rounded-full p-1"
                aria-label="Close"
            >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
            </button>

            {/* Scrollable Area */}
            <div className="overflow-y-auto p-4 pt-5 min-h-0 flex-grow scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600">
                <div className="pr-8 mb-2"> {/* Right padding for close button */}
                    <h3 className="font-bold text-lg text-gray-800 dark:text-gray-100 leading-tight">Entity: {selectedEntity.name}</h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 italic mt-1">{selectedEntity.description}</p>
                </div>
                
                <div className="border-b border-gray-100 dark:border-gray-700 mb-3"></div>

                {selectedEntity.attributes.length > 0 && (
                    <div className="space-y-1">
                    {selectedEntity.attributes.map(attr => (
                        <AttributeEditor 
                            key={attr.name} 
                            attribute={attr} 
                            entity={selectedEntity} 
                            onChange={handleAttributeChange} 
                            isLoading={isLoading} 
                            pendingValue={pendingAttributeUpdates[`${selectedEntity.name}:${attr.name}`]}
                        />
                    ))}
                    </div>
                )}
            </div>
            </div>
        )}
      </div>

      <style>{`
        @keyframes fade-in-up { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .animate-fade-in-up { animation: fade-in-up 0.3s ease-out forwards; }
        @keyframes fade-in { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
        .animate-fade-in { animation: fade-in 0.2s ease-out forwards; }
      `}</style>
    </div>
  );
};

export default BeliefGraph;
