
import React, { useState, useMemo } from 'react';
import { X, UserCircle2, Info, Plus, Pencil, Trash2, RotateCcw, ChevronDown, ChevronRight } from 'lucide-react';
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
  // Optional: State to toggle category collapse. Defaults to all collapsed.
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(
    new Set([...PERSONA_CATEGORIES, 'Other'])
  );

  const handleCreate = () => {
    setEditingPersona(undefined);
    setIsModalOpen(true);
  };

  const handleEdit = (e: React.MouseEvent, persona: Persona) => {
    e.stopPropagation();
    setEditingPersona(persona);
    setIsModalOpen(true);
  };

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (confirm('Are you sure you want to delete this persona?')) {
      onDeletePersona(id);
    }
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

  return (
    <>
      <PersonaModal 
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSave={handleSaveModal}
        initialPersona={editingPersona}
      />

      {/* Mobile Overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar Content */}
      <div className={`fixed inset-y-0 right-0 z-50 w-80 bg-slate-900 border-l border-slate-800 transform transition-transform duration-300 ease-in-out lg:relative lg:translate-x-0 ${
        isOpen ? 'translate-x-0' : 'translate-x-full lg:hidden'
      } ${!isOpen && 'lg:!hidden'}`}>
        
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
          <div className="p-3 border-b border-slate-800/50 flex gap-2">
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

          {/* Persona List Grouped */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
              
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
                                  {items.map(p => {
                                      const isActive = activePersonaId === p.id;
                                      const Icon = getPersonaIcon(p.icon);
                                      return (
                                          <div
                                            key={p.id}
                                            onClick={() => {
                                                onSelectPersona(p.id);
                                                if (window.innerWidth < 1024) setIsOpen(false);
                                            }}
                                            className={`relative w-full flex items-start gap-3 p-3 rounded-xl border text-left transition-all group cursor-pointer ${
                                                isActive 
                                                ? 'bg-indigo-600/10 border-indigo-500/50 shadow-[0_0_15px_rgba(99,102,241,0.1)]' 
                                                : 'bg-slate-800/40 border-slate-700/50 hover:bg-slate-800 hover:border-slate-600'
                                            }`}
                                          >
                                              <div className={`p-2 rounded-lg shrink-0 transition-colors ${
                                                  isActive ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-400 group-hover:text-slate-200'
                                              }`}>
                                                  <Icon size={20} />
                                              </div>
                                              <div className="min-w-0 flex-1">
                                                  <div className={`text-sm font-semibold mb-0.5 ${isActive ? 'text-indigo-300' : 'text-slate-200'}`}>
                                                      {p.name}
                                                  </div>
                                                  <div className="text-xs text-slate-500 leading-snug line-clamp-2 pr-6">
                                                      {p.description}
                                                  </div>
                                              </div>
                                              
                                              {/* Edit/Delete Actions */}
                                              <div className={`absolute right-2 top-2 flex flex-col gap-1 transition-opacity ${isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>
                                                <button 
                                                  onClick={(e) => handleEdit(e, p)}
                                                  className="p-1.5 rounded-md hover:bg-slate-700 text-slate-400 hover:text-white bg-slate-900/50 backdrop-blur-sm"
                                                >
                                                  <Pencil size={12} />
                                                </button>
                                                {personas.length > 1 && (
                                                  <button 
                                                    onClick={(e) => handleDelete(e, p.id)}
                                                    className="p-1.5 rounded-md hover:bg-red-900/50 text-slate-400 hover:text-red-400 bg-slate-900/50 backdrop-blur-sm"
                                                  >
                                                    <Trash2 size={12} />
                                                  </button>
                                                )}
                                              </div>
                                          </div>
                                      )
                                  })}
                              </div>
                          )}
                      </div>
                  );
              })}
          </div>

          {/* Footer - Fixed at bottom */}
          <div className="p-4 border-t border-slate-800/50 bg-slate-900 shrink-0">
              <div className="p-3 bg-blue-900/10 border border-blue-500/20 rounded-xl flex gap-3 text-xs text-blue-300/80">
                  <Info size={16} className="shrink-0 mt-0.5" />
                  <p>
                      Personas act as system prompts. Editing them changes the behavior of the AI for subsequent messages.
                  </p>
              </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default RightSidebar;
