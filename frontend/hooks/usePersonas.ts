
import { useState, useEffect, useCallback } from 'react';
import { Persona } from '../types/types';
import { v4 as uuidv4 } from 'uuid';
import { db } from '../services/db';

export const usePersonas = (
  initialData?: {
    personas: Persona[];
  }
) => {
  // ✅ 使用 initialData 初始化状态（如果提供），否则使用空数组（等待后端初始化）
  const [personas, setPersonas] = useState<Persona[]>(
    initialData?.personas || []
  );
  const [activePersonaId, setActivePersonaId] = useState<string>('general');

  // ✅ 当 initialData 更新时，同步更新 personas
  useEffect(() => {
    if (initialData?.personas) {
      setPersonas(initialData.personas);
      // 如果当前 activePersonaId 不在新的 personas 中，重置为第一个
      if (initialData.personas.length > 0 && !initialData.personas.find(p => p.id === activePersonaId)) {
        setActivePersonaId(initialData.personas[0].id);
      }
    }
  }, [initialData?.personas, activePersonaId]);

  // ✅ 保存到后端（后端会自动处理时间戳）
  const saveToBackend = useCallback(async (newPersonas: Persona[]) => {
    try {
      await db.savePersonas(newPersonas);
    } catch (error) {
      console.error('Failed to save personas to backend:', error);
      throw error;
    }
  }, []);

  const createPersona = useCallback(async (persona: Omit<Persona, 'id'>) => {
    const newPersona = { ...persona, id: uuidv4() };
    const updated = [...personas, newPersona];
    setPersonas(updated);
    try {
      await saveToBackend(updated);
    } catch (error) {
      // 回滚状态
      setPersonas(personas);
      throw error;
    }
    return newPersona;
  }, [personas, saveToBackend]);

  const updatePersona = useCallback(async (id: string, updates: Partial<Persona>) => {
    const previousPersonas = personas;
    const updated = personas.map(p => p.id === id ? { ...p, ...updates } : p);
    setPersonas(updated);
    try {
      await saveToBackend(updated);
    } catch (error) {
      // 回滚状态
      setPersonas(previousPersonas);
      throw error;
    }
  }, [personas, saveToBackend]);

  const deletePersona = useCallback(async (id: string) => {
    // Prevent deleting the last one
    if (personas.length <= 1) return;
    
    const previousPersonas = personas;
    const updated = personas.filter(p => p.id !== id);
    setPersonas(updated);
    
    try {
      await saveToBackend(updated);
      
      if (activePersonaId === id) {
        setActivePersonaId(updated[0].id);
      }
    } catch (error) {
      // 回滚状态
      setPersonas(previousPersonas);
      throw error;
    }
  }, [personas, activePersonaId, saveToBackend]);

  const refreshPersonas = useCallback(async () => {
    try {
      // 刷新功能：重新从后端获取最新的 Personas 数据（不删除、不重置）
      const refreshedPersonas = await db.getPersonas();
      // 更新本地状态
      setPersonas(refreshedPersonas);
      // 如果当前激活的 Persona 不在新列表中，选择第一个
      if (refreshedPersonas.length > 0) {
        const currentPersonaExists = refreshedPersonas.find(p => p.id === activePersonaId);
        if (!currentPersonaExists) {
          setActivePersonaId(refreshedPersonas[0].id);
        }
      }
    } catch (error) {
      console.error('Failed to refresh personas:', error);
      throw error;
    }
  }, [activePersonaId]);

  const activePersona = personas.find(p => p.id === activePersonaId) || personas[0];

  return {
    personas,
    activePersona,
    activePersonaId,
    setActivePersonaId,
    createPersona,
    updatePersona,
    deletePersona,
    refreshPersonas
  };
};
