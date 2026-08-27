import { zodResolver } from '@hookform/resolvers/zod'
import { Loader2 } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { OrderflowLogo } from '@/assets/logo'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError } from '@/shared/api/client'

import { PasswordInput } from './PasswordInput'
import { useLogin } from './useAuth'

const loginSchema = z.object({
  email_or_phone: z.string().min(1, 'Required'),
  password: z.string().min(1, 'Required'),
})

type LoginForm = z.infer<typeof loginSchema>

export function LoginPage() {
  const navigate = useNavigate()
  const login = useLogin()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) })

  const onSubmit = (data: LoginForm) => {
    login.mutate(data, { onSuccess: () => navigate('/dashboard', { replace: true }) })
  }

  return (
    <div className="from-background to-secondary/40 flex min-h-svh items-center justify-center bg-gradient-to-b px-4 py-12">
      <div className="w-full max-w-sm space-y-8">
        <div className="flex items-center justify-center gap-2.5">
          <OrderflowLogo className="size-8" />
          <p className="text-primary font-serif text-2xl tracking-tight">Orderflow</p>
        </div>

        <Card className="shadow-lg">
          <CardHeader className="items-center text-center">
            <h1 className="font-serif text-xl font-semibold">Welcome back</h1>
            <p className="text-muted-foreground text-sm">Log in to your merchant dashboard</p>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email_or_phone">Email or phone</Label>
                <Input
                  id="email_or_phone"
                  autoComplete="username"
                  {...register('email_or_phone')}
                />
                {errors.email_or_phone && (
                  <p className="text-destructive text-sm">{errors.email_or_phone.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <PasswordInput
                  id="password"
                  autoComplete="current-password"
                  {...register('password')}
                />
                {errors.password && (
                  <p className="text-destructive text-sm">{errors.password.message}</p>
                )}
              </div>

              {login.isError && (
                <p className="text-destructive text-sm">
                  {login.error instanceof ApiError && login.error.status === 401
                    ? 'Invalid email/phone or password.'
                    : 'Something went wrong. Please try again.'}
                </p>
              )}

              <Button type="submit" className="w-full" size="lg" disabled={login.isPending}>
                {login.isPending && <Loader2 className="animate-spin" />}
                {login.isPending ? 'Logging in…' : 'Log in'}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="text-muted-foreground text-center text-sm">
          No account yet?{' '}
          <Link to="/register" className="text-primary font-medium underline underline-offset-4">
            Register your business
          </Link>
        </p>
      </div>
    </div>
  )
}
