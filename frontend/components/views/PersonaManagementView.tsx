import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Info,
  MoreHorizontal,
  Pencil,
  Plus,
  RotateCcw,
  Search,
  Trash2,
  UserCircle2,
} from 'lucide-react';
import { Persona } from '../../types/types';
import { PERSONA_CATEGORIES } from '../../constants/personaCategories';
import { getPersonaIcon } from '../../utils/iconUtils';
import PersonaModal from '../modals/PersonaModal';
import ConfirmDialog from '../common/ConfirmDialog';
import { GenViewLayout } from '../common/GenViewLayout';
import {
  flatToolbarBarClass,
  flatToolbarButtonClass,
  flatToolbarSearchInputClass,
  flatToolbarSearchWrapClass,
  flatToolbarSectionClass,
  flatToolbarSeparatorClass,
  flatToolbarTitleClass
} from '../common/flatToolbarStyles';

interface PersonaManagementViewProps {
  personas: Persona[];
  activePersonaId: string;
  onSelectPersona: (id: string) => void;
  onCreatePersona: (p: Omit<Persona, 'id'>) => void;
  onUpdatePersona: (id: string, p: Partial<Persona>) => void;
  onDeletePersona: (id: string) => void;
  onRefreshPersonas: () => void;
  onClose: () => void;
}

