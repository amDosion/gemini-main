import { useState, useMemo, useCallback } from 'react';
import {
  InteractionsClient,
  CreateInteractionParams,
  Interaction,
  StreamChunk,
} from '../services/InteractionsClient';

/**
 * Hook to interact with the InteractionsClient.
 * 
 * @param baseUrl The base URL of the API.
 * @param apiKey The API key for authentication.
 * @returns An object with methods to interact with the API, along with loading and error states.
 */
export const useInteractions = (baseUrl: string, apiKey: string) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const client = useMemo(() => {
    return new InteractionsClient(baseUrl, apiKey);
  }, [baseUrl, apiKey]);

  const createInteraction = useCallback(
    async (params: CreateInteractionParams): Promise<Interaction | undefined> => {
      setLoading(true);
      setError(null);
      try {
        const interaction = await client.createInteraction(params);
        return interaction;
      } catch (err) {
        setError(err as Error);
        return undefined;
      } finally {
        setLoading(false);
      }
    },
    [client]
  );

  const getInteraction = useCallback(
    async (interactionId: string): Promise<Interaction | undefined> => {
      setLoading(true);
      setError(null);
      try {
        const interaction = await client.getInteraction(interactionId);
        return interaction;
      } catch (err) {
        setError(err as Error);
        return undefined;
      } finally {
        setLoading(false);
      }
    },
    [client]
  );

  const deleteInteraction = useCallback(
    async (interactionId: string): Promise<void> => {
      setLoading(true);
      setError(null);
      try {
        await client.deleteInteraction(interactionId);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    },
    [client]
  );

  const streamInteraction = useCallback(
    (
      interactionId: string,
      onChunk: (chunk: StreamChunk) => void,
      onComplete: () => void
    ): EventSource => {
      setLoading(true);
      setError(null);

      const handleError = (err: Error) => {
        setError(err);
        setLoading(false);
      };
      
      const handleComplete = () => {
        onComplete();
        setLoading(false);
      }

      const eventSource = client.streamInteraction(
        interactionId,
        onChunk,
        handleComplete,
        handleError
      );

      return eventSource;
    },
    [client]
  );

  return {
    createInteraction,
    getInteraction,
    deleteInteraction,
    streamInteraction,
    loading,
    error,
  };
};
