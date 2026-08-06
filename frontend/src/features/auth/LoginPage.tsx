import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError } from '@/shared/api/client'

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
    login.mutate(data, { onSuccess: () => navigate('/', { replace: true }) })
  }

  return (
    <div className="flex min-h-svh items-center justify-center px-4">
      <form onSubmit={handleSubmit(onSubmit)} className="w-full max-w-sm space-y-4">
        <div className="space-y-1 text-center">
          <h1 className="text-xl font-semibold">Log in to Orderflow</h1>
          <p className="text-muted-foreground text-sm">Merchant dashboard access</p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="email_or_phone">Email or phone</Label>
          <Input id="email_or_phone" autoComplete="username" {...register('email_or_phone')} />
          {errors.email_or_phone && (
            <p className="text-destructive text-sm">{errors.email_or_phone.message}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            {...register('password')}
          />
          {errors.password && <p className="text-destructive text-sm">{errors.password.message}</p>}
        </div>

        {login.isError && (
          <p className="text-destructive text-sm">
            {login.error instanceof ApiError && login.error.status === 401
              ? 'Invalid email/phone or password.'
              : 'Something went wrong. Please try again.'}
          </p>
        )}

        <Button type="submit" className="w-full" disabled={login.isPending}>
          {login.isPending ? 'Logging in…' : 'Log in'}
        </Button>

        <p className="text-muted-foreground text-center text-sm">
          No account yet?{' '}
          <Link to="/register" className="text-foreground underline underline-offset-4">
            Register your restaurant
          </Link>
        </p>
      </form>
    </div>
  )
}
