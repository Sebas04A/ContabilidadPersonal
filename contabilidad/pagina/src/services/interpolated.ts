import axios from 'axios'

const API_URL = '/api'

/** Quién manda sobre un grupo. Derivado en el backend; `type` solo dice cómo se ejecuta. */
export type OrigenGrupo = 'manual' | 'fondo' | 'inversion' | 'generado'

export interface InterpolationGroup {
    id: string
    name: string
    description?: string
    type?: 'interpolated' | 'fixed'
    origen?: OrigenGrupo
    /** De qué grupo salió, cuando `origen === 'generado'`. */
    fondo_origen?: string | null
}

export interface InterpolatedPayment {
    id: string
    group_id: string
    amount: number
    /** Vacío = «desde siempre». Solo los grupos `fixed` lo admiten. */
    start_date: string | null
    /** Vacío = «para siempre». Solo los grupos `fixed` lo admiten. */
    end_date: string | null
    note?: string
}

export const getGroups = async (
    type: string = 'interpolated',
    origen?: OrigenGrupo,
): Promise<InterpolationGroup[]> => {
    const response = await axios.get(`${API_URL}/payments/groups`, { params: { type, origen } })
    return response.data
}

export const createGroup = async (
    group: Omit<InterpolationGroup, 'id'>
): Promise<InterpolationGroup> => {
    const response = await axios.post(`${API_URL}/payments/groups`, group)
    return response.data
}

export const updateGroup = async (
    id: string,
    group: Partial<InterpolationGroup>
): Promise<InterpolationGroup> => {
    const response = await axios.put(`${API_URL}/payments/groups/${id}`, group)
    return response.data
}

export const deleteGroup = async (id: string): Promise<void> => {
    await axios.delete(`${API_URL}/payments/groups/${id}`)
}

export const getPayments = async (groupId: string): Promise<InterpolatedPayment[]> => {
    const response = await axios.get(`${API_URL}/payments/groups/${groupId}/payments`)
    return response.data
}

export const createPayment = async (
    groupId: string,
    payment: Omit<InterpolatedPayment, 'id' | 'group_id'>
): Promise<InterpolatedPayment> => {
    const response = await axios.post(`${API_URL}/payments/groups/${groupId}/payments`, payment)
    return response.data
}

export const updatePayment = async (
    id: string,
    payment: Partial<InterpolatedPayment>
): Promise<InterpolatedPayment> => {
    const response = await axios.put(`${API_URL}/payments/payments/${id}`, payment)
    return response.data
}

export const deletePayment = async (id: string): Promise<void> => {
    await axios.delete(`${API_URL}/payments/payments/${id}`)
}
