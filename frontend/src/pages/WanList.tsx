import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Network, Plus, Trash2 } from 'lucide-react';
import { wanApi } from '../services/api';
import type { TopologyType } from '../types';

export default function WanList() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    tunnel_ip_range: '10.0.0.0/24',
    shared_services_range: '10.0.5.0/24',
    topology_type: 'mesh' as TopologyType,
  });

  const { data: wans, isLoading } = useQuery({
    queryKey: ['wans'],
    queryFn: wanApi.list,
  });

  const createMutation = useMutation({
    mutationFn: wanApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wans'] });
      setShowCreate(false);
      setFormData({
        name: '',
        description: '',
        tunnel_ip_range: '10.0.0.0/24',
        shared_services_range: '10.0.5.0/24',
        topology_type: 'mesh',
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: wanApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wans'] });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(formData);
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">WAN Networks</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="btn btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Create WAN
        </button>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md">
            <h2 className="text-xl font-bold mb-4">Create WAN Network</h2>
            <form onSubmit={handleSubmit}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Name</label>
                  <input
                    type="text"
                    className="input"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Description</label>
                  <textarea
                    className="input"
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    rows={2}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Tunnel IP Range</label>
                  <input
                    type="text"
                    className="input"
                    value={formData.tunnel_ip_range}
                    onChange={(e) => setFormData({ ...formData, tunnel_ip_range: e.target.value })}
                    placeholder="10.0.0.0/24"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Shared Services Range</label>
                  <input
                    type="text"
                    className="input"
                    value={formData.shared_services_range}
                    onChange={(e) => setFormData({ ...formData, shared_services_range: e.target.value })}
                    placeholder="10.0.5.0/24"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Topology</label>
                  <select
                    className="input"
                    value={formData.topology_type}
                    onChange={(e) => setFormData({ ...formData, topology_type: e.target.value as TopologyType })}
                  >
                    <option value="mesh">Mesh</option>
                    <option value="hub-spoke">Hub and Spoke</option>
                    <option value="hybrid">Hybrid</option>
                  </select>
                </div>
              </div>
              <div className="flex gap-2 mt-6">
                <button type="button" className="btn btn-secondary flex-1" onClick={() => setShowCreate(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary flex-1" disabled={createMutation.isPending}>
                  {createMutation.isPending ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* WAN List */}
      {isLoading ? (
        <div className="text-center py-8">Loading...</div>
      ) : wans?.items.length === 0 ? (
        <div className="card p-8 text-center text-gray-500">
          <Network className="w-16 h-16 mx-auto mb-4 opacity-50" />
          <p className="text-lg mb-2">No WAN networks yet</p>
          <p className="mb-4">Create your first WAN network to get started</p>
          <button onClick={() => setShowCreate(true)} className="btn btn-primary">
            Create WAN Network
          </button>
        </div>
      ) : (
        <div className="grid gap-4">
          {wans?.items.map((wan) => (
            <div key={wan.id} className="card p-4">
              <div className="flex items-start justify-between">
                <Link to={`/wan/${wan.id}`} className="flex items-start gap-4 flex-1">
                  <div className="p-2 bg-primary-100 rounded-lg">
                    <Network className="w-6 h-6 text-primary-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-lg">{wan.name}</h3>
                    {wan.description && (
                      <p className="text-gray-500 text-sm mt-1">{wan.description}</p>
                    )}
                    <div className="flex gap-4 mt-2 text-sm text-gray-500">
                      <span>Topology: {wan.topology_type}</span>
                      <span>Tunnel: {wan.tunnel_ip_range}</span>
                      <span>Services: {wan.shared_services_range}</span>
                    </div>
                  </div>
                </Link>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <p className="text-2xl font-bold">{wan.peer_count}</p>
                    <p className="text-sm text-gray-500">peers</p>
                  </div>
                  <button
                    onClick={() => {
                      if (confirm('Are you sure you want to delete this WAN network?')) {
                        deleteMutation.mutate(wan.id);
                      }
                    }}
                    className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
