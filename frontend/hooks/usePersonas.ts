
import { useState, useEffect } from 'react';
import { Persona } from '../config/personas';
import { DEFAULT_PERSONAS } from '../config/personas';
import { v4 as uuidv4 } from 'uuid';

export const usePersonas = (
  initialData?: {
    personas: Persona[];
  }
) => {
  // ✅ 使用 initialData 初始化状态（如果提供），否则使用默认值
  const [personas, setPersonas] = useState<Persona[]>(
    initialData?.personas || DEFAULT_PERSONAS
  );
  const [activePersonaId, setActivePersonaId] = useState<string>('general');

  // ❌ 移除从 localStorage 加载的 useEffect
  // 初始化数据现在来自 initialData（由 useInitData 提供）
  // localStorage 仅用于保存用户修改（CRUD 操作后）

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
