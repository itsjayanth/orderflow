import { FileText, Megaphone } from 'lucide-react'
import { useState } from 'react'
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
import type { AudienceFilter, CampaignStatus } from '@/shared/api/types'
import { EmptyState } from '@/shared/components/EmptyState'
import { PageHeader } from '@/shared/components/PageHeader'

import { CampaignForm } from './CampaignForm'
import { useCampaigns } from './useCampaigns'

const STATUS_TONE: Record<CampaignStatus, Tone> = {
  draft: 'gray',
  scheduled: 'blue',
  sending: 'amber',
  completed: 'green',
  failed: 'red',
}

const STATUS_LABEL: Record<CampaignStatus, string> = {
  draft: 'Draft',
  scheduled: 'Scheduled',
  sending: 'Sending',
  completed: 'Completed',
  failed: 'Failed',
}

export function audienceLabel(filter: AudienceFilter): string {
  if (filter.kind === 'all') return 'All customers'
  if (filter.kind === 'ordered_within_days') return `Ordered in last ${filter.days}d`
  return `No order in last ${filter.days}d`
}

export function CampaignsPage() {
  const { data: campaigns, isLoading } = useCampaigns()
  const [formOpen, setFormOpen] = useState(false)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Campaigns"
        description="Send an approved WhatsApp template to a segment of your customers."
        actions={
          <>
            <Button type="button" variant="outline" asChild>
              <Link to="/campaigns/templates">
                <FileText />
                Templates
              </Link>
            </Button>
            <Button type="button" onClick={() => setFormOpen(true)}>
              <Megaphone />
              New campaign
            </Button>
          </>
        }
      />

      <Card className="overflow-hidden py-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Audience</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading &&
              Array.from({ length: 3 }).map((_, i) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: skeleton placeholders have no stable identity
                <TableRow key={`campaigns-skeleton-${i}`} className="hover:bg-transparent">
                  <TableCell className="py-2.5">
                    <Skeleton className="h-4 w-32" />
                  </TableCell>
                  <TableCell className="py-2.5">
                    <Skeleton className="h-4 w-24" />
                  </TableCell>
                  <TableCell className="py-2.5">
                    <Skeleton className="h-5 w-20 rounded-full" />
                  </TableCell>
                </TableRow>
              ))}

            {!isLoading && campaigns && campaigns.length === 0 && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={3}>
                  <EmptyState
                    icon={Megaphone}
                    title="No campaigns yet. Create one to get started."
                  />
                </TableCell>
              </TableRow>
            )}

            {!isLoading &&
              campaigns?.map((campaign) => (
                <TableRow key={campaign.campaign_id} className="cursor-pointer">
                  <TableCell className="py-2.5 font-medium">
                    <Link to={`/campaigns/${campaign.campaign_id}`} className="hover:underline">
                      {campaign.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground py-2.5 text-sm">
                    {audienceLabel(campaign.audience_filter)}
                  </TableCell>
                  <TableCell className="py-2.5">
                    <Badge tone={STATUS_TONE[campaign.status]}>
                      {STATUS_LABEL[campaign.status]}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </Card>

      <CampaignForm open={formOpen} onOpenChange={setFormOpen} />
    </div>
  )
}
