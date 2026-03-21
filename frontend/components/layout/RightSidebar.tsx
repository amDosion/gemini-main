
import React, { useState, useMemo, useEffect } from 'react';
import { X, UserCircle2, Info, Plus, Pencil, Trash2, RotateCcw, ChevronDown, ChevronRight, CheckCircle2 } from 'lucide-react';
import { Persona } from '../../types/types';
import { PERSONA_CATEGORIES } from '../../constants/personaCategories';
import { getPersonaIcon } from '../../utils/iconUtils';
import PersonaModal from '../modals/PersonaModal';

interface RightSidebarProps {
  isOpen: boolean;
  setIsOpen: (isOpen: boolean) => void;
  personas: Persona[];
  activePersonaId: string;
  onSelectPersona: (id: string) => void;
  onCreatePersona: (p: Omit<Persona, 'id'>) => void;
  onUpdatePersona: (id: string, p: Partial<Persona>) => void;
  onDeletePersona: (id: string) => void;
  onRefreshPersonas: () => void;
}

const RightSidebar: React.FC<RightSidebarProps> = ({ 
  isOpen, 
  setIsOpen, 
  personas,
  activePersonaId,
  onSelectPersona,
  onCreatePersona,
  onUpdatePersona,
  onDeletePersona,
  onRefreshPersonas
}) => {
  const [editingPersona, setEditingPersona] = useState<Persona | undefined>(undefined);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedPersonaId, setSelectedPersonaId] = useState<string>(activePersonaId);
  // Track collapsed categories. Empty set means all categories are expanded by default.
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(
    new Set()
  );

  const handleCreate = () => {
    setEditingPersona(undefined);
    setIsModalOpen(true);
  };

  const handleEdit = (persona: Persona) => {
    setEditingPersona(persona);
    setIsModalOpen(true);
  };

  const handleDelete = (id: string) => {
    if (confirm('Are you sure you want to delete this persona?')) {
      onDeletePersona(id);
    }
  };

  const handlePreviewPersona = (id: string) => {
    setSelectedPersonaId(id);
  };

  const handleActivatePersona = (id: string) => {
    setSelectedPersonaId(id);
    onSelectPersona(id);
  };

  const handleSaveModal = (personaData: Persona | Omit<Persona, 'id'>) => {
    if ('id' in personaData) {
      onUpdatePersona(personaData.id, personaData);
    } else {
      onCreatePersona(personaData);
    }
  };

  const toggleCategory = (cat: string) => {
      const newSet = new Set(collapsedCategories);
      if (newSet.has(cat)) newSet.delete(cat);
      else newSet.add(cat);
      setCollapsedCategories(newSet);
  };

  // Group Personas by Category
  const groupedPersonas = useMemo(() => {
      const groups: Record<string, Persona[]> = {};
      
      // Initialize with preferred order (optional, ensuring standard cats come first)
      PERSONA_CATEGORIES.forEach(cat => groups[cat] = []);
      groups['Other'] = [];

      personas.forEach(p => {
          const cat = p.category || 'General'; // Fallback
          if (!groups[cat]) groups[cat] = [];
          groups[cat].push(p);
      });

      // Remove empty categories
      return Object.entries(groups).filter(([_, items]) => items.length > 0);
  }, [personas]);

  const selectedPersona = useMemo(() => {
    if (personas.length === 0) return null;
    return (
      personas.find((p) => p.id === selectedPersonaId) ||
      personas.find((p) => p.id === activePersonaId) ||
      personas[0]
    );
  }, [personas, selectedPersonaId, activePersonaId]);

  useEffect(() => {
    if (!isOpen) return;

    if (personas.length === 0) {
      if (selectedPersonaId !== '') setSelectedPersonaId('');
      return;
    }

    const hasSelected = personas.some((p) => p.id === selectedPersonaId);
    if (hasSelected) return;

    const fallbackId = personas.some((p) => p.id === activePersonaId)
      ? activePersonaId
      : personas[0].id;

    if (fallbackId !== selectedPersonaId) {
      setSelectedPersonaId(fallbackId);
    }
  }, [isOpen, personas, activePersonaId, selectedPersonaId]);

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, setIsOpen]);

  return (
    <>
      <PersonaModal 
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSave={handleSaveModal}
        initialPersona={editingPersona}
      />

      {/* Backdrop Overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar Content */}
      <div className={`fixed inset-y-0 right-0 z-50 w-full md:w-[88vw] md:max-w-[1120px] bg-slate-950 border-l border-slate-800 shadow-2xl transform transition-transform duration-300 ease-in-out ${
        isOpen ? 'translate-x-0 pointer-events-auto' : 'translate-x-full pointer-events-none'
      }`}>
        
        <div className="flex flex-col h-full">
          
          {/* Header */}
          <div className="p-4 flex items-center justify-between border-b border-slate-800/50">
            <div className="flex items-center gap-2 font-bold text-white">
                <UserCircle2 size={20} className="text-indigo-400" />
                <span>AI Persona</span>
            </div>
            <button onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-white">
              <X size={20} />
            </button>
          </div>

          {/* Actions */}
          <div className="p-3 border-b border-slate-800/50 flex gap-2 shrink-0">
            <button 
              onClick={handleCreate}
              className="flex-1 flex items-center justify-center gap-2 bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-400 text-xs font-medium py-2 rounded-lg transition-colors border border-indigo-500/20"
            >
              <Plus size={14} /> Create New
            </button>
            <button 
              onClick={onRefreshPersonas}
              className="px-3 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white text-xs font-medium rounded-lg transition-colors border border-slate-700"
              title="Refresh personas from server"
            >
              <RotateCcw size={14} />
            </button>
          </div>

          <div className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-[320px_minmax(0,1fr)]">
            {/* Left Persona List */}
            <div className="min-h-0 max-h-[44vh] md:max-h-none flex flex-col border-b md:border-b-0 md:border-r border-slate-800/60 bg-slate-900/35">
              <div className="px-4 py-3 border-b border-slate-800/60 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">角色列表</span>
                <span className="text-[11px] text-slate-500">{personas.length} roles</span>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
                {groupedPersonas.length === 0 && (
                  <div className="text-xs text-slate-500 border border-slate-800 rounded-lg p-3 bg-slate-900/60">
                    No persona available. Click Create New to add one.
                  </div>
                )}

                {groupedPersonas.map(([category, items]) => {
                  const isCollapsed = collapsedCategories.has(category);
                  return (
                    <div key={category} className="space-y-2">
                      <button
                        onClick={() => toggleCategory(category)}
                        className="w-full flex items-center justify-between text-xs font-bold text-slate-500 uppercase tracking-wider hover:text-slate-300 transition-colors"
                      >
                        <span>{category}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-600">{items.length}</span>
                          {isCollapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
                        </div>
                      </button>

                      {!isCollapsed && (
                        <div className="space-y-2 animate-[fadeIn_0.2s_ease-out]">
                          {items.map((persona) => {
                            const Icon = getPersonaIcon(persona.icon);
                            const isSelected = selectedPersona?.id === persona.id;
                            const isActive = activePersonaId === persona.id;

                            return (
                              <button
                                key={persona.id}
                                type="button"
                                onClick={() => handlePreviewPersona(persona.id)}
                                className={`w-full flex items-start gap-3 p-3 rounded-xl border text-left transition-all ${
                                  isSelected
                                    ? 'bg-indigo-600/10 border-indigo-500/50 shadow-[0_0_15px_rgba(99,102,241,0.1)]'
                                    : 'bg-slate-800/40 border-slate-700/50 hover:bg-slate-800 hover:border-slate-600'
                                }`}
                              >
                                <div className={`p-2 rounded-lg shrink-0 transition-colors ${
                                  isSelected ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-400'
                                }`}>
                                  <Icon size={18} />
                                </div>
                                <div className="min-w-0 flex-1">
                                  <div className={`text-sm font-semibold mb-0.5 truncate ${isSelected ? 'text-indigo-300' : 'text-slate-200'}`}>
                                    {persona.name}
                                  </div>
                                  <div className="text-xs text-slate-500 leading-snug line-clamp-2">
                                    {persona.description || 'No description'}
                                  </div>
                                </div>
                                {isActive && (
                                  <span className="mt-0.5 text-[10px] px-1.5 py-0.5 rounded border border-emerald-500/30 text-emerald-300 bg-emerald-500/10">
                                    Active
                                  </span>
                                )}
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Right Persona Details */}
            <div className="min-h-0 flex flex-col">
              {!selectedPersona ? (
                <div className="h-full flex flex-col items-center justify-center text-center px-6">
                  <UserCircle2 size={36} className="text-slate-600 mb-3" />
                  <p className="text-sm text-slate-300">No persona selected</p>
                  <p className="text-xs text-slate-500 mt-1">Create a persona to get started.</p>
                </div>
              ) : (
                <>
                  <div className="px-5 md:px-6 py-4 border-b border-slate-800/60 flex items-start justify-between gap-4">
                    <div className="min-w-0 flex items-start gap-3">
                      <div className="p-2.5 rounded-xl bg-indigo-600/15 border border-indigo-500/30 text-indigo-300 shrink-0">
                        {(() => {
                          const Icon = getPersonaIcon(selectedPersona.icon);
                          return <Icon size={20} />;
                        })()}
                      </div>
                      <div className="min-w-0">
                        <h3 className="text-lg font-semibold text-white truncate">{selectedPersona.name}</h3>
                        <div className="mt-1 flex items-center gap-2">
                          <span className="text-[11px] px-2 py-0.5 rounded-full border border-slate-700 bg-slate-800/80 text-slate-300">
                            {selectedPersona.category || 'General'}
                          </span>
                          {activePersonaId === selectedPersona.id && (
                            <span className="text-[11px] px-2 py-0.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 inline-flex items-center gap-1">
                              <CheckCircle2 size={12} />
                              当前启用
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {activePersonaId !== selectedPersona.id && (
                        <button
                          type="button"
                          onClick={() => handleActivatePersona(selectedPersona.id)}
                          className="px-3 py-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 text-xs font-medium transition-colors"
                        >
                          设为当前
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleEdit(selectedPersona)}
                        className="px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-900 text-slate-300 hover:bg-slate-800 text-xs font-medium transition-colors inline-flex items-center gap-1.5"
                      >
                        <Pencil size={12} />
                        编辑
                      </button>
                      {personas.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleDelete(selectedPersona.id)}
                          className="px-3 py-1.5 rounded-lg border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 text-xs font-medium transition-colors inline-flex items-center gap-1.5"
                        >
                          <Trash2 size={12} />
                          删除
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="flex-1 overflow-y-auto custom-scrollbar px-5 md:px-6 py-5 space-y-5">
                    <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">角色描述</h4>
                      <p className="text-sm text-slate-200 leading-relaxed">
                        {selectedPersona.description || 'No description provided.'}
                      </p>
                    </section>

                    <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">System Prompt</h4>
                      <pre className="text-xs md:text-sm text-slate-200 leading-relaxed whitespace-pre-wrap break-words font-sans max-h-[42vh] overflow-y-auto custom-scrollbar pr-1">
                        {selectedPersona.systemPrompt || 'No system prompt configured.'}
                      </pre>
                    </section>

                    <section className="p-3 bg-blue-900/10 border border-blue-500/20 rounded-xl flex gap-3 text-xs text-blue-300/80">
                      <Info size={16} className="shrink-0 mt-0.5" />
                      <p>
                        Personas act as system prompts. Editing them changes the behavior of the AI for subsequent messages.
                      </p>
                    </section>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default RightSidebar;
