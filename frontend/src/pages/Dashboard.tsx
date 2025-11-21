import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Network, Server, Share2, Activity } from 'lucide-react';
import { wanApi, serviceApi, jobApi } from '../services/api';

export default function Dashboard() {
  const { data: wans } = useQuery({
    queryKey: ['wans'],
    queryFn: wanApi.list,
  });

  const { data: jobs } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobApi.list({ status_filter: 'running' }),
  });

  const totalPeers = wans?.items.reduce((sum, wan) => sum + wan.peer_count, 0) || 0;
  const totalWans = wans?.total || 0;
  const runningJobs = jobs?.total || 0;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary-100 rounded-lg">
              <Network className="w-6 h-6 text-primary-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">WAN Networks</p>
              <p className="text-2xl font-bold">{totalWans}</p>
            </div>
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 rounded-lg">
              <Server className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total Peers</p>
              <p className="text-2xl font-bold">{totalPeers}</p>
            </div>
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-100 rounded-lg">
              <Share2 className="w-6 h-6 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Services</p>
              <p className="text-2xl font-bold">-</p>
            </div>
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-yellow-100 rounded-lg">
              <Activity className="w-6 h-6 text-yellow-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Running Jobs</p>
              <p className="text-2xl font-bold">{runningJobs}</p>
            </div>
          </div>
        </div>
      </div>

      {/* WAN Networks List */}
      <div className="card">
        <div className="p-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-lg font-semibold">WAN Networks</h2>
          <Link to="/wan" className="btn btn-primary text-sm">
            Manage Networks
          </Link>
        </div>

        {wans?.items.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <Network className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p>No WAN networks yet</p>
            <Link to="/wan" className="btn btn-primary mt-4">
              Create your first WAN
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {wans?.items.map((wan) => (
              <Link
                key={wan.id}
                to={`/wan/${wan.id}`}
                className="flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <Network className="w-5 h-5 text-gray-400" />
                  <div>
                    <p className="font-medium">{wan.name}</p>
                    <p className="text-sm text-gray-500">
                      {wan.topology_type} - {wan.tunnel_ip_range}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-medium">{wan.peer_count} peers</p>
                  <p className="text-sm text-gray-500">
                    Services: {wan.shared_services_range}
                  </p>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
