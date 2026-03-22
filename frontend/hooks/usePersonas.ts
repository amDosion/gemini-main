import { useEffect, useCallback, useRef } from 'react';
import { Persona } from '../types/types';
import { v4 as uuidv4 } from 'uuid';
import { db } from '../services/db';
import { cacheManager, CACHE_DOMAINS } from '../services/CacheManager';
import { useCacheSubscription, useCacheUpdater } from './useCacheSubscription';

export const usePersonas = (
  initialData?: {
    personas: Persona[];
  }
) => {
  const initializedRef = useRef(false);

  // ✅ 订阅 CacheManager 中的数据
  const personas = useCacheSubscription<Persona[]>(CACHE_DOMAINS.PERSONAS, []);
  const activePersonaId = useCacheSubscription<string>(CACHE_DOMAINS.ACTIVE_PERSONA_ID, '');
  const personasUpdater = useCacheUpdater<Persona[]>(CACHE_DOMAINS.PERSONAS, []);
  const activeIdUpdater = useCacheUpdater<string>(CACHE_DOMAINS.ACTIVE_PERSONA_ID, '');

  // ✅ initData 仅用于首次初始化
  useEffect(() => {
    if (!initialData?.personas || initializedRef.current) return;
    const personas = initialData.personas;
    if (personas.length > 0) {
      initializedRef.current = true;
      personasUpdater.set(personas);
      // 设置第一个为 active（如果还没设过）
      const currentActive = cacheManager.get<string>(CACHE_DOMAINS.ACTIVE_PERSONA_ID);
      if (!currentActive) {
        activeIdUpdater.set(personas[0].id);
      }
    }
  }, [initialData, personasUpdater, activeIdUpdater]);

  // ✅ 当 initialData 更新时，同步更新 personas（后续更新）
  useEffect(() => {
    if (!initialData?.personas || !initializedRef.current) return;
    // initializedRef 已为 true，说明不是首次——检查 personas 是否变化
    const currentPersonas = cacheManager.get<Persona[]>(CACHE_DOMAINS.PERSONAS) ?? [];
    // 仅当 initialData 和当前缓存不同引用时才更新
    if (initialData.personas !== currentPersonas) {
      personasUpdater.set(initialData.personas);
      // ✅ 如果当前 activePersonaId 不在新的 personas 中，重置为第一个
      if (initialData.personas.length > 0) {
        const currentActiveId = cacheManager.get<string>(CACHE_DOMAINS.ACTIVE_PERSONA_ID) ?? '';
        const currentPersonaExists = initialData.personas.find(p => p.id === currentActiveId);
        if (!currentPersonaExists) {
          activeIdUpdater.set(initialData.personas[0].id);
        }
      } else {
        // 如果没有 Personas，清空 activePersonaId
        activeIdUpdater.set('');
      }
    }
  }, [initialData?.personas, personasUpdater, activeIdUpdater]);

  // ✅ 保存到后端（后端会自动处理时间戳）
  const saveToBackend = useCallback(async (newPersonas: Persona[]) => {
    try {
      await db.savePersonas(newPersonas);
    } catch (error) {
      throw error;
    }
  }, []);

  const createPersona = useCallback(async (persona: Omit<Persona, 'id'>) => {
    const newPersona = { ...persona, id: uuidv4() };
    const currentPersonas = cacheManager.get<Persona[]>(CACHE_DOMAINS.PERSONAS) ?? [];
    const updated = [...currentPersonas, newPersona];
    personasUpdater.set(updated);
    try {
      await saveToBackend(updated);
    } catch (error) {
      // 回滚状态
      personasUpdater.set(currentPersonas);
      throw error;
    }
    return newPersona;
  }, [personasUpdater, saveToBackend]);

  const updatePersona = useCallback(async (id: string, updates: Partial<Persona>) => {
    const currentPersonas = cacheManager.get<Persona[]>(CACHE_DOMAINS.PERSONAS) ?? [];
    const updated = currentPersonas.map(p => p.id === id ? { ...p, ...updates } : p);
    personasUpdater.set(updated);
    try {
      await saveToBackend(updated);
    } catch (error) {
      // 回滚状态
      personasUpdater.set(currentPersonas);
      throw error;
    }
  }, [personasUpdater, saveToBackend]);

  const deletePersona = useCallback(async (id: string) => {
    const currentPersonas = cacheManager.get<Persona[]>(CACHE_DOMAINS.PERSONAS) ?? [];
    // Prevent deleting the last one
    if (currentPersonas.length <= 1) return;
    
    const updated = currentPersonas.filter(p => p.id !== id);
    personasUpdater.set(updated);
    
    try {
      await saveToBackend(updated);
      
      const currentActiveId = cacheManager.get<string>(CACHE_DOMAINS.ACTIVE_PERSONA_ID) ?? '';
      if (currentActiveId === id) {
        activeIdUpdater.set(updated[0].id);
      }
    } catch (error) {
      // 回滚状态
      personasUpdater.set(currentPersonas);
      throw error;
    }
  }, [personasUpdater, activeIdUpdater, saveToBackend]);

  const setActivePersonaId = useCallback((id: string) => {
    activeIdUpdater.set(id);
  }, [activeIdUpdater]);

  const refreshPersonas = useCallback(async () => {
    try {
      // 刷新功能：重新从后端获取最新的 Personas 数据（不删除、不重置）
      const refreshedPersonas = await db.getPersonas();
      // 更新缓存
      personasUpdater.set(refreshedPersonas);
      // 如果当前激活的 Persona 不在新列表中，选择第一个
      if (refreshedPersonas.length > 0) {
        const currentActiveId = cacheManager.get<string>(CACHE_DOMAINS.ACTIVE_PERSONA_ID) ?? '';
        const currentPersonaExists = refreshedPersonas.find(p => p.id === currentActiveId);
        if (!currentPersonaExists) {
          activeIdUpdater.set(refreshedPersonas[0].id);
        }
      }
    } catch (error) {
      throw error;
    }
  }, [personasUpdater, activeIdUpdater]);

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
