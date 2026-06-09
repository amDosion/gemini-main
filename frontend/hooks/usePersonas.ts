import { useEffect, useCallback, useRef } from 'react';
import { Persona } from '../types/types';
import { v4 as uuidv4 } from 'uuid';
import { db } from '../services/db';
import { cacheManager, CACHE_DOMAINS } from '../services/CacheManager';
import {
  capturePrivateCacheLifecycleSnapshot,
  isPrivateCacheLifecycleSnapshotCurrent,
} from '../services/privateCacheInvalidation';
import { scopedPrivateSingletonCacheKey } from '../services/privateCacheScope';
import { useCacheSubscription, useCacheUpdater } from './useCacheSubscription';
import { usePrivateCacheScopeRevision } from './usePrivateCacheScopeRevision';

const EMPTY_PERSONAS: Persona[] = [];

const getPersonasFingerprint = (personas: Persona[]): string =>
  personas
    .map((persona) =>
      [
        persona.id,
        persona.name,
        persona.description,
        persona.systemPrompt,
        persona.icon,
        persona.category,
      ].join('\u0001')
    )
    .join('\u0002');

const getInitialPersonasSignature = (
  initialData: { personas: Persona[] } | undefined
): string | null => (initialData?.personas ? getPersonasFingerprint(initialData.personas) : null);

