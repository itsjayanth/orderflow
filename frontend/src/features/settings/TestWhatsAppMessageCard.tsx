import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

import { useSendTestWhatsAppMessage } from './useWhatsAppSettings'

export function TestWhatsAppMessageCard({ disabled = false }: { disabled?: boolean }) {
  const [testPhone, setTestPhone] = useState('')
  const sendTest = useSendTestWhatsAppMessage()

  const onSend = () => {
    sendTest.mutate(testPhone)
  }

  return (
    <div className="max-w-md space-y-3 border-t pt-4">
      <div>
        <h3 className="text-sm font-medium">Send yourself a test message</h3>
        <p className="text-muted-foreground text-xs">
          Confirm your saved credentials can actually send messages before relying on them.
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="test_phone">Test recipient number</Label>
        <div className="flex items-center gap-3">
          <Input
            id="test_phone"
            placeholder="+919876543210"
            value={testPhone}
            onChange={(e) => setTestPhone(e.target.value)}
            disabled={disabled}
          />
          <Button
            type="button"
            variant="outline"
            disabled={disabled || !testPhone || sendTest.isPending}
            onClick={onSend}
          >
            {sendTest.isPending ? 'Sending…' : 'Send test message'}
          </Button>
        </div>
      </div>
      {disabled && (
        <p className="text-muted-foreground text-xs">
          Save your credentials above before sending a test message.
        </p>
      )}
      {sendTest.isSuccess && sendTest.data.status === 'success' && (
        <p className="text-sm font-medium text-green-700 dark:text-green-400">
          {sendTest.data.message}
        </p>
      )}
      {sendTest.isSuccess && sendTest.data.status === 'failed' && (
        <p className="text-destructive text-sm">{sendTest.data.message}</p>
      )}
      {sendTest.isError && (
        <p className="text-destructive text-sm">Failed to send test message. Please try again.</p>
      )}
    </div>
  )
}
