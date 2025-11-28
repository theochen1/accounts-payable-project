'use client';

import { useState } from 'react';
import { useAgentTasks } from '@/hooks/useAgentTasks';
import { AgentTask } from '@/lib/api';

interface AgentResolutionPanelProps {
  invoiceId: number;
}

export default function AgentResolutionPanel({ invoiceId }: AgentResolutionPanelProps) {
  const { tasks, isLoading, triggerResolution, hasActiveTasks } = useAgentTasks(invoiceId);
  const [isTriggering, setIsTriggering] = useState(false);

  const handleTrigger = async () => {
    setIsTriggering(true);
    try {
      await triggerResolution();
    } catch (error: any) {
      alert(`Failed to trigger agent: ${error.message}`);
    } finally {
      setIsTriggering(false);
    }
  };

  if (isLoading && tasks.length === 0) {
    return <div className="loading">Loading agent tasks...</div>;
  }

  const latestTask = tasks[0]; // Most recent task

  if (!latestTask) {
    return (
      <div className="card">
        <div className="card-content">
          <div className="empty-state">
            <div className="empty-icon">🤖</div>
            <h3>No agent resolution attempted</h3>
            <p>Click below to let AI attempt to resolve this exception automatically</p>
            <button
              onClick={handleTrigger}
              disabled={isTriggering}
              className="btn btn-primary"
            >
              {isTriggering ? 'Starting...' : 'Resolve with AI Agent'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="flex-between">
          <h2>🤖 AI Agent Resolution</h2>
          <AgentStatusBadge status={latestTask.status} />
        </div>
      </div>

      <div className="card-content">
        {/* Status indicator */}
        {latestTask.status === 'running' && (
          <div className="status-banner running">
            <div className="spinner"></div>
            <div>
              <p className="status-title">Agent is analyzing...</p>
              <p className="status-subtitle">This usually takes 5-15 seconds</p>
            </div>
          </div>
        )}

        {/* Success with high confidence */}
        {latestTask.status === 'completed' && latestTask.applied && (
          <div className="status-banner success">
            <div className="icon">✓</div>
            <div>
              <p className="status-title">Automatically resolved!</p>
              <p className="status-subtitle">
                Confidence: {latestTask.confidence_score ? (latestTask.confidence_score * 100).toFixed(0) : 'N/A'}%
              </p>
            </div>
          </div>
        )}

        {/* Suggestion (medium confidence) */}
        {latestTask.status === 'completed' && !latestTask.applied && latestTask.confidence_score && latestTask.confidence_score > 0.7 && (
          <div className="status-banner suggestion">
            <div className="icon">💡</div>
            <div>
              <p className="status-title">Agent suggests a resolution</p>
              <p className="status-subtitle">
                Confidence: {(latestTask.confidence_score * 100).toFixed(0)}%
              </p>
            </div>
          </div>
        )}

        {/* Error state */}
        {latestTask.status === 'failed' && (
          <div className="status-banner error">
            <div className="icon">✗</div>
            <div>
              <p className="status-title">Agent resolution failed</p>
              <p className="status-subtitle">{latestTask.error_message || 'Unknown error'}</p>
            </div>
          </div>
        )}

        {/* Escalated state */}
        {latestTask.status === 'escalated' && (
          <div className="status-banner escalated">
            <div className="icon">⚠</div>
            <div>
              <p className="status-title">Requires human review</p>
              <p className="status-subtitle">Agent could not automatically resolve this exception</p>
            </div>
          </div>
        )}

        {/* Reasoning */}
        {latestTask.reasoning && (
          <div className="reasoning-section">
            <h4>Agent Reasoning</h4>
            <div className="reasoning-text">{latestTask.reasoning}</div>
          </div>
        )}

        {/* Resolution preview */}
        {latestTask.output_data?.resolution_data && (
          <div className="resolution-preview">
            <h4>Proposed Resolution</h4>
            <ResolutionPreview data={latestTask.output_data.resolution_data} />
          </div>
        )}

        {/* Tools used */}
        {latestTask.output_data?.tools_used && latestTask.output_data.tools_used.length > 0 && (
          <div className="tools-section">
            <h4>Tools Used</h4>
            <div className="tools-list">
              {latestTask.output_data.tools_used.map((tool: any, idx: number) => (
                <span key={idx} className="tool-badge">{tool.tool}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="card-footer">
        {latestTask.status === 'completed' && !latestTask.applied && latestTask.confidence_score && latestTask.confidence_score > 0.7 && (
          <>
            <button className="btn btn-primary">
              ✓ Approve & Apply
            </button>
            <button className="btn btn-secondary">
              Modify
            </button>
            <button className="btn btn-ghost">
              Reject
            </button>
          </>
        )}

        {latestTask.status === 'failed' && (
          <button onClick={handleTrigger} className="btn btn-outline">
            Retry
          </button>
        )}

        {!hasActiveTasks && (
          <button onClick={handleTrigger} className="btn btn-outline btn-sm">
            Run Again
          </button>
        )}
      </div>

      <style jsx>{`
        .card {
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 12px;
          overflow: hidden;
        }

        .card-header {
          padding: 16px 20px;
          border-bottom: 1px solid #e5e7eb;
        }

        .card-header h2 {
          margin: 0;
          font-size: 18px;
          color: #1f2937;
        }

        .flex-between {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .card-content {
          padding: 20px;
        }

        .card-footer {
          padding: 16px 20px;
          border-top: 1px solid #e5e7eb;
          display: flex;
          gap: 8px;
        }

        .loading {
          padding: 40px;
          text-align: center;
          color: #6b7280;
        }

        .empty-state {
          text-align: center;
          padding: 40px 20px;
        }

        .empty-icon {
          font-size: 48px;
          margin-bottom: 16px;
        }

        .empty-state h3 {
          margin: 0 0 8px 0;
          font-size: 18px;
          color: #1f2937;
        }

        .empty-state p {
          margin: 0 0 20px 0;
          color: #6b7280;
        }

        .status-banner {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 16px;
          border-radius: 8px;
          margin-bottom: 20px;
        }

        .status-banner.running {
          background: #eff6ff;
          border: 1px solid #3b82f6;
        }

        .status-banner.success {
          background: #f0fdf4;
          border: 1px solid #22c55e;
        }

        .status-banner.suggestion {
          background: #fffbeb;
          border: 1px solid #f59e0b;
        }

        .status-banner.error {
          background: #fef2f2;
          border: 1px solid #ef4444;
        }

        .status-banner.escalated {
          background: #fef3c7;
          border: 1px solid #f59e0b;
        }

        .spinner {
          width: 24px;
          height: 24px;
          border: 3px solid #e5e7eb;
          border-top-color: #3b82f6;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .icon {
          font-size: 24px;
          line-height: 1;
        }

        .status-title {
          margin: 0;
          font-weight: 500;
          font-size: 14px;
        }

        .status-subtitle {
          margin: 4px 0 0 0;
          font-size: 13px;
          opacity: 0.8;
        }

        .reasoning-section,
        .resolution-preview,
        .tools-section {
          margin-top: 20px;
        }

        .reasoning-section h4,
        .resolution-preview h4,
        .tools-section h4 {
          margin: 0 0 8px 0;
          font-size: 14px;
          font-weight: 500;
          color: #374151;
        }

        .reasoning-text {
          background: #f9fafb;
          padding: 12px;
          border-radius: 6px;
          font-size: 13px;
          color: #6b7280;
          line-height: 1.6;
          white-space: pre-wrap;
        }

        .resolution-preview {
          background: #f9fafb;
          padding: 12px;
          border-radius: 6px;
        }

        .tools-list {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }

        .tool-badge {
          display: inline-block;
          padding: 4px 8px;
          background: #e5e7eb;
          border-radius: 4px;
          font-size: 12px;
          color: #374151;
        }

        .btn {
          padding: 10px 20px;
          border: none;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
        }

        .btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .btn-primary {
          background: #3b82f6;
          color: white;
        }

        .btn-primary:hover:not(:disabled) {
          background: #2563eb;
        }

        .btn-secondary {
          background: #f3f4f6;
          color: #374151;
        }

        .btn-secondary:hover:not(:disabled) {
          background: #e5e7eb;
        }

        .btn-ghost {
          background: transparent;
          color: #6b7280;
        }

        .btn-ghost:hover:not(:disabled) {
          background: #f9fafb;
        }

        .btn-outline {
          background: transparent;
          border: 1px solid #d1d5db;
          color: #374151;
        }

        .btn-outline:hover:not(:disabled) {
          background: #f9fafb;
        }

        .btn-sm {
          padding: 6px 12px;
          font-size: 12px;
        }
      `}</style>
    </div>
  );
}

function AgentStatusBadge({ status }: { status: string }) {
  const config: Record<string, { bg: string; color: string; label: string }> = {
    pending: { bg: '#fef3c7', color: '#92400e', label: 'Pending' },
    running: { bg: '#dbeafe', color: '#1e40af', label: 'Running' },
    completed: { bg: '#dcfce7', color: '#166534', label: 'Completed' },
    failed: { bg: '#fee2e2', color: '#991b1b', label: 'Failed' },
    escalated: { bg: '#fef3c7', color: '#92400e', label: 'Escalated' },
  };

  const { bg, color, label } = config[status] || { bg: '#f3f4f6', color: '#6b7280', label: status };

  return (
    <span className="badge" style={{ background: bg, color: color }}>
      {label}
    </span>
  );
}

function ResolutionPreview({ data }: { data: any }) {
  if (data.new_vendor_name) {
    return (
      <div className="preview-item">
        <p className="preview-label">Proposed Vendor Update</p>
        <div className="preview-change">
          <span className="old-value">{data.old_vendor_name}</span>
          <span>→</span>
          <span className="new-value">{data.new_vendor_name}</span>
        </div>
        {data.match_confidence && (
          <p className="preview-note">
            Match confidence: {(data.match_confidence * 100).toFixed(0)}%
          </p>
        )}
      </div>
    );
  }

  if (data.variance_percent !== undefined) {
    return (
      <div className="preview-item">
        <p className="preview-label">Price Variance Approval</p>
        <p className="preview-text">{data.reason}</p>
      </div>
    );
  }

  return <pre style={{ fontSize: '12px' }}>{JSON.stringify(data, null, 2)}</pre>;
}

