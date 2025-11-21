import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Copy,
  Download,
  RefreshCw,
  Play,
  TestTube,
  Wifi,
  WifiOff,
  Plus,
  Trash2,
  KeyRound,
  ShieldQuestion,
  BadgeCheck,
  Globe2,
  Link2,
} from 'lucide-react';
import { peerApi } from '../services/api';
import { serviceApi } from '../services/api';

export default function PeerDetail() {
  const { peerId } = useParams<{ peerId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [configType, setConfigType] = useState<'wireguard' | 'mikrotik-script'>('wireguard');
  const [showConfig, setShowConfig] = useState(false);
  const [newSubnet, setNewSubnet] = useState('');
  const [showCredentialsModal, setShowCredentialsModal] = useState(false);
  const [credentialsForm, setCredentialsForm] = useState({
    mikrotik_management_ip: '',
    mikrotik_api_port: 8728,
    mikrotik_use_ssl: false,
    mikrotik_verify_cert: false,
    mikrotik_auto_deploy: false,
    mikrotik_username: '',
    mikrotik_password: '',
  });
  const [preflightResult, setPreflightResult] = useState<{
    success: boolean;
    issues: { type: string; description: string; suggestions?: string[] }[];
  } | null>(null);
  const [verifyResult, setVerifyResult] = useState<{
    in_sync: boolean;
    issues: string[];
  } | null>(null);
  const [subnetServiceOnly, setSubnetServiceOnly] = useState(false);
  const [routeAllTraffic, setRouteAllTraffic] = useState(false);
  const [serviceForm, setServiceForm] = useState({
    name: '',
    description: '',
    local_ip: '',
    local_port: 80,
    shared_port: '',
    protocol: 'tcp' as 'tcp' | 'udp' | 'both',
    all_ports: false,
    autoDeploy: false,
  });

  const { data: peer, isLoading } = useQuery({
    queryKey: ['peer', peerId],
    queryFn: () => peerApi.get(peerId!),
    enabled: !!peerId,
  });

  const { data: config } = useQuery({
    queryKey: ['peer-config', peerId, configType],
    queryFn: () => peerApi.getConfig(peerId!, configType),
    enabled: !!peerId && showConfig,
  });

  const testConnectionMutation = useMutation({
    mutationFn: () => peerApi.testMikrotikConnection(peerId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['peer', peerId] });
    },
  });

  const [deployPlan, setDeployPlan] = useState<any>(null);
  const deployMutation = useMutation({
    mutationFn: (approve: boolean) => peerApi.deployToMikrotik(peerId!, approve),
    onSuccess: (data) => {
      if (data?.plan && !data.job_id) {
        setDeployPlan(data.plan);
      } else {
        queryClient.invalidateQueries({ queryKey: ['peer', peerId] });
        setDeployPlan(null);
      }
    },
  });

  const preflightMutation = useMutation({
    mutationFn: () => peerApi.preflightMikrotik(peerId!),
    onSuccess: (data) => {
      setPreflightResult(data);
    },
  });

  const verifyMutation = useMutation({
    mutationFn: () => peerApi.verifyMikrotik(peerId!),
    onSuccess: (data) => {
      setVerifyResult(data);
    },
  });

  const revertMutation = useMutation({
    mutationFn: () => peerApi.revertMikrotik(peerId!),
  });

  const clearMutation = useMutation({
    mutationFn: () => peerApi.clearMikrotik(peerId!),
  });


  const { data: services } = useQuery({
    queryKey: ['services', peer?.wan_id, peerId],
    queryFn: () => serviceApi.list(peer!.wan_id, { peer_id: peerId! }),
    enabled: !!peer?.wan_id && !!peerId,
  });

  const createServiceMutation = useMutation({
    mutationFn: () =>
      serviceApi.create(peerId!, {
        name: serviceForm.name,
        description: serviceForm.description || undefined,
        local_ip: serviceForm.local_ip,
        local_port: serviceForm.all_ports ? 0 : serviceForm.local_port,
        shared_port: serviceForm.all_ports
          ? undefined
          : serviceForm.shared_port
          ? parseInt(serviceForm.shared_port, 10)
          : undefined,
        protocol: serviceForm.protocol,
        auto_deploy: serviceForm.autoDeploy,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services', peer?.wan_id, peerId] });
      queryClient.invalidateQueries({ queryKey: ['peer-config', peerId] });
      setServiceForm({
        name: '',
        description: '',
        local_ip: '',
        local_port: 80,
        shared_port: '',
        protocol: 'tcp',
        all_ports: false,
        autoDeploy: false,
      });
    },
  });

  const deleteServiceMutation = useMutation({
    mutationFn: (serviceId: string) => serviceApi.delete(serviceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services', peer?.wan_id, peerId] });
    },
  });

  const regenerateKeysMutation = useMutation({
    mutationFn: () => peerApi.regenerateKeys(peerId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['peer', peerId] });
    },
  });

  const addSubnetMutation = useMutation({
    mutationFn: (payload: { cidr: string; is_routed: boolean }) =>
      peerApi.addSubnet(peerId!, payload.cidr, payload.is_routed),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['peer', peerId] });
      setNewSubnet('');
      setSubnetServiceOnly(false);
    },
  });

  const deleteSubnetMutation = useMutation({
    mutationFn: (subnetId: string) => peerApi.deleteSubnet(peerId!, subnetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['peer', peerId] });
    },
  });

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const deletePeerMutation = useMutation({
    mutationFn: () => peerApi.delete(peerId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['peers', peer?.wan_id] });
      queryClient.invalidateQueries({ queryKey: ['topology', peer?.wan_id] });
      queryClient.invalidateQueries({ queryKey: ['wan', peer?.wan_id] });
      navigate(peer?.wan_id ? `/wan/${peer.wan_id}` : '/wan');
    },
  });

  const updateCredentialsMutation = useMutation({
    mutationFn: (payload: Partial<typeof credentialsForm> & { mikrotik_auth_method?: 'password' }) =>
      peerApi.update(peerId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['peer', peerId] });
      setShowCredentialsModal(false);
      setCredentialsForm((prev) => ({ ...prev, mikrotik_password: '' }));
    },
  });

  useEffect(() => {
    if (peer && showCredentialsModal) {
      setCredentialsForm({
        mikrotik_management_ip: peer.mikrotik_management_ip || '',
        mikrotik_api_port: peer.mikrotik_api_port || (peer.mikrotik_use_ssl ? 8729 : 8728),
        mikrotik_use_ssl: peer.mikrotik_use_ssl,
        mikrotik_verify_cert: peer.mikrotik_verify_cert,
        mikrotik_auto_deploy: peer.mikrotik_auto_deploy,
        mikrotik_username: peer.mikrotik_username || '',
        mikrotik_password: '',
      });
    }
    if (peer) {
      const meta = (peer.peer_metadata as Record<string, unknown>) || {};
      setRouteAllTraffic(Boolean(meta.route_all_traffic));
    }
  }, [peer, showCredentialsModal]);

  const handleSaveCredentials = (e: React.FormEvent) => {
    e.preventDefault();
    const payload: Partial<typeof credentialsForm> & { mikrotik_auth_method?: 'password' } = {
      mikrotik_management_ip: credentialsForm.mikrotik_management_ip || undefined,
      mikrotik_api_port: credentialsForm.mikrotik_api_port || (credentialsForm.mikrotik_use_ssl ? 8729 : 8728),
      mikrotik_use_ssl: credentialsForm.mikrotik_use_ssl,
      mikrotik_verify_cert: credentialsForm.mikrotik_verify_cert,
      mikrotik_auto_deploy: credentialsForm.mikrotik_auto_deploy,
    };

    if (credentialsForm.mikrotik_username) {
      payload.mikrotik_username = credentialsForm.mikrotik_username;
      payload.mikrotik_auth_method = 'password';
    }
    if (credentialsForm.mikrotik_password) {
      payload.mikrotik_password = credentialsForm.mikrotik_password;
    }

    updateCredentialsMutation.mutate(payload);
  };

  const downloadConfig = () => {
    if (!config) return;
    const blob = new Blob([config.config_text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${peer?.name || 'peer'}.${configType === 'wireguard' ? 'conf' : 'rsc'}`;
    a.click();
  };

  if (isLoading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  if (!peer) {
    return <div className="text-center py-8">Peer not found</div>;
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-6 flex-wrap justify-between">
        <div className="flex items-center gap-4">
          <Link
            to={`/wan/${peer.wan_id}`}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">{peer.name}</h1>
              {peer.is_online ? (
                <span className="badge badge-success flex items-center gap-1">
                  <Wifi className="w-3 h-3" /> Online
                </span>
              ) : (
                <span className="badge badge-danger flex items-center gap-1">
                  <WifiOff className="w-3 h-3" /> Offline
                </span>
              )}
            </div>
            <p className="text-gray-500 capitalize">{peer.type.replace('-', ' ')}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {peer.type === 'mikrotik' && (
            <button
              onClick={() => setShowCredentialsModal(true)}
              className="btn btn-secondary flex items-center gap-2"
            >
              <KeyRound className="w-4 h-4" />
              Change credentials
            </button>
          )}
          <button
            onClick={() => {
              if (confirm('Delete this peer? This cannot be undone.')) {
                deletePeerMutation.mutate();
              }
            }}
            className="btn btn-secondary flex items-center gap-2 text-red-600 border-red-200 hover:border-red-300"
            disabled={deletePeerMutation.isPending}
          >
            <Trash2 className="w-4 h-4" />
            {deletePeerMutation.isPending ? 'Deleting...' : 'Delete peer'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Info */}
        <div className="lg:col-span-2 space-y-6">
          {/* WireGuard Info */}
          <div className="card">
            <div className="p-4 border-b border-gray-200">
              <h2 className="font-semibold">WireGuard Configuration</h2>
            </div>
            <div className="p-4 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Tunnel IP</p>
                  <p className="font-mono">{peer.tunnel_ip}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Listen Port</p>
                  <p className="font-mono">{peer.listen_port || 51820}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Endpoint</p>
                  <p className="font-mono">{peer.endpoint || 'Not set'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Keepalive</p>
                  <p>{peer.persistent_keepalive || 25}s</p>
                </div>
              </div>

              <div>
                <p className="text-sm text-gray-500 mb-1">Public Key</p>
                <div className="flex items-center gap-2">
                  <code className="bg-gray-100 px-2 py-1 rounded text-sm flex-1 overflow-hidden text-ellipsis">
                    {peer.public_key}
                  </code>
                  <button
                    onClick={() => copyToClipboard(peer.public_key || '')}
                    className="p-1 hover:bg-gray-100 rounded"
                  >
                    <Copy className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => regenerateKeysMutation.mutate()}
                  className="btn btn-secondary flex items-center gap-2"
                  disabled={regenerateKeysMutation.isPending}
                >
                  <RefreshCw className={`w-4 h-4 ${regenerateKeysMutation.isPending ? 'animate-spin' : ''}`} />
                  Regenerate Keys
                </button>
                <button
                  onClick={() => setShowConfig(true)}
                  className="btn btn-primary flex items-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  Get Config
                </button>
              </div>
            </div>
          </div>

          {/* MikroTik Info */}
          {peer.type === 'mikrotik' && (
            <div className="card">
              <div className="p-4 border-b border-gray-200">
                <h2 className="font-semibold">MikroTik API</h2>
              </div>
              <div className="p-4 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-500">Management IP</p>
                    <p className="font-mono">{peer.mikrotik_management_ip || 'Not set'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">API Status</p>
                    <span
                      className={`badge ${
                        peer.mikrotik_api_status === 'connected'
                          ? 'badge-success'
                          : peer.mikrotik_api_status === 'unreachable'
                          ? 'badge-danger'
                          : 'badge-warning'
                      }`}
                    >
                      {peer.mikrotik_api_status || 'Unknown'}
                    </span>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Router Identity</p>
                    <p>{peer.mikrotik_router_identity || '-'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">RouterOS Version</p>
                    <p>{peer.mikrotik_routeros_version || '-'}</p>
                  </div>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => testConnectionMutation.mutate()}
                    className="btn btn-secondary flex items-center gap-2"
                    disabled={testConnectionMutation.isPending}
                  >
                        <TestTube className={`w-4 h-4 ${testConnectionMutation.isPending ? 'animate-pulse' : ''}`} />
                        Test Connection
                      </button>
                      <button
                        onClick={() => preflightMutation.mutate()}
                        className="btn btn-secondary flex items-center gap-2"
                        disabled={preflightMutation.isPending}
                      >
                        <ShieldQuestion className={`w-4 h-4 ${preflightMutation.isPending ? 'animate-pulse' : ''}`} />
                        Pre-deploy check
                      </button>
                      <button
                        onClick={() => {
                          if (deployPlan) {
                            deployMutation.mutate(true);
                          } else {
                            deployMutation.mutate(false);
                          }
                        }}
                        className="btn btn-primary flex items-center gap-2"
                        disabled={deployMutation.isPending}
                      >
                        <Play className={`w-4 h-4 ${deployMutation.isPending ? 'animate-pulse' : ''}`} />
                        {deployPlan ? 'Approve & Deploy' : 'Deploy Config'}
                      </button>
                </div>

                {testConnectionMutation.data && (
                  <div
                    className={`p-3 rounded-lg ${
                      testConnectionMutation.data.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
                    }`}
                  >
                    {testConnectionMutation.data.success ? (
                      `Connected! Router: ${testConnectionMutation.data.router_identity}, Version: ${testConnectionMutation.data.routeros_version}`
                    ) : (
                      <div>
                        <p className="font-medium mb-2">Connection failed: {testConnectionMutation.data.error_message}</p>
                        <details className="mt-2">
                          <summary className="cursor-pointer text-sm font-medium hover:underline">
                            Troubleshooting Guide
                          </summary>
                          <div className="mt-2 text-sm space-y-2 bg-red-100 p-3 rounded">
                            <p className="font-medium">Check these requirements:</p>
                            <ol className="list-decimal list-inside space-y-1 ml-2">
                              <li>
                                <strong>Enable API service</strong> - The RouterOS API must be enabled
                                <code className="block bg-white/50 px-2 py-1 rounded mt-1 text-xs">/ip service enable api</code>
                                <span className="block text-xs mt-1">Or for SSL (port 8729): <code>/ip service enable api-ssl</code></span>
                              </li>
                              <li>
                                <strong>Check service status</strong>:
                                <code className="block bg-white/50 px-2 py-1 rounded mt-1 text-xs">/ip service print</code>
                              </li>
                              <li>
                                <strong>Verify credentials</strong> - Ensure username/password are correct
                                <code className="block bg-white/50 px-2 py-1 rounded mt-1 text-xs">/user print</code>
                              </li>
                              <li>
                                <strong>Check firewall</strong> - Allow API port from WireWAN server
                                <code className="block bg-white/50 px-2 py-1 rounded mt-1 text-xs">/ip firewall filter print where dst-port=8728</code>
                              </li>
                              <li>
                                <strong>RouterOS version</strong> - WireGuard requires RouterOS 7.x
                                <code className="block bg-white/50 px-2 py-1 rounded mt-1 text-xs">/system resource print</code>
                              </li>
                            </ol>
                            <p className="mt-2 text-xs">
                              Default ports: API = 8728, API-SSL = 8729. Make sure the port matches your configuration.
                            </p>
                          </div>
                        </details>
                      </div>
                    )}
                  </div>
                )}

                {deployMutation.data && deployMutation.data.job_id && (
                  <div className="p-3 rounded-lg bg-blue-50 text-blue-800">
                    Deployment job created: {deployMutation.data.job_id}
                  </div>
                )}

                {deployPlan && (
                  <div className="p-3 rounded-lg bg-amber-50 text-amber-800 space-y-2">
                    <p className="font-medium">Approval required. Planned changes:</p>
                    <ul className="text-sm list-disc ml-4 space-y-1">
                      <li>IPs: create {deployPlan.summary.ips.to_create}, delete {deployPlan.summary.ips.to_delete}</li>
                      <li>Routes: create {deployPlan.summary.routes.to_create}, delete {deployPlan.summary.routes.to_delete}</li>
                      <li>Firewall: create {deployPlan.summary.firewall.to_create}, delete {deployPlan.summary.firewall.to_delete}</li>
                      <li>NAT: create {deployPlan.summary.nat.to_create}, delete {deployPlan.summary.nat.to_delete}</li>
                      <li>Peers: create {deployPlan.summary.peers.to_create}, delete {deployPlan.summary.peers.to_delete}</li>
                    </ul>
                    <p className="text-xs">Click “Approve & Deploy” to execute, or rerun to refresh plan.</p>
                  </div>
                )}

                {preflightResult && (
                  <div className="p-3 rounded-lg mt-2 border border-amber-200 bg-amber-50">
                    {preflightResult.success ? (
                      <div className="flex items-center gap-2 text-amber-800">
                        <BadgeCheck className="w-4 h-4" />
                        No blocking issues detected. You can deploy safely.
                      </div>
                    ) : (
                      <div>
                        <p className="font-medium text-amber-800">Potential conflicts detected:</p>
                        <ul className="list-disc ml-5 text-sm text-amber-800 mt-2 space-y-1">
                          {preflightResult.issues.map((issue, idx) => (
                            <li key={idx}>
                              <span className="font-semibold capitalize">{issue.type}:</span> {issue.description}
                              {issue.suggestions && issue.suggestions.length > 0 && (
                                <ul className="list-disc ml-5 mt-1">
                                  {issue.suggestions.map((s, i) => (
                                    <li key={i} className="text-xs">{s}</li>
                                  ))}
                                </ul>
                              )}
                            </li>
                          ))}
                        </ul>
                        <p className="text-xs text-amber-700 mt-2">Resolve manually or adjust settings, then deploy.</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Local Subnets */}
          <div className="card">
            <div className="p-4 border-b border-gray-200 flex justify-between items-center">
              <h2 className="font-semibold">Local Subnets</h2>
            </div>
            <div className="p-4">
              <div className="flex gap-2 mb-4">
                <input
                  type="text"
                  className="input flex-1"
                  value={newSubnet}
                  onChange={(e) => setNewSubnet(e.target.value)}
                  placeholder="192.168.1.0/24"
                />
                <label className="flex items-center gap-2 text-sm text-gray-600">
                  <input
                    type="checkbox"
                    className="w-4 h-4"
                    checked={subnetServiceOnly}
                    onChange={(e) => setSubnetServiceOnly(e.target.checked)}
                  />
                  Service-only (do not route)
                </label>
                <button
                  onClick={() =>
                    addSubnetMutation.mutate({
                      cidr: newSubnet,
                      is_routed: !subnetServiceOnly,
                    })
                  }
                  className="btn btn-primary flex items-center gap-2"
                  disabled={!newSubnet || addSubnetMutation.isPending}
                >
                  <Plus className="w-4 h-4" />
                  Add
                </button>
              </div>

              {peer.local_subnets.length === 0 ? (
                <p className="text-gray-500 text-center py-4">No local subnets configured</p>
              ) : (
                <div className="space-y-2">
                  {peer.local_subnets.map((subnet) => (
                    <div
                      key={subnet.id}
                      className="flex items-center justify-between bg-gray-50 px-3 py-2 rounded-lg"
                    >
                      <div>
                        <code className="font-mono">{subnet.cidr}</code>
                        <div className="flex gap-2 mt-1">
                          {subnet.is_routed && <span className="badge badge-info">Routed</span>}
                          {!subnet.is_routed && <span className="badge badge-warning">Service-only</span>}
                          {subnet.nat_enabled && (
                            <span className="badge badge-warning">
                              NAT: {subnet.nat_translated_cidr}
                            </span>
                          )}
                        </div>
                      </div>
                      <button
                        onClick={() => deleteSubnetMutation.mutate(subnet.id)}
                        className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Published Services */}
          <div className="card p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">Publish a Service</h3>
              <Globe2 className="w-4 h-4 text-gray-400" />
            </div>
            <p className="text-sm text-gray-500">
              Expose a local IP:port from this peer to the shared services subnet (WAN shared range).
            </p>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">Service name</label>
                <input
                  className="input"
                  value={serviceForm.name}
                  onChange={(e) => setServiceForm({ ...serviceForm, name: e.target.value })}
                  placeholder="e.g., Office Router UI"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Description (optional)</label>
                <input
                  className="input"
                  value={serviceForm.description}
                  onChange={(e) => setServiceForm({ ...serviceForm, description: e.target.value })}
                  placeholder="What is this service?"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">Local IP</label>
                  <input
                    className="input"
                    value={serviceForm.local_ip}
                    onChange={(e) => setServiceForm({ ...serviceForm, local_ip: e.target.value })}
                    placeholder="192.168.95.1"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Local port</label>
                  <input
                    type="number"
                    className="input"
                    value={serviceForm.local_port}
                    onChange={(e) =>
                      setServiceForm({ ...serviceForm, local_port: parseInt(e.target.value, 10) || 0 })
                    }
                    placeholder="80"
                    disabled={serviceForm.all_ports}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Shared port <span className="text-gray-400">(optional)</span>
                  </label>
                  <input
                    type="number"
                    className="input"
                    value={serviceForm.shared_port}
                    onChange={(e) => setServiceForm({ ...serviceForm, shared_port: e.target.value })}
                    placeholder="Defaults to local port"
                    disabled={serviceForm.all_ports}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Protocol</label>
                  <select
                    className="input"
                    value={serviceForm.protocol}
                    onChange={(e) => setServiceForm({ ...serviceForm, protocol: e.target.value as any })}
                  >
                    <option value="tcp">TCP</option>
                    <option value="udp">UDP</option>
                    <option value="both">Both</option>
                  </select>
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  className="w-4 h-4"
                  checked={serviceForm.all_ports}
                  onChange={(e) => setServiceForm({ ...serviceForm, all_ports: e.target.checked })}
                />
                Expose all ports on this IP
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  className="w-4 h-4"
                  checked={serviceForm.autoDeploy}
                  onChange={(e) => setServiceForm({ ...serviceForm, autoDeploy: e.target.checked })}
                />
                Auto-deploy to MikroTik peers now (shows approvals)
              </label>
              <button
                onClick={() => createServiceMutation.mutate()}
                className="btn btn-primary w-full flex items-center gap-2 justify-center"
                disabled={
                  createServiceMutation.isPending ||
                  !serviceForm.name ||
                  !serviceForm.local_ip ||
                  (!serviceForm.all_ports && !serviceForm.local_port)
                }
              >
                <Link2 className="w-4 h-4" />
                {createServiceMutation.isPending ? 'Publishing...' : 'Publish Service'}
              </button>
            </div>
            {services && services.items.length > 0 && (
              <div className="pt-3 border-t">
                <h4 className="font-semibold text-sm mb-2">Existing services</h4>
                <div className="space-y-2">
                  {services.items.map((svc) => (
                    <div key={svc.id} className="p-2 border rounded flex items-center justify-between text-sm">
                      <div>
                        <p className="font-medium">{svc.name}</p>
                        <p className="font-mono text-xs text-gray-600">
                          {svc.shared_ip}
                          {svc.shared_port ? `:${svc.shared_port}` : ''}
                          {' \u2192 '}
                          {svc.local_ip}
                          {svc.local_port ? `:${svc.local_port}` : ' (all ports)'} ({svc.protocol})
                        </p>
                        {svc.hostname && (
                          <p className="text-xs text-gray-500">DNS: {svc.hostname}</p>
                        )}
                      </div>
                      <button
                        onClick={() => {
                          if (confirm('Delete this published service?')) {
                            deleteServiceMutation.mutate(svc.id);
                          }
                        }}
                        className="p-1 text-gray-400 hover:text-red-500"
                        disabled={deleteServiceMutation.isPending}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

            <div className="card p-4">
              <h3 className="font-semibold mb-3">Quick Info</h3>
              <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Type</dt>
                <dd className="capitalize">{peer.type.replace('-', ' ')}</dd>
              </div>
              {peer.type === 'client' && (
                <div className="flex items-center justify-between">
                  <dt className="text-gray-500">Route all traffic</dt>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      className="w-4 h-4"
                      checked={routeAllTraffic}
                      onChange={(e) => {
                        setRouteAllTraffic(e.target.checked);
                        updateMetadataMutation.mutate({ peer_metadata: { route_all_traffic: e.target.checked } });
                      }}
                    />
                    <span className="text-sm">Enable</span>
                  </label>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-gray-500">Created</dt>
                <dd>{new Date(peer.created_at).toLocaleDateString()}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Updated</dt>
                <dd>{new Date(peer.updated_at).toLocaleDateString()}</dd>
              </div>
              {peer.last_seen && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Last Seen</dt>
                  <dd>{new Date(peer.last_seen).toLocaleString()}</dd>
                </div>
              )}
              {peer.peer_metadata?.needs_config_refresh && (
                <div className="p-2 bg-amber-50 border border-amber-200 rounded text-amber-800 text-xs mt-2">
                  This peer needs a config refresh after recent changes.
                </div>
              )}
            </dl>
          </div>

          {peer.type === 'mikrotik' && (
            <div className="card p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">Deployment Status</h3>
                <div className="flex gap-2">
                  <button
                    onClick={() => verifyMutation.mutate()}
                    className="btn btn-secondary btn-sm flex items-center gap-1"
                    disabled={verifyMutation.isPending}
                  >
                    <BadgeCheck className={`w-4 h-4 ${verifyMutation.isPending ? 'animate-pulse' : ''}`} />
                    Verify
                  </button>
                  <button
                    onClick={() => {
                      if (confirm('Revert to last stored MikroTik config?')) {
                        revertMutation.mutate();
                      }
                    }}
                    className="btn btn-secondary btn-sm"
                    disabled={revertMutation.isPending}
                  >
                    Revert
                  </button>
                  <button
                    onClick={() => {
                      if (confirm('Clear all WireWAN-managed config from this router?')) {
                        clearMutation.mutate();
                      }
                    }}
                    className="btn btn-secondary btn-sm text-red-600"
                    disabled={clearMutation.isPending}
                  >
                    Clear
                  </button>
                </div>
              </div>
              {verifyResult ? (
                verifyResult.in_sync ? (
                  <p className="text-sm text-green-700 bg-green-50 border border-green-200 rounded p-2">
                    Router state matches desired WireWAN config.
                  </p>
                ) : (
                  <div className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded p-2 space-y-2">
                    <p className="font-medium">Out of sync:</p>
                    <ul className="list-disc ml-4 space-y-1">
                      {verifyResult.issues.map((issue, idx) => (
                        <li key={idx}>{issue}</li>
                      ))}
                    </ul>
                    <p className="text-xs">Review these items and redeploy to reconcile.</p>
                  </div>
                )
              ) : (
                <p className="text-sm text-gray-500">Run verification to check deployed state.</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Config Modal */}
      {showConfig && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl p-6 w-full max-w-3xl max-h-[90vh] overflow-auto">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Configuration</h2>
              <div className="flex gap-2">
                <select
                  className="input"
                  value={configType}
                  onChange={(e) => setConfigType(e.target.value as any)}
                >
                  <option value="wireguard">WireGuard Config</option>
                  <option value="mikrotik-script">MikroTik Script</option>
                </select>
              </div>
            </div>

            <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-auto text-sm font-mono">
              {config?.config_text || 'Loading...'}
            </pre>

            <div className="flex gap-2 mt-4">
              <button
                onClick={() => copyToClipboard(config?.config_text || '')}
                className="btn btn-secondary flex items-center gap-2"
              >
                <Copy className="w-4 h-4" />
                Copy
              </button>
              <button onClick={downloadConfig} className="btn btn-secondary flex items-center gap-2">
                <Download className="w-4 h-4" />
                Download
              </button>
              <button onClick={() => setShowConfig(false)} className="btn btn-primary ml-auto">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Credentials Modal */}
      {showCredentialsModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl p-6 w-full max-w-xl max-h-[90vh] overflow-auto">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="text-xl font-bold">Update MikroTik credentials</h2>
                <p className="text-sm text-gray-500">Refresh API access details without recreating the peer.</p>
              </div>
              <button onClick={() => setShowCredentialsModal(false)} className="text-gray-500 hover:text-gray-700">
                Close
              </button>
            </div>

            <form onSubmit={handleSaveCredentials} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Management IP / Hostname</label>
                <input
                  type="text"
                  className="input"
                  value={credentialsForm.mikrotik_management_ip}
                  onChange={(e) =>
                    setCredentialsForm((prev) => ({ ...prev, mikrotik_management_ip: e.target.value }))
                  }
                  placeholder="192.168.88.1 or router.local"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">API Port</label>
                  <input
                    type="number"
                    className="input"
                    value={credentialsForm.mikrotik_api_port}
                    onChange={(e) =>
                      setCredentialsForm((prev) => ({
                        ...prev,
                        mikrotik_api_port: parseInt(e.target.value) || (prev.mikrotik_use_ssl ? 8729 : 8728),
                      }))
                    }
                    placeholder="8728"
                  />
                </div>
                <div className="flex items-end pb-1">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      className="w-4 h-4"
                      checked={credentialsForm.mikrotik_use_ssl}
                      onChange={(e) =>
                        setCredentialsForm((prev) => ({
                          ...prev,
                          mikrotik_use_ssl: e.target.checked,
                          mikrotik_api_port: e.target.checked ? 8729 : 8728,
                        }))
                      }
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
                    value={credentialsForm.mikrotik_username}
                    onChange={(e) =>
                      setCredentialsForm((prev) => ({ ...prev, mikrotik_username: e.target.value }))
                    }
                    placeholder="admin"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">API Password</label>
                  <input
                    type="password"
                    className="input"
                    value={credentialsForm.mikrotik_password}
                    onChange={(e) =>
                      setCredentialsForm((prev) => ({ ...prev, mikrotik_password: e.target.value }))
                    }
                    placeholder="••••••••"
                  />
                  <p className="text-xs text-gray-500 mt-1">Leave blank to keep the existing password.</p>
                </div>
              </div>

              <div className="flex flex-col gap-3">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    className="w-4 h-4"
                    checked={credentialsForm.mikrotik_verify_cert}
                    onChange={(e) =>
                      setCredentialsForm((prev) => ({ ...prev, mikrotik_verify_cert: e.target.checked }))
                    }
                  />
                  <span className="text-sm">Verify TLS certificate</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    className="w-4 h-4"
                    checked={credentialsForm.mikrotik_auto_deploy}
                    onChange={(e) =>
                      setCredentialsForm((prev) => ({ ...prev, mikrotik_auto_deploy: e.target.checked }))
                    }
                  />
                  <span className="text-sm">Auto-deploy configuration changes</span>
                </label>
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  className="btn btn-secondary flex-1"
                  onClick={() => setShowCredentialsModal(false)}
                  disabled={updateCredentialsMutation.isPending}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary flex-1"
                  disabled={updateCredentialsMutation.isPending}
                >
                  {updateCredentialsMutation.isPending ? 'Saving...' : 'Save credentials'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
