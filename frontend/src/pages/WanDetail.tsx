import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Server,
  Plus,
  Wifi,
  WifiOff,
  Settings,
  Router,
  Monitor,
  Globe,
  ArrowLeft,
} from 'lucide-react';
import { wanApi, peerApi } from '../services/api';
import type { PeerType } from '../types';
import NetworkTopology from '../components/NetworkTopology';

const peerTypeIcons: Record<PeerType, typeof Server> = {
  mikrotik: Router,
  'generic-router': Router,
  server: Server,
  client: Monitor,
  hub: Globe,
};

const peerTypeLabels: Record<PeerType, string> = {
  mikrotik: 'MikroTik',
  'generic-router': 'Generic Router',
  server: 'Server',
  client: 'Client',
  hub: 'Hub',
};

export default function WanDetail() {
  const { wanId } = useParams<{ wanId: string }>();
  const queryClient = useQueryClient();
  const [showAddPeer, setShowAddPeer] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    type: 'mikrotik' as PeerType,
    endpoint: '',
    listen_port: 51820,
    local_subnets: [] as { cidr: string; is_routed: boolean }[],
    mikrotik_management_ip: '',
    mikrotik_api_port: 8728,
    mikrotik_use_ssl: false,
    mikrotik_username: '',
    mikrotik_password: '',
    mikrotik_auto_deploy: false,
  });
  const [newSubnet, setNewSubnet] = useState('');
  const [newSubnetServiceOnly, setNewSubnetServiceOnly] = useState(false);

  const { data: wan, isLoading: wanLoading } = useQuery({
    queryKey: ['wan', wanId],
    queryFn: () => wanApi.get(wanId!),
    enabled: !!wanId,
  });

  const { data: peers, isLoading: peersLoading } = useQuery({
    queryKey: ['peers', wanId],
    queryFn: () => peerApi.list(wanId!),
    enabled: !!wanId,
  });

  const { data: topology } = useQuery({
    queryKey: ['topology', wanId],
    queryFn: () => wanApi.getTopology(wanId!),
    enabled: !!wanId,
  });

  const createPeerMutation = useMutation({
    mutationFn: (data: typeof formData) => peerApi.create(wanId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['peers', wanId] });
      queryClient.invalidateQueries({ queryKey: ['topology', wanId] });
      queryClient.invalidateQueries({ queryKey: ['wan', wanId] });
      setShowAddPeer(false);
      resetForm();
    },
  });

  const resetForm = () => {
    setFormData({
      name: '',
      type: 'mikrotik',
      endpoint: '',
      listen_port: 51820,
      local_subnets: [],
      mikrotik_management_ip: '',
      mikrotik_api_port: 8728,
      mikrotik_use_ssl: false,
      mikrotik_username: '',
      mikrotik_password: '',
      mikrotik_auto_deploy: false,
    });
    setNewSubnet('');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Clean up form data - convert empty strings to undefined/null
    const cleanedData: Record<string, unknown> = {
      name: formData.name,
      type: formData.type,
      endpoint: formData.endpoint || undefined,
      listen_port: formData.listen_port || 51820,
      local_subnets: formData.local_subnets.length > 0 ? formData.local_subnets : undefined,
    };

    // Add MikroTik fields only if type is mikrotik and credentials provided
    if (formData.type === 'mikrotik') {
      if (formData.mikrotik_management_ip) {
        cleanedData.mikrotik_management_ip = formData.mikrotik_management_ip;
        cleanedData.mikrotik_api_port = formData.mikrotik_api_port || 8728;
        cleanedData.mikrotik_use_ssl = formData.mikrotik_use_ssl;
      }
      if (formData.mikrotik_username) {
        cleanedData.mikrotik_username = formData.mikrotik_username;
        cleanedData.mikrotik_auth_method = 'password'; // Set auth method when username provided
      }
      if (formData.mikrotik_password) {
        cleanedData.mikrotik_password = formData.mikrotik_password;
      }
      cleanedData.mikrotik_auto_deploy = formData.mikrotik_auto_deploy;
    }

    createPeerMutation.mutate(cleanedData as typeof formData);
  };

  const addSubnet = () => {
    if (newSubnet) {
      setFormData({
        ...formData,
        local_subnets: [...formData.local_subnets, { cidr: newSubnet, is_routed: !newSubnetServiceOnly }],
      });
      setNewSubnet('');
      setNewSubnetServiceOnly(false);
    }
  };

  if (wanLoading || peersLoading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  if (!wan) {
    return <div className="text-center py-8">WAN network not found</div>;
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <Link to="/wan" className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold">{wan.name}</h1>
          <p className="text-gray-500">{wan.description || `${wan.topology_type} topology`}</p>
        </div>
      </div>

      {/* Network Info */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="card p-4">
          <p className="text-sm text-gray-500">Tunnel Network</p>
          <p className="font-mono font-medium">{wan.tunnel_ip_range}</p>
        </div>
        <div className="card p-4">
          <p className="text-sm text-gray-500">Shared Services</p>
          <p className="font-mono font-medium">{wan.shared_services_range}</p>
        </div>
        <div className="card p-4">
          <p className="text-sm text-gray-500">Topology</p>
          <p className="font-medium capitalize">{wan.topology_type.replace('-', ' ')}</p>
        </div>
      </div>

      {/* Topology Visualization */}
      {topology && topology.nodes.length > 0 && (
        <div className="card mb-6">
          <div className="p-4 border-b border-gray-200">
            <h2 className="font-semibold">Network Topology</h2>
          </div>
          <div className="p-4">
            <NetworkTopology topology={topology} />
          </div>
        </div>
      )}

      {/* Peers List */}
      <div className="card">
        <div className="p-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="font-semibold">Peers ({peers?.total || 0})</h2>
          <button
            onClick={() => setShowAddPeer(true)}
            className="btn btn-primary flex items-center gap-2 text-sm"
          >
            <Plus className="w-4 h-4" />
            Add Peer
          </button>
        </div>

        {peers?.items.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <Server className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p>No peers in this network</p>
            <button onClick={() => setShowAddPeer(true)} className="btn btn-primary mt-4">
              Add your first peer
            </button>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {peers?.items.map((peer) => {
              const Icon = peerTypeIcons[peer.type];
              return (
                <Link
                  key={peer.id}
                  to={`/peers/${peer.id}`}
                  className="flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <div className="relative">
                      <Icon className="w-8 h-8 text-gray-400" />
                      {peer.is_online ? (
                        <Wifi className="w-3 h-3 text-green-500 absolute -bottom-1 -right-1" />
                      ) : (
                        <WifiOff className="w-3 h-3 text-gray-400 absolute -bottom-1 -right-1" />
                      )}
                    </div>
                    <div>
                      <p className="font-medium">{peer.name}</p>
                      <div className="flex gap-2 text-sm text-gray-500">
                        <span className="badge badge-info">{peerTypeLabels[peer.type]}</span>
                        {peer.type === 'mikrotik' && peer.mikrotik_api_status && (
                          <span
                            className={`badge ${
                              peer.mikrotik_api_status === 'connected'
                                ? 'badge-success'
                                : peer.mikrotik_api_status === 'unreachable'
                                ? 'badge-danger'
                                : 'badge-warning'
                            }`}
                          >
                            API: {peer.mikrotik_api_status}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-mono">{peer.tunnel_ip}</p>
                    <p className="text-sm text-gray-500">{peer.endpoint || 'No endpoint'}</p>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {/* Add Peer Modal */}
      {showAddPeer && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-auto p-4">
          <div className="bg-white rounded-xl p-6 w-full max-w-xl max-h-[90vh] overflow-auto">
            <h2 className="text-xl font-bold mb-2">Add Peer</h2>
            <p className="text-gray-500 text-sm mb-4">
              Add a new device to this WAN overlay network. The device will receive a tunnel IP and can connect to other peers.
            </p>
            <form onSubmit={handleSubmit}>
              <div className="space-y-5">
                {/* Basic Info */}
                <div>
                  <label className="block text-sm font-medium mb-1">Peer Name *</label>
                  <input
                    type="text"
                    className="input"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g., Office-Router-NYC, Home-Server"
                    required
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    A friendly name to identify this peer. Use something descriptive like location or purpose.
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Device Type *</label>
                  <select
                    className="input"
                    value={formData.type}
                    onChange={(e) => setFormData({ ...formData, type: e.target.value as PeerType })}
                  >
                    <option value="mikrotik">MikroTik Router (auto-configurable via API)</option>
                    <option value="generic-router">Generic Router (manual config)</option>
                    <option value="server">Server / VPS</option>
                    <option value="client">Client Device (laptop, workstation)</option>
                    <option value="hub">Hub Node (central point for hub-spoke)</option>
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    {formData.type === 'mikrotik' && 'MikroTik routers can be automatically configured via REST API (RouterOS 7+).'}
                    {formData.type === 'generic-router' && 'You\'ll receive a WireGuard config to manually apply to this router.'}
                    {formData.type === 'server' && 'Servers typically expose services and have a stable endpoint.'}
                    {formData.type === 'client' && 'Client devices usually connect to other peers but don\'t accept incoming connections.'}
                    {formData.type === 'hub' && 'Hub nodes act as central connection points in hub-spoke topologies.'}
                  </p>
                </div>

                {/* Network Settings */}
                <div className="border-t pt-4">
                  <h3 className="font-medium mb-3">Network Settings</h3>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium mb-1">Public Endpoint</label>
                      <input
                        type="text"
                        className="input"
                        value={formData.endpoint}
                        onChange={(e) => setFormData({ ...formData, endpoint: e.target.value })}
                        placeholder="myrouter.dyndns.org or 203.0.113.50:51820"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        The public IP address or hostname where other peers can reach this device. Port defaults to 51820 if not specified.
                        <br />
                        <strong>Dynamic IP?</strong> Use a Dynamic DNS hostname (e.g., <code>mysite.duckdns.org</code>).
                        <br />
                        <strong>Behind NAT without port forwarding?</strong> Leave empty - this peer will only initiate connections to others.
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium mb-1">
                        Listen Port
                        <span className="text-gray-400 font-normal ml-1">(optional)</span>
                      </label>
                      <input
                        type="number"
                        className="input"
                        value={formData.listen_port || ''}
                        onChange={(e) => setFormData({ ...formData, listen_port: e.target.value ? parseInt(e.target.value) : 51820 })}
                        placeholder="51820"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        The UDP port WireGuard will listen on. Default is 51820. Only change if you have port conflicts or firewall requirements.
                      </p>
                    </div>
                  </div>
                </div>

                {/* MikroTik-specific fields */}
                {formData.type === 'mikrotik' && (
                  <div className="border-t pt-4">
                    <h3 className="font-medium mb-1">MikroTik API Settings</h3>
                    <p className="text-xs text-gray-500 mb-3">
                      Connect to this router's REST API to automatically deploy WireGuard configuration.
                    </p>

                    {/* Prerequisites Alert */}
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4">
                      <p className="text-sm font-medium text-amber-800 mb-2">Prerequisites (run on router):</p>
                      <div className="space-y-2 text-xs text-amber-700">
                        <div>
                          <span className="font-medium">1. Enable API service</span> (port 8728):
                          <code className="block bg-white/50 px-2 py-1 rounded mt-1">/ip service enable api</code>
                        </div>
                        <div>
                          <span className="font-medium">2. Or enable API-SSL</span> (port 8729, more secure):
                          <code className="block bg-white/50 px-2 py-1 rounded mt-1">/ip service enable api-ssl</code>
                        </div>
                        <div>
                          <span className="font-medium">3. Create API user</span> (optional, can use admin):
                          <code className="block bg-white/50 px-2 py-1 rounded mt-1">/user add name=wirewan password=YourPass group=full</code>
                        </div>
                      </div>
                      <p className="text-xs text-amber-600 mt-2">
                        Note: WireGuard requires RouterOS 7.x. Check with: <code>/system resource print</code>
                      </p>
                    </div>
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium mb-1">Management IP / Hostname</label>
                        <input
                          type="text"
                          className="input"
                          value={formData.mikrotik_management_ip}
                          onChange={(e) => setFormData({ ...formData, mikrotik_management_ip: e.target.value })}
                          placeholder="192.168.88.1 or router.local"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          The IP address or hostname to reach this router's API. This can be a local IP if WireWAN runs on the same network.
                        </p>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium mb-1">API Port</label>
                          <input
                            type="number"
                            className="input"
                            value={formData.mikrotik_api_port}
                            onChange={(e) => setFormData({
                              ...formData,
                              mikrotik_api_port: parseInt(e.target.value) || 8728
                            })}
                            placeholder="8728"
                          />
                          <p className="text-xs text-gray-500 mt-1">8728 (API) or 8729 (API-SSL)</p>
                        </div>
                        <div className="flex items-end pb-6">
                          <label className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={formData.mikrotik_use_ssl}
                              onChange={(e) => setFormData({
                                ...formData,
                                mikrotik_use_ssl: e.target.checked,
                                mikrotik_api_port: e.target.checked ? 8729 : 8728
                              })}
                              className="w-4 h-4"
                            />
                            <span className="text-sm">Use SSL (API-SSL)</span>
                          </label>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium mb-1">API Username</label>
                          <input
                            type="text"
                            className="input"
                            value={formData.mikrotik_username}
                            onChange={(e) => setFormData({ ...formData, mikrotik_username: e.target.value })}
                            placeholder="admin"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium mb-1">API Password</label>
                          <input
                            type="password"
                            className="input"
                            value={formData.mikrotik_password}
                            onChange={(e) => setFormData({ ...formData, mikrotik_password: e.target.value })}
                          />
                        </div>
                      </div>
                      <p className="text-xs text-gray-500">
                        Create a dedicated user on the MikroTik with API access. Credentials are encrypted at rest.
                      </p>
                      <label className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg">
                        <input
                          type="checkbox"
                          checked={formData.mikrotik_auto_deploy}
                          onChange={(e) => setFormData({ ...formData, mikrotik_auto_deploy: e.target.checked })}
                          className="w-4 h-4"
                        />
                        <div>
                          <span className="text-sm font-medium">Auto-deploy configuration changes</span>
                          <p className="text-xs text-gray-500">
                            Automatically push config updates when peers are added/removed or settings change.
                          </p>
                        </div>
                      </label>
                    </div>
                  </div>
                )}

                {/* Local Subnets */}
                <div className="border-t pt-4">
                  <h3 className="font-medium mb-1">Local Networks (Subnets)</h3>
                  <p className="text-xs text-gray-500 mb-3">
                    Add the local network(s) behind this peer that should be accessible through the WAN overlay.
                    These are the LAN subnets that other peers will be able to route to.
                    <br />
                    <strong>Examples:</strong> <code>192.168.1.0/24</code> (home network), <code>10.0.10.0/24</code> (office VLAN), <code>172.16.0.0/16</code> (datacenter)
                  </p>
                  <div className="flex gap-2 mb-2">
                    <input
                      type="text"
                      className="input flex-1"
                      value={newSubnet}
                      onChange={(e) => setNewSubnet(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          addSubnet();
                        }
                      }}
                      placeholder="192.168.1.0/24"
                    />
                    <label className="flex items-center gap-1 text-xs text-gray-600">
                      <input
                        type="checkbox"
                        className="w-4 h-4"
                        checked={newSubnetServiceOnly}
                        onChange={(e) => setNewSubnetServiceOnly(e.target.checked)}
                      />
                      Service-only
                    </label>
                    <button type="button" onClick={addSubnet} className="btn btn-secondary">
                      Add
                    </button>
                  </div>
                  {formData.local_subnets.length > 0 ? (
                    <div className="space-y-1">
                      {formData.local_subnets.map((subnet, index) => (
                        <div key={index} className="flex items-center justify-between bg-gray-100 px-3 py-2 rounded">
                          <span className="font-mono text-sm">{subnet.cidr}</span>
                          <div className="flex items-center gap-2">
                            {!subnet.is_routed && <span className="badge badge-warning">Service-only</span>}
                          <button
                            type="button"
                            onClick={() =>
                              setFormData({
                                ...formData,
                                local_subnets: formData.local_subnets.filter((_, i) => i !== index),
                              })
                            }
                            className="text-red-500 text-sm hover:text-red-700"
                          >
                            Remove
                          </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-gray-400 italic">
                      No subnets added. You can add them later from the peer details page.
                    </p>
                  )}
                  <p className="text-xs text-gray-500 mt-2">
                    <strong>Tip:</strong> You can add multiple subnets if this peer has access to several networks.
                    The system will automatically detect conflicts with other peers' subnets.
                  </p>
                </div>
              </div>

              <div className="flex gap-2 mt-6 pt-4 border-t">
                <button type="button" className="btn btn-secondary flex-1" onClick={() => setShowAddPeer(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary flex-1" disabled={createPeerMutation.isPending}>
                  {createPeerMutation.isPending ? 'Adding...' : 'Add Peer'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
