import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ClipboardList, XCircle, RotateCcw, CheckCircle, Clock, Play, AlertCircle, Trash2 } from 'lucide-react';
import { jobApi } from '../services/api';
import type { JobStatus } from '../types';

const statusIcons: Record<JobStatus, typeof Clock> = {
  pending: Clock,
  running: Play,
  completed: CheckCircle,
  failed: AlertCircle,
  cancelled: XCircle,
};

const statusColors: Record<JobStatus, string> = {
  pending: 'text-gray-500',
  running: 'text-blue-500',
  completed: 'text-green-500',
  failed: 'text-red-500',
  cancelled: 'text-gray-400',
};

export default function Jobs() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<JobStatus | ''>('');

  const { data: jobs, isLoading } = useQuery({
    queryKey: ['jobs', statusFilter],
    queryFn: () => jobApi.list({ status_filter: statusFilter || undefined }),
    refetchInterval: 5000, // Auto-refresh every 5 seconds
  });

  const cancelMutation = useMutation({
    mutationFn: jobApi.cancel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  const retryMutation = useMutation({
    mutationFn: jobApi.retry,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: jobApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Deployment Jobs</h1>

      {/* Filters */}
      <div className="card p-4 mb-6">
        <label className="block text-sm font-medium mb-2">Filter by Status</label>
        <select
          className="input max-w-xs"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as JobStatus | '')}
        >
          <option value="">All</option>
          <option value="pending">Pending</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {/* Jobs List */}
      {isLoading ? (
        <div className="text-center py-8">Loading jobs...</div>
      ) : jobs?.items.length === 0 ? (
        <div className="card p-8 text-center text-gray-500">
          <ClipboardList className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p>No deployment jobs found</p>
          <p className="text-sm mt-2">
            Jobs are created when you deploy configurations to MikroTik routers
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {jobs?.items.map((job) => {
            const StatusIcon = statusIcons[job.status];
            return (
              <div key={job.id} className="card p-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <StatusIcon className={`w-5 h-5 mt-1 ${statusColors[job.status]}`} />
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium capitalize">
                          {job.job_type.replace('-', ' ')}
                        </span>
                        <span
                          className={`badge ${
                            job.status === 'completed'
                              ? 'badge-success'
                              : job.status === 'failed'
                              ? 'badge-danger'
                              : job.status === 'running'
                              ? 'badge-info'
                              : 'badge-warning'
                          }`}
                        >
                          {job.status}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500 mt-1">
                        Peer: {job.peer_id.substring(0, 8)}...
                      </p>
                      {job.error_message && (
                        <p className="text-sm text-red-600 mt-2">{job.error_message}</p>
                      )}
                    </div>
                  </div>

                  <div className="text-right">
                    <p className="text-sm text-gray-500">
                      Created: {new Date(job.created_at).toLocaleString()}
                    </p>
                    {job.completed_at && (
                      <p className="text-sm text-gray-500">
                        Completed: {new Date(job.completed_at).toLocaleString()}
                      </p>
                    )}
                  </div>
                </div>

                {/* Progress bar for running jobs */}
                {job.status === 'running' && (
                  <div className="mt-4">
                    <div className="flex justify-between text-sm mb-1">
                      <span>Progress</span>
                      <span>{job.progress_percent}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-500 h-2 rounded-full transition-all"
                        style={{ width: `${job.progress_percent}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2 mt-4">
                  {(job.status === 'pending' || job.status === 'running') && (
                    <button
                      onClick={() => cancelMutation.mutate(job.id)}
                      className="btn btn-secondary text-sm flex items-center gap-1"
                      disabled={cancelMutation.isPending}
                    >
                      <XCircle className="w-4 h-4" />
                      Cancel
                    </button>
                  )}
                  {job.status === 'failed' && (
                    <button
                      onClick={() => retryMutation.mutate(job.id)}
                      className="btn btn-primary text-sm flex items-center gap-1"
                      disabled={retryMutation.isPending}
                    >
                      <RotateCcw className="w-4 h-4" />
                      Retry
                    </button>
                  )}
                  {job.status !== 'running' && job.status !== 'pending' && (
                    <button
                      onClick={() => {
                        if (confirm('Delete this job?')) {
                          deleteMutation.mutate(job.id);
                        }
                      }}
                      className="btn btn-secondary text-sm flex items-center gap-1"
                      disabled={deleteMutation.isPending}
                    >
                      <Trash2 className="w-4 h-4" />
                      Delete
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
