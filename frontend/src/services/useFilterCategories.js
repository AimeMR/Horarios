import { useState, useEffect, useCallback } from 'react';
import { fetchFilterCategories, normalizeFilterCategories, DEFAULT_FILTER_DATA } from './filterService';

export function useFilterCategories() {
  const [categories, setCategories] = useState(() => normalizeFilterCategories(DEFAULT_FILTER_DATA));
  const [isLoading, setIsLoading] = useState(true);
  const [isFallback, setIsFallback] = useState(false);
  const [error, setError] = useState(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await fetchFilterCategories();
      setCategories(result.data);
      setIsFallback(result.isFallback);
      setError(result.error);
    } catch (err) {
      setCategories(normalizeFilterCategories(DEFAULT_FILTER_DATA));
      setIsFallback(true);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  return {
    categories,
    isLoading,
    isFallback,
    error,
    reload: loadData
  };
}

