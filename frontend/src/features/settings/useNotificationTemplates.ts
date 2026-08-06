import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/shared/api/client'
import type { NotificationKind, NotificationTemplateOut } from '@/shared/api/types'

const QUERY_KEY = ['settings', 'notification-templates']

export function useNotificationTemplates() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => apiFetch<NotificationTemplateOut[]>('/api/v1/notifications/templates'),
  })
}

interface UpdateNotificationTemplateInput {
  notification_kind: NotificationKind
  template_name: string
  language_code: string
  body: string
  is_active: boolean
}

export function useUpdateNotificationTemplate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ notification_kind, ...body }: UpdateNotificationTemplateInput) =>
      apiFetch<NotificationTemplateOut>(`/api/v1/notifications/templates/${notification_kind}`, {
        method: 'PUT',
        body: JSON.stringify(body),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  })
}