export const PersonaManagementView: React.FC<PersonaManagementViewProps> = ({
  personas,
  activePersonaId,
  onSelectPersona,
  onCreatePersona,
  onUpdatePersona,
  onDeletePersona,
  onRefreshPersonas,
  onClose,
}) => {
  const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);
  const [editingPersona, setEditingPersona] = useState<Persona | undefined>(undefined);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedPersonaId, setSelectedPersonaId] = useState<string>(activePersonaId);
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [openActionPersonaId, setOpenActionPersonaId] = useState<string | null>(null);
  const [personaToDelete, setPersonaToDelete] = useState<Persona | null>(null);

  const normalizedQuery = useMemo(() => searchQuery.trim().toLowerCase(), [searchQuery]);
  const filteredPersonas = useMemo(() => {
    if (!normalizedQuery) return personas;
    return personas.filter((persona) => {
      const name = persona.name || '';
      const description = persona.description || '';
      const category = persona.category || '';
      const systemPrompt = persona.systemPrompt || '';
      return (
        name.toLowerCase().includes(normalizedQuery) ||
        description.toLowerCase().includes(normalizedQuery) ||
        category.toLowerCase().includes(normalizedQuery) ||
        systemPrompt.toLowerCase().includes(normalizedQuery)
      );
    });
  }, [personas, normalizedQuery]);

  const groupedPersonas = useMemo(() => {
    const groups: Record<string, Persona[]> = {};
    PERSONA_CATEGORIES.forEach((cat) => {
      groups[cat] = [];
    });
    groups.Other = [];

    filteredPersonas.forEach((persona) => {
      const category = persona.category || 'General';
      if (!groups[category]) groups[category] = [];
      groups[category].push(persona);
    });

    return Object.entries(groups).filter(([_, items]) => items.length > 0);
  }, [filteredPersonas]);

  const selectedPersona = useMemo(() => {
    if (personas.length === 0) return null;
    return (
      personas.find((p) => p.id === selectedPersonaId) ||
      personas.find((p) => p.id === activePersonaId) ||
      personas[0]
    );
  }, [personas, selectedPersonaId, activePersonaId]);

  useEffect(() => {
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
  }, [personas, activePersonaId, selectedPersonaId]);

  useEffect(() => {
    if (!openActionPersonaId) return;
    if (!personas.some((persona) => persona.id === openActionPersonaId)) {
      setOpenActionPersonaId(null);
    }
  }, [openActionPersonaId, personas]);

  useEffect(() => {
    if (!personaToDelete) return;
    if (!personas.some((persona) => persona.id === personaToDelete.id)) {
      setPersonaToDelete(null);
    }
  }, [personaToDelete, personas]);

  useEffect(() => {
    const handleOutsideClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest('[data-persona-item-actions]')) {
        return;
      }
      setOpenActionPersonaId(null);
    };

    document.addEventListener('mousedown', handleOutsideClick);
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
    };
  }, []);

  const handleCreate = () => {
    setEditingPersona(undefined);
    setIsModalOpen(true);
  };

  const handleEdit = (persona: Persona) => {
    setEditingPersona(persona);
    setIsModalOpen(true);
  };

  const handleDelete = (persona: Persona) => {
    setPersonaToDelete(persona);
  };

  const handleConfirmDelete = () => {
    if (!personaToDelete) return;
    onDeletePersona(personaToDelete.id);
    setPersonaToDelete(null);
  };

  const handleSaveModal = (personaData: Persona | Omit<Persona, 'id'>) => {
    if ('id' in personaData) {
      onUpdatePersona(personaData.id, personaData);
    } else {
      onCreatePersona(personaData);
    }
  };

  const toggleCategory = (category: string) => {
    setCollapsedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      return next;
    });
  };

  const sidebarSectionClass = 'border-b border-slate-800/70';
  const detailSectionClass = 'px-4 md:px-6 py-4 border-b border-slate-800/70';
  const detailHeadingClass = 'text-[11px] font-bold uppercase tracking-wider text-slate-500';
  const roleCountLabel = `${personas.length} role(s)`;
  const emptyPersonaMessage =
    personas.length === 0 ? 'No persona available' : 'No persona matched your search';
  const SelectedPersonaIcon = selectedPersona ? getPersonaIcon(selectedPersona.icon) : UserCircle2;

  const sidebarContent = (
    <div className="min-h-full">
      <div className={`${sidebarSectionClass} px-3 py-2.5`}>
        <div className="flex items-center justify-between gap-3">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Personas</span>
          <span className="text-xs text-slate-300 whitespace-nowrap">{roleCountLabel}</span>
        </div>
      </div>

      {groupedPersonas.length === 0 && (
        <p className="px-3 py-3 text-xs text-slate-500">
          {emptyPersonaMessage}
        </p>
      )}

      {groupedPersonas.map(([category, items]) => {
        const isCollapsed = collapsedCategories.has(category);
        return (
          <section key={category} className={sidebarSectionClass}>
            <button
              type="button"
              onClick={() => toggleCategory(category)}
              className="flex h-9 w-full items-center justify-between px-3 text-xs font-bold uppercase tracking-wider text-slate-500 transition-colors hover:text-slate-300"
            >
              <span>{category}</span>
              <span className="flex items-center gap-2 text-[10px]">
                <span className="text-slate-600">{items.length}</span>
                {isCollapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
              </span>
            </button>

            {!isCollapsed && (
              <div className="animate-[fadeIn_0.2s_ease-out]">
                {items.map((persona) => {
                  const Icon = getPersonaIcon(persona.icon);
                  const isSelected = selectedPersona?.id === persona.id;
                  const isActive = activePersonaId === persona.id;
                  const isActionOpen = openActionPersonaId === persona.id;

                  return (
                    <div key={persona.id} className="group relative border-t border-slate-800/60 first:border-t-0">
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedPersonaId(persona.id);
                          setOpenActionPersonaId(null);
                        }}
                        className={`flex w-full items-start gap-2.5 px-3 py-2.5 pr-10 text-left transition-colors ${
                          isSelected
                            ? 'bg-indigo-500/10 text-indigo-100'
                            : 'text-slate-200 hover:bg-slate-900/60'
                        }`}
                      >
                        <div
                          className={`mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${
                            isSelected ? 'bg-indigo-600 text-white' : 'bg-slate-800/80 text-slate-400'
                          }`}
                        >
                          <Icon size={15} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-xs font-semibold">{persona.name}</p>
                          <p className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-slate-500">
                            {persona.description || 'No description'}
                          </p>
                        </div>
                        {isActive && (
                          <span className="inline-flex h-5 shrink-0 items-center rounded border border-emerald-500/30 px-1.5 text-[10px] text-emerald-300">
                            Active
                          </span>
                        )}
                      </button>

                      <div
                        data-persona-item-actions
                        className={`absolute right-2 top-2 transition-opacity ${
                          isActionOpen ? 'opacity-100' : 'opacity-0 group-hover:opacity-100 group-focus-within:opacity-100'
                        }`}
                      >
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            setOpenActionPersonaId((prev) => (prev === persona.id ? null : persona.id));
                          }}
                          className="inline-flex h-6 w-6 items-center justify-center rounded text-slate-500 transition-colors hover:bg-slate-800/80 hover:text-white"
                          title="Actions"
                        >
                          <MoreHorizontal size={13} />
                        </button>

                        {isActionOpen && (
                          <div className="absolute right-0 top-7 z-20 min-w-28 rounded-md border border-slate-700 bg-slate-900 shadow-xl p-1">
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                setOpenActionPersonaId(null);
                                handleEdit(persona);
                              }}
                              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
                            >
                              <Pencil size={12} />
                              <span>编辑</span>
                            </button>
                            {personas.length > 1 && (
                              <button
                                type="button"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  setOpenActionPersonaId(null);
                                  handleDelete(persona);
                                }}
                                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs text-red-300 hover:bg-red-900/30"
                              >
                                <Trash2 size={12} />
                                <span>删除</span>
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );

  const mainContent = (
    <div className="h-full flex flex-col">
      <div className={flatToolbarBarClass}>
        <div className="min-w-0 h-full flex items-center">
          <span className={flatToolbarTitleClass}>AI Persona Manager</span>
        </div>

        <div className={flatToolbarSectionClass}>
          <label className={`${flatToolbarSearchWrapClass} w-44 md:w-52`}>
            <Search size={13} className="absolute left-1 top-1/2 -translate-y-1/2 text-slate-600" />
            <input
              type="text"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search personas"
              className={flatToolbarSearchInputClass}
            />
          </label>
          <span className={flatToolbarSeparatorClass}>｜</span>

          <button
            type="button"
            onClick={handleCreate}
            className={`${flatToolbarButtonClass} text-indigo-300 hover:text-indigo-200`}
            title="Create persona"
          >
            <Plus size={12} />
            Create
          </button>
          <button
            type="button"
            onClick={onRefreshPersonas}
            className={flatToolbarButtonClass}
            title="Refresh personas"
          >
            <RotateCcw size={12} />
            Refresh
          </button>

          {selectedPersona && activePersonaId !== selectedPersona.id && (
            <button
              type="button"
              onClick={() => onSelectPersona(selectedPersona.id)}
              className={`${flatToolbarButtonClass} text-emerald-300 hover:text-emerald-200`}
            >
              设为当前
            </button>
          )}

          <span className={flatToolbarSeparatorClass}>｜</span>

          <button
            type="button"
            onClick={onClose}
            className={flatToolbarButtonClass}
          >
            <ArrowLeft size={12} />
            Back
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {!selectedPersona ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-slate-400">
            <UserCircle2 size={36} className="text-slate-600 mb-3" />
            <p className="text-sm">No persona selected</p>
          </div>
        ) : (
          <>
            <section className={detailSectionClass}>
              <div className="flex items-start gap-3">
                <div className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-600/15 text-indigo-300">
                  <SelectedPersonaIcon size={18} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="truncate text-base font-semibold text-white">{selectedPersona.name}</h3>
                    <span className="inline-flex h-5 items-center rounded-full border border-slate-700 px-2 text-[11px] text-slate-300">
                      {selectedPersona.category || 'General'}
                    </span>
                    {activePersonaId === selectedPersona.id && (
                      <span className="inline-flex h-5 items-center gap-1 rounded-full border border-emerald-500/30 px-2 text-[11px] text-emerald-300">
                        <CheckCircle2 size={11} />
                        当前启用
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </section>

            <section className={detailSectionClass}>
              <h4 className={detailHeadingClass}>角色描述</h4>
              <p className="mt-2 text-sm leading-relaxed text-slate-200">
                {selectedPersona.description || 'No description provided.'}
              </p>
            </section>

            <section className={detailSectionClass}>
              <h4 className={detailHeadingClass}>System Prompt</h4>
              <pre className="mt-2 max-h-[44vh] overflow-y-auto whitespace-pre-wrap break-words pr-1 font-sans text-xs leading-relaxed text-slate-200 custom-scrollbar md:text-sm">
                {selectedPersona.systemPrompt || 'No system prompt configured.'}
              </pre>
            </section>

            <section className="px-4 md:px-6 py-3 text-xs text-blue-300/80">
              <div className="flex gap-2.5">
                <Info size={15} className="mt-0.5 shrink-0" />
                <p>
                  Personas act as system prompts. Editing them changes the behavior of the AI for subsequent messages.
                </p>
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );

  return (
    <>
      <PersonaModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSave={handleSaveModal}
        initialPersona={editingPersona}
      />
      <ConfirmDialog
        isOpen={personaToDelete !== null}
        title="Delete persona?"
        message={
          personaToDelete
            ? `Are you sure you want to delete "${personaToDelete.name}"?`
            : ''
        }
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onConfirm={handleConfirmDelete}
        onCancel={() => setPersonaToDelete(null)}
      />

      <GenViewLayout
        isMobileHistoryOpen={isMobileHistoryOpen}
        setIsMobileHistoryOpen={setIsMobileHistoryOpen}
        sidebarTitle="AI Persona"
        sidebarHeaderIcon={<UserCircle2 size={14} />}
        sidebar={sidebarContent}
        main={mainContent}
        hideSessionSwitcher
      />
    </>
  );
};

export default PersonaManagementView;
