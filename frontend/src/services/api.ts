import axios from 'axios';
import type {
  WanNetwork,
  Peer,
  PublishedService,
  DeploymentJob,
  Topology,
} from '../types';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// WAN API
export const wanApi = {
  list: async () => {
    const { data } = await api.get<{ items: WanNetwork[]; total: number }>('/wan');
    return data;
  },

  get: async (id: string) => {
    const { data } = await api.get<WanNetwork>(`/wan/${id}`);
    return data;
  },

  create: async (wan: Partial<WanNetwork>) => {
    const { data } = await api.post<WanNetwork>('/wan', wan);
    return data;
  },

  update: async (id: string, wan: Partial<WanNetwork>) => {
    const { data } = await api.put<WanNetwork>(`/wan/${id}`, wan);
    return data;
  },

  delete: async (id: string) => {
    await api.delete(`/wan/${id}`);
  },

  getTopology: async (id: string) => {
    const { data } = await api.get<Topology>(`/wan/${id}/topology`);
    return data;
  },

  getIpInfo: async (id: string) => {
    const { data } = await api.get(`/wan/${id}/ip-info`);
    return data;
  },

  getConflicts: async (id: string) => {
    const { data } = await api.get(`/wan/${id}/conflicts`);
    return data;
  },
};

// Peer API
export const peerApi = {
  list: async (wanId: string) => {
    const { data } = await api.get<{ items: Peer[]; total: number }>(`/peers/wan/${wanId}`);
    return data;
  },

  get: async (id: string) => {
    const { data } = await api.get<Peer>(`/peers/${id}`);
    return data;
  },

  create: async (wanId: string, peer: Partial<Peer> & { local_subnets?: { cidr: string; is_routed: boolean }[] }) => {
    const { data } = await api.post<Peer>(`/peers/wan/${wanId}`, peer);
    return data;
  },

  update: async (id: string, peer: Partial<Peer>) => {
    const { data } = await api.put<Peer>(`/peers/${id}`, peer);
    return data;
  },

  delete: async (id: string) => {
    await api.delete(`/peers/${id}`);
  },

  regenerateKeys: async (id: string) => {
    const { data } = await api.post<Peer>(`/peers/${id}/regenerate-keys`);
    return data;
  },

  getConfig: async (id: string, type: 'wireguard' | 'mikrotik-script' = 'wireguard') => {
    const { data } = await api.get(`/peers/${id}/config`, { params: { config_type: type } });
    return data;
  },

  testMikrotikConnection: async (id: string) => {
    const { data } = await api.post(`/peers/${id}/mikrotik/test-connection`);
    return data;
  },

  deployToMikrotik: async (id: string, approve: boolean = false) => {
    const { data } = await api.post(`/peers/${id}/mikrotik/deploy`, null, {
      params: { approve },
    });
    return data;
  },

  preflightMikrotik: async (id: string) => {
    const { data } = await api.get(`/peers/${id}/mikrotik/preflight`);
    return data as { success: boolean; issues: { type: string; description: string; suggestions?: string[] }[] };
  },

  verifyMikrotik: async (id: string) => {
    const { data } = await api.get(`/peers/${id}/mikrotik/verify`);
    return data as { in_sync: boolean; issues: string[]; current?: Record<string, unknown> };
  },

  checkConflicts: async (id: string) => {
    const { data } = await api.get(`/peers/${id}/check-conflicts`);
    return data;
  },

  addSubnet: async (peerId: string, cidr: string, isRouted: boolean = true) => {
    const { data } = await api.post(`/peers/${peerId}/subnets`, null, {
      params: { cidr, is_routed: isRouted },
    });
    return data;
  },

  deleteSubnet: async (peerId: string, subnetId: string) => {
    await api.delete(`/peers/${peerId}/subnets/${subnetId}`);
  },

  revertMikrotik: async (id: string) => {
    const { data } = await api.post(`/peers/${id}/mikrotik/revert`);
    return data;
  },

  clearMikrotik: async (id: string) => {
    const { data } = await api.post(`/peers/${id}/mikrotik/clear`);
    return data;
  },
};

// Service API
export const serviceApi = {
  list: async (wanId: string, params?: { peer_id?: string; status_filter?: string }) => {
    const { data } = await api.get<{ items: PublishedService[]; total: number }>(`/services/wan/${wanId}`, {
      params,
    });
    return data;
  },

  get: async (id: string) => {
    const { data } = await api.get<PublishedService>(`/services/${id}`);
    return data;
  },

  create: async (peerId: string, service: Partial<PublishedService> & { auto_deploy?: boolean }) => {
    const { data } = await api.post<PublishedService>(`/services/peer/${peerId}`, service, {
      params: service.auto_deploy !== undefined ? { auto_deploy: service.auto_deploy } : undefined,
    });
    return data;
  },

  update: async (id: string, service: Partial<PublishedService>) => {
    const { data } = await api.put<PublishedService>(`/services/${id}`, service);
    return data;
  },

  delete: async (id: string) => {
    await api.delete(`/services/${id}`);
  },
};

// Jobs API
export const jobApi = {
  list: async (params?: { peer_id?: string; status_filter?: string }) => {
    const { data } = await api.get<{ items: DeploymentJob[]; total: number }>('/jobs', { params });
    return data;
  },

  get: async (id: string) => {
    const { data } = await api.get<DeploymentJob>(`/jobs/${id}`);
    return data;
  },

  cancel: async (id: string) => {
    const { data } = await api.post(`/jobs/${id}/cancel`);
    return data;
  },

  retry: async (id: string) => {
    const { data } = await api.post(`/jobs/${id}/retry`);
    return data;
  },

  delete: async (id: string) => {
    await api.delete(`/jobs/${id}`);
  },

  getLogs: async (id: string) => {
    const { data } = await api.get(`/jobs/${id}/logs`);
    return data;
  },
};

// Auth API
export const authApi = {
  login: async (username: string, password: string) => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    const { data } = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    localStorage.setItem('token', data.access_token);
    return data;
  },

  register: async (username: string, email: string, password: string) => {
    const { data } = await api.post('/auth/register', { username, email, password });
    return data;
  },

  me: async () => {
    const { data } = await api.get('/auth/me');
    return data;
  },

  logout: () => {
    localStorage.removeItem('token');
  },
};

export default api;
