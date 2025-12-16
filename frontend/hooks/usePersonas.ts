
import { useState, useEffect } from 'react';
import { Persona } from '../config/personas';
import { DEFAULT_PERSONAS } from '../config/personas';
import { v4 as uuidv4 } from 'uuid';

export const usePersonas = () => {
  const [personas, setPersonas] = useState<Persona[]>(DEFAULT_PERSONAS);
  const [activePersonaId, setActivePersonaId] = useState<string>('general');

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem('flux_personas');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setPersonas(parsed);
        }
      }
    } catch (e) {
      console.error("Failed to load personas (storage access denied or invalid)", e);
    }
  }, []);

  const saveToStorage = (newPersonas: Persona[]) => {
    try {
      localStorage.setItem('flux_personas', JSON.stringify(newPersonas));
    } catch (e) {
      console.warn("Failed to save personas to storage", e);
    }
  };

  const createPersona = (persona: Omit<Persona, 'id'>) => {
    const newPersona = { ...persona, id: uuidv4() };
    const updated = [...personas, newPersona];
    setPersonas(updated);
    saveToStorage(updated);
    return newPersona;
  };

  const updatePersona = (id: string, updates: Partial<Persona>) => {
    const updated = personas.map(p => p.id === id ? { ...p, ...updates } : p);
    setPersonas(updated);
    saveToStorage(updated);
  };

  const deletePersona = (id: string) => {
    // Prevent deleting the last one
    if (personas.length <= 1) return;
    
    const updated = personas.filter(p => p.id !== id);
    setPersonas(updated);
    saveToStorage(updated);

    if (activePersonaId === id) {
      setActivePersonaId(updated[0].id);
    }
  };

  const resetPersonas = () => {
    setPersonas(DEFAULT_PERSONAS);
    saveToStorage(DEFAULT_PERSONAS);
    setActivePersonaId('general');
  };

  const activePersona = personas.find(p => p.id === activePersonaId) || personas[0];

  return {
    personas,
    activePersona,
    activePersonaId,
    setActivePersonaId,
    createPersona,
    updatePersona,
    deletePersona,
    resetPersonas
  };
};
