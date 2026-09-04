import { ChevronLeft, Megaphone, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge, type Tone } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { MessageTemplateOut, TemplateApprovalStatus } from '@/shared/api/types'
import { EmptyState } from '@/shared/components/EmptyState'
import { PageHeader } from '@/shared/components/PageHeader'

import { TemplateForm } from './TemplateForm'
import { useDeleteTemplate, useTemplates } from './useTemplates'

const STATUS_TONE: Record<TemplateApprovalStatus, Tone> = {
  pending: 'amber',
  approved: 'green',
  rejected: 'red',
  paused: 'gray',
  disabled: 'gray',
}

const STATUS_LABEL: Record<TemplateApprovalStatus, string> = {
  pending: 'Pending review',
  approved: 'Approved',
  rejected: 'Rejected',
  paused: 'Paused',
  disabled: 'Disabled',
}

function ApprovalStatusBadge({ template }: { template: MessageTemplateOut }) {
  const badge = (
    <Badge tone={STATUS_TONE[template.meta_approval_status]}>
      {STATUS_LABEL[template.meta_approval_status]}
    </Badge>
  )
  if (template.meta_approval_status !== 'rejected' || !template.meta_rejection_reason) {
    return badge
  }
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span>{badge}</span>
      </TooltipTrigger>
      <TooltipContent>{template.meta_rejection_reason}</TooltipContent>
    </Tooltip>
  )
}

export function TemplatesPage() {
  const { data: templates, isLoading } = useTemplates()
  const deleteTemplate = useDeleteTemplate()

  return (
    <div className="space-y-6">
      <Link
        to="/campaigns"
        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm transition-colors duration-150"
      >
        <ChevronLeft className="size-4" />
        Back to campaigns
      </Link>

      <PageHeader
        title="Templates"
        description="WhatsApp message templates for broadcast campaigns, submitted to Meta for approval."
      />

      <Card className="overflow-hidden py-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading &&
              Array.from({ length: 3 }).map((_, i) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: skeleton placeholders have no stable identity
                <TableRow key={`templates-skeleton-${i}`} className="hover:bg-transparent">
                  <TableCell className="py-2.5">
                    <Skeleton className="h-4 w-32" />
                  </TableCell>
                  <TableCell className="py-2.5">
                    <Skeleton className="h-4 w-20" />
                  </TableCell>
                  <TableCell className="py-2.5">
                    <Skeleton className="h-5 w-24 rounded-full" />
                  </TableCell>
                  <TableCell className="py-2.5" />
                </TableRow>
              ))}

            {!isLoading && templates && templates.length === 0 && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={4}>
                  <EmptyState
                    icon={Megaphone}
                    title="No templates yet. Submit one below to get started."
                  />
                </TableCell>
              </TableRow>
            )}

            {!isLoading &&
              templates?.map((template) => (
                <TableRow key={template.template_id}>
                  <TableCell className="py-2.5 font-medium">{template.name}</TableCell>
                  <TableCell className="text-muted-foreground py-2.5 text-sm capitalize">
                    {template.category.toLowerCase()}
                  </TableCell>
                  <TableCell className="py-2.5">
                    <ApprovalStatusBadge template={template} />
                  </TableCell>
                  <TableCell className="py-2.5">
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="hover:text-destructive"
                      aria-label={`Delete ${template.name}`}
                      disabled={deleteTemplate.isPending}
                      onClick={() => deleteTemplate.mutate(template.template_id)}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </Card>

      <TemplateForm />
    </div>
  )
}