export const usePersonas = (initialData?: { personas: Persona[] }) => {
  const initialDataSignature = getInitialPersonasSignature(initialData);
  const latestInitialDataSignatureRef = useRef<string | null>(initialDataSignature);
  const appliedInitialDataSignatureRef = useRef<string | null>(null);
  const suppressedInitialDataSignatureRef = useRef<string | null>(null);
  const personasCacheKey = scopedPrivateSingletonCacheKey(CACHE_DOMAINS.PERSONAS);
  const activePersonaIdCacheKey = scopedPrivateSingletonCacheKey(CACHE_DOMAINS.ACTIVE_PERSONA_ID);

  // ✅ 订阅 CacheManager 中的数据
  const personas = useCacheSubscription<Persona[]>(personasCacheKey, EMPTY_PERSONAS);
  const activePersonaId = useCacheSubscription<string>(activePersonaIdCacheKey, '');
  const { set: setPersonasCache } = useCacheUpdater<Persona[]>(personasCacheKey, EMPTY_PERSONAS);
  const { set: setActivePersonaIdCache } = useCacheUpdater<string>(activePersonaIdCacheKey, '');

  const isPersonaCacheScopeCurrent = useCallback(
    (lifecycleSnapshot?: ReturnType<typeof capturePrivateCacheLifecycleSnapshot>): boolean => {
      const cacheKeysCurrent =
        personasCacheKey === scopedPrivateSingletonCacheKey(CACHE_DOMAINS.PERSONAS) &&
        activePersonaIdCacheKey === scopedPrivateSingletonCacheKey(CACHE_DOMAINS.ACTIVE_PERSONA_ID);
      if (!cacheKeysCurrent) return false;
      return lifecycleSnapshot ? isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot) : true;
    },
    [activePersonaIdCacheKey, personasCacheKey]
  );

  const assertPersonaCacheScopeCurrent = useCallback((): void => {
    if (!isPersonaCacheScopeCurrent()) {
      throw new Error('private cache scope changed');
    }
  }, [isPersonaCacheScopeCurrent]);

  useEffect(() => {
    latestInitialDataSignatureRef.current = initialDataSignature;
  }, [initialDataSignature]);

  usePrivateCacheScopeRevision(() => {
    suppressedInitialDataSignatureRef.current = latestInitialDataSignatureRef.current;
    appliedInitialDataSignatureRef.current = null;
  });

  // ✅ 只接收当前用户 scope 下的新 initialData；scope 切换后同一个旧对象不会被重新灌回
  useEffect(() => {
    if (!initialData?.personas) {
      suppressedInitialDataSignatureRef.current = null;
      appliedInitialDataSignatureRef.current = null;
      return;
    }
    if (!initialDataSignature) return;
    if (suppressedInitialDataSignatureRef.current === initialDataSignature) return;
    if (appliedInitialDataSignatureRef.current === initialDataSignature) return;

    appliedInitialDataSignatureRef.current = initialDataSignature;
    const currentPersonas = cacheManager.get<Persona[]>(personasCacheKey) ?? [];
    // 用内容指纹判断，避免调用方每次 render 传新数组导致重复写缓存。
    if (getPersonasFingerprint(initialData.personas) !== getPersonasFingerprint(currentPersonas)) {
      setPersonasCache(initialData.personas);
    }

    // ✅ 如果当前 activePersonaId 不在新的 personas 中，重置为第一个
    if (initialData.personas.length > 0) {
      const currentActiveId = cacheManager.get<string>(activePersonaIdCacheKey) ?? '';
      const currentPersonaExists = initialData.personas.find((p) => p.id === currentActiveId);
      if (!currentPersonaExists) {
        setActivePersonaIdCache(initialData.personas[0].id);
      }
    } else {
      // 如果没有 Personas，清空 activePersonaId
      setActivePersonaIdCache('');
    }
  }, [
    activePersonaIdCacheKey,
    initialDataSignature,
    initialData?.personas,
    personasCacheKey,
    setActivePersonaIdCache,
    setPersonasCache,
  ]);

  // ✅ 保存到后端（后端会自动处理时间戳）
  const saveToBackend = useCallback(async (newPersonas: Persona[]) => {
    await db.savePersonas(newPersonas);
  }, []);

  const createPersona = useCallback(
    async (persona: Omit<Persona, 'id'>) => {
      const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
      assertPersonaCacheScopeCurrent();
      const newPersona = { ...persona, id: uuidv4() };
      const currentPersonas = cacheManager.get<Persona[]>(personasCacheKey) ?? [];
      const updated = [...currentPersonas, newPersona];
      setPersonasCache(updated);
      try {
        await saveToBackend(updated);
      } catch (error) {
        if (isPersonaCacheScopeCurrent(lifecycleSnapshot)) {
          setPersonasCache(currentPersonas);
        }
        throw error;
      }
      return newPersona;
    },
    [
      assertPersonaCacheScopeCurrent,
      isPersonaCacheScopeCurrent,
      personasCacheKey,
      saveToBackend,
      setPersonasCache,
    ]
  );

  const updatePersona = useCallback(
    async (id: string, updates: Partial<Persona>) => {
      const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
      assertPersonaCacheScopeCurrent();
      const currentPersonas = cacheManager.get<Persona[]>(personasCacheKey) ?? [];
      const updated = currentPersonas.map((p) => (p.id === id ? { ...p, ...updates } : p));
      setPersonasCache(updated);
      try {
        await saveToBackend(updated);
      } catch (error) {
        if (isPersonaCacheScopeCurrent(lifecycleSnapshot)) {
          setPersonasCache(currentPersonas);
        }
        throw error;
      }
    },
    [
      assertPersonaCacheScopeCurrent,
      isPersonaCacheScopeCurrent,
      personasCacheKey,
      saveToBackend,
      setPersonasCache,
    ]
  );

  const deletePersona = useCallback(
    async (id: string) => {
      const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
      assertPersonaCacheScopeCurrent();
      const currentPersonas = cacheManager.get<Persona[]>(personasCacheKey) ?? [];
      // Prevent deleting the last one
      if (currentPersonas.length <= 1) return;

      const updated = currentPersonas.filter((p) => p.id !== id);
      setPersonasCache(updated);

      try {
        await saveToBackend(updated);
        if (!isPersonaCacheScopeCurrent(lifecycleSnapshot)) {
          return;
        }

        const currentActiveId = cacheManager.get<string>(activePersonaIdCacheKey) ?? '';
        if (currentActiveId === id) {
          setActivePersonaIdCache(updated[0].id);
        }
      } catch (error) {
        if (isPersonaCacheScopeCurrent(lifecycleSnapshot)) {
          setPersonasCache(currentPersonas);
        }
        throw error;
      }
    },
    [
      activePersonaIdCacheKey,
      assertPersonaCacheScopeCurrent,
      isPersonaCacheScopeCurrent,
      personasCacheKey,
      saveToBackend,
      setActivePersonaIdCache,
      setPersonasCache,
    ]
  );

  const setActivePersonaId = useCallback(
    (id: string) => {
      assertPersonaCacheScopeCurrent();
      setActivePersonaIdCache(id);
    },
    [assertPersonaCacheScopeCurrent, setActivePersonaIdCache]
  );

  const refreshPersonas = useCallback(async () => {
    const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
    assertPersonaCacheScopeCurrent();
    // 刷新功能：重新从后端获取最新的 Personas 数据（不删除、不重置）
    const refreshedPersonas = await db.getPersonas();
    if (!isPersonaCacheScopeCurrent(lifecycleSnapshot)) {
      return;
    }
    // 更新缓存
    setPersonasCache(refreshedPersonas);
    // 如果当前激活的 Persona 不在新列表中，选择第一个
    if (refreshedPersonas.length > 0) {
      const currentActiveId = cacheManager.get<string>(activePersonaIdCacheKey) ?? '';
      const currentPersonaExists = refreshedPersonas.find((p) => p.id === currentActiveId);
      if (!currentPersonaExists) {
        setActivePersonaIdCache(refreshedPersonas[0].id);
      }
    } else {
      // 刷新后列表为空时清空激活 ID,与 initialData 同步逻辑保持一致,避免 activePersonaId
      // 仍指向已不存在的 persona。
      setActivePersonaIdCache('');
    }
  }, [
    activePersonaIdCacheKey,
    assertPersonaCacheScopeCurrent,
    isPersonaCacheScopeCurrent,
    setActivePersonaIdCache,
    setPersonasCache,
  ]);

  const activePersona = personas.find((p) => p.id === activePersonaId) || personas[0];

  return {
    personas,
    activePersona,
    activePersonaId,
    setActivePersonaId,
    createPersona,
    updatePersona,
    deletePersona,
    refreshPersonas,
  };
};
