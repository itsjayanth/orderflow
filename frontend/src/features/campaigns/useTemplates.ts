import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { MessageTemplateOut, TemplateButton } from '@/shared/api/types'

export const templatesQueryKey = ['campaigns', 'templates'] as const

export function useTemplates() {
  return useQuery({
    queryKey: templatesQueryKey,
    queryFn: () => apiFetch<MessageTemplateOut[]>('/api/v1/campaigns/templates'),
  })
}

interface CreateTemplateInput {
  name: string
  category: string
  language_code?: string
  header_type: string
  header_text?: string
  header_image_base64?: string
  header_image_content_type?: string
  body_text: string
  footer_text?: string
  buttons: TemplateButton[]
}

export function useCreateTemplate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateTemplateInput) =>
      apiFetch<MessageTemplateOut>('/api/v1/campaigns/templates', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: templatesQueryKey })
    },
  })
}

export function useDeleteTemplate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (templateId: string) =>
      apiFetch<void>(`/api/v1/campaigns/templates/${templateId}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: templatesQueryKey })
    },
  })
}
