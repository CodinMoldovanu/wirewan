import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Share2, Server, ArrowRightCircle } from 'lucide-react';
import { wanApi, serviceApi } from '../services/api';

export default function Services() {
  const [selectedWan, setSelectedWan] = useState<string>('');

  const { data: wans } = useQuery({
    queryKey: ['wans'],
    queryFn: wanApi.list,
  });

  const { data: services, isLoading } = useQuery({
    queryKey: ['services', selectedWan],
    queryFn: () => serviceApi.list(selectedWan),
    enabled: !!selectedWan,
  });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Published Services</h1>

      {/* WAN Selector */}
      <div className="card p-4 mb-6">
        <label className="block text-sm font-medium mb-2">Select WAN Network</label>
        <select
          className="input max-w-md"
          value={selectedWan}
          onChange={(e) => setSelectedWan(e.target.value)}
        >
          <option value="">Choose a network...</option>
          {wans?.items.map((wan) => (
            <option key={wan.id} value={wan.id}>
              {wan.name} ({wan.shared_services_range})
            </option>
          ))}
        </select>
      </div>

      {/* Services List */}
      {!selectedWan ? (
        <div className="card p-8 text-center text-gray-500">
          <Share2 className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p>Select a WAN network to view its published services</p>
        </div>
      ) : isLoading ? (
        <div className="text-center py-8">Loading services...</div>
      ) : services?.items.length === 0 ? (
        <div className="card p-8 text-center text-gray-500">
          <Server className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p>No services published in this network</p>
          <p className="text-sm mt-2">
            Go to a peer's detail page to publish a service
          </p>
        </div>
      ) : (
        <div className="grid gap-4">
          {services?.items.map((service) => (
            <div key={service.id} className="card p-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-lg">{service.name}</h3>
                  {service.description && (
                    <p className="text-gray-500 text-sm mt-1">{service.description}</p>
                  )}
                </div>
                <span
                  className={`badge ${service.is_active ? 'badge-success' : 'badge-danger'}`}
                >
                  {service.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
                <div>
                  <p className="text-sm text-gray-500">Shared Address</p>
                  <p className="font-mono">
                    {service.shared_ip}:{service.shared_port}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Local Address</p>
                  <p className="font-mono">
                    {service.local_ip}:{service.local_port}
                  </p>
                </div>
                {service.hostname && (
                  <div>
                    <p className="text-sm text-gray-500">DNS</p>
                    <p className="font-mono">{service.hostname}</p>
                  </div>
                )}
                <div>
                  <p className="text-sm text-gray-500">Protocol</p>
                  <p className="uppercase">{service.protocol}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Created</p>
                  <p>{new Date(service.created_at).toLocaleDateString()}</p>
                </div>
              </div>

              <div className="mt-4 flex justify-between items-center text-sm">
                <div className="text-gray-500">Peer: {service.peer_id.substring(0, 8)}...</div>
                <Link
                  to={`/peers/${service.peer_id}`}
                  className="btn btn-secondary btn-sm flex items-center gap-1"
                >
                  <ArrowRightCircle className="w-4 h-4" />
                  Go to peer
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
