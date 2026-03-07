import axios from 'axios';

const API_URL = '/api';

export interface InterpolationGroup {
  id: string;
  name: string;
  description?: string;
  type?: 'interpolated' | 'fixed';
}

export interface InterpolatedPayment {
  id: string;
  group_id: string;
  amount: number;
  start_date: string;
  end_date: string;
  note?: string;
}

export const getGroups = async (type: string = 'interpolated'): Promise<InterpolationGroup[]> => {
  const response = await axios.get(`${API_URL}/groups`, { params: { type } });
  return response.data;
};

export const createGroup = async (group: Omit<InterpolationGroup, 'id'>): Promise<InterpolationGroup> => {
  const response = await axios.post(`${API_URL}/groups`, group);
  return response.data;
};

export const updateGroup = async (id: string, group: Partial<InterpolationGroup>): Promise<InterpolationGroup> => {
  const response = await axios.put(`${API_URL}/groups/${id}`, group);
  return response.data;
};

export const deleteGroup = async (id: string): Promise<void> => {
  await axios.delete(`${API_URL}/groups/${id}`);
};

export const getPayments = async (groupId: string): Promise<InterpolatedPayment[]> => {
  const response = await axios.get(`${API_URL}/groups/${groupId}/payments`);
  return response.data;
};

export const createPayment = async (groupId: string, payment: Omit<InterpolatedPayment, 'id' | 'group_id'>): Promise<InterpolatedPayment> => {
  const response = await axios.post(`${API_URL}/groups/${groupId}/payments`, payment);
  return response.data;
};

export const updatePayment = async (id: string, payment: Partial<InterpolatedPayment>): Promise<InterpolatedPayment> => {
  const response = await axios.put(`${API_URL}/payments/${id}`, payment);
  return response.data;
};

export const deletePayment = async (id: string): Promise<void> => {
  await axios.delete(`${API_URL}/payments/${id}`);
};
