import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listHoldings, getPortfolioSummary, listSips, listFds, createInstrument, createHolding, type InstrumentCreate, type HoldingCreate } from '@/api/investments'
import { useAuthStore } from '@/store/auth'

function enabled() {
  return useAuthStore.getState().isAuthenticated
}

export function useHoldings() {
  return useQuery({
    queryKey: ['investments', 'holdings'],
    queryFn: listHoldings,
    enabled: enabled(),
  })
}

export function usePortfolioSummary() {
  return useQuery({
    queryKey: ['investments', 'summary'],
    queryFn: getPortfolioSummary,
    enabled: enabled(),
  })
}

export function useSips() {
  return useQuery({
    queryKey: ['investments', 'sips'],
    queryFn: listSips,
    enabled: enabled(),
  })
}

export function useFds() {
  return useQuery({
    queryKey: ['investments', 'fds'],
    queryFn: listFds,
    enabled: enabled(),
  })
}

export function useAddHolding() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: InstrumentCreate & Omit<HoldingCreate, 'instrument_id'>) => {
      const { name, type, ticker, currency, ...holdingFields } = payload
      const instrument = await createInstrument({ name, type, ticker, currency })
      return createHolding({ instrument_id: instrument.id, ...holdingFields })
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['investments'] })
    },
  })
}
