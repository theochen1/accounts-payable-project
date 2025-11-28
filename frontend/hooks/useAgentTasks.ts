'use client';

import { useState, useEffect } from 'react';
import { agentApi, AgentTask } from '@/lib/api';

export function useAgentTasks(invoiceId: number) {
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const loadTasks = async () => {
    try {
      setIsLoading(true);
      const data = await agentApi.getInvoiceTasks(invoiceId);
      setTasks(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to load agent tasks'));
      console.error('Failed to load agent tasks:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadTasks();
    
    // Poll every 2s if any task is running
    const hasRunning = tasks.some(t => t.status === 'running' || t.status === 'pending');
    let interval: NodeJS.Timeout | null = null;
    
    if (hasRunning) {
      interval = setInterval(() => {
        loadTasks();
      }, 2000);
    }
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [invoiceId]);

  const triggerResolution = async () => {
    try {
      const newTask = await agentApi.resolve(invoiceId);
      await loadTasks(); // Reload to get updated list
      return newTask;
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to trigger agent resolution'));
      throw err;
    }
  };

  const hasActiveTasks = tasks.some(t => ['pending', 'running'].includes(t.status));

  return {
    tasks,
    isLoading,
    error,
    triggerResolution,
    hasActiveTasks,
    refresh: loadTasks,
  };
}

