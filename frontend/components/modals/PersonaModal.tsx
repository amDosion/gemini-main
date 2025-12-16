
import React, { useState, useEffect } from 'react';
import { X, Save, Tag } from 'lucide-react';
import { Persona, PERSONA_CATEGORIES } from '../../config/personas';
import { ICON_MAP, AVAILABLE_ICONS } from '../../utils/iconUtils';

interface PersonaModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (persona: Omit<Persona, 'id'> | Persona) => void;
  initialPersona?: Persona;
}

const PersonaModal: React.FC<PersonaModalProps> = ({ isOpen, onClose, onSave, initialPersona }) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [selectedIcon, setSelectedIcon] = useState('MessageSquare');
  const [category, setCategory] = useState('General');

  useEffect(() => {
    if (isOpen) {
      if (initialPersona) {
        setName(initialPersona.name);
        setDescription(initialPersona.description);
        setSystemPrompt(initialPersona.systemPrompt);
        setSelectedIcon(initialPersona.icon);
        setCategory(initialPersona.category || 'General');
      } else {
        setName('');
        setDescription('');
        setSystemPrompt('');
        setSelectedIcon('MessageSquare');
        setCategory('General');
      }
    }
  }, [isOpen, initialPersona]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const personaData = {
      name,
      description,
      systemPrompt,
      icon: selectedIcon,
      category,
      ...(initialPersona ? { id: initialPersona.id } : {})
    };
    onSave(personaData as Persona);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]">
      <div className="relative w-full max-w-2xl bg-slate-950 border border-slate-800 rounded-2xl shadow-2xl flex flex-col max-h-[90vh]">
        
        <div className="flex items-center justify-between p-4 border-b border-slate-800">
          <h2 className="text-xl font-bold text-white">
            {initialPersona ? 'Edit Persona' : 'Create New Persona'}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-300">Name</label>
              <input
                type="text"
                required
                value={name}
                onChange={e => setName(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-sm focus:border-indigo-500 outline-none text-slate-200"
                placeholder="e.g. Coding Expert"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-300 flex items-center gap-1.5">
                  <Tag size={12} /> Category
              </label>
              <div className="relative">
                  <select 
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-sm focus:border-indigo-500 outline-none text-slate-200 appearance-none"
                  >
                      {PERSONA_CATEGORIES.map(cat => (
                          <option key={cat} value={cat}>{cat}</option>
                      ))}
                      <option value="Other">Other</option>
                  </select>
                  <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500">
                      <svg width="10" height="6" viewBox="0 0 10 6" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                  </div>
              </div>
            </div>
            
            <div className="space-y-2 md:col-span-2">
              <label className="text-sm font-medium text-slate-300">Icon</label>
              <div className="grid grid-cols-8 sm:grid-cols-10 gap-2 bg-slate-900 p-3 rounded-lg border border-slate-700 max-h-32 overflow-y-auto custom-scrollbar">
                {AVAILABLE_ICONS.map(iconKey => {
                  const Icon = ICON_MAP[iconKey];
                  return (
                    <button
                      key={iconKey}
                      type="button"
                      onClick={() => setSelectedIcon(iconKey)}
                      className={`p-2 rounded-lg flex items-center justify-center transition-all ${
                        selectedIcon === iconKey 
                        ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/30' 
                        : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'
                      }`}
                      title={iconKey}
                    >
                      <Icon size={18} />
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-300">Description</label>
            <input
              type="text"
              required
              value={description}
              onChange={e => setDescription(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-sm focus:border-indigo-500 outline-none text-slate-200"
              placeholder="Short description of capabilities..."
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-300">System Instructions</label>
            <textarea
              required
              value={systemPrompt}
              onChange={e => setSystemPrompt(e.target.value)}
              className="w-full h-40 bg-slate-900 border border-slate-700 rounded-lg px-4 py-3 text-sm focus:border-indigo-500 outline-none text-slate-200 resize-none font-mono"
              placeholder="You are a..."
            />
            <p className="text-xs text-slate-500">
              These instructions define how the AI behaves. Be specific about tone, style, and constraints.
            </p>
          </div>
        </form>

        <div className="p-4 border-t border-slate-800 flex justify-end gap-3">
          <button 
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-900 transition-colors text-sm font-medium"
          >
            Cancel
          </button>
          <button 
            onClick={handleSubmit}
            className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg transition-all text-sm font-medium flex items-center gap-2"
          >
            <Save size={16} />
            Save Persona
          </button>
        </div>

      </div>
    </div>
  );
};

export default PersonaModal;
