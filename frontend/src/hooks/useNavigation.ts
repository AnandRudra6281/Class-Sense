import { useState, useCallback } from 'react';
import { ViewId } from '../types';

export function useNavigation(initialView: ViewId = 'dashboard') {
  const [currentView, setCurrentView] = useState<ViewId>(initialView);
  const [history, setHistory] = useState<ViewId[]>([initialView]);

  const navigateTo = useCallback((view: ViewId) => {
    setCurrentView(view);
    setHistory((prev) => [...prev, view]);
  }, []);

  const goBack = useCallback(() => {
    setHistory((prev) => {
      if (prev.length <= 1) return prev;
      const newHistory = prev.slice(0, -1);
      setCurrentView(newHistory[newHistory.length - 1]);
      return newHistory;
    });
  }, []);

  return {
    currentView,
    navigateTo,
    goBack,
    canGoBack: history.length > 1,
  };
}
