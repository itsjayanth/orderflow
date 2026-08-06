import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError } from '@/shared/api/client'

import { useRegister } from './useAuth'

const registerSchema = z.object({
  business_name: z.string().min(1, 'Required'),
  owner_name: z.string().min(1, 'Required'),
  owner_contact: z.string().email('Enter a valid email'),
  password: z.string().min(8, 'At least 8 characters'),
})

type RegisterForm = z.infer<typeof registerSchema>

export function RegisterPage() {
  const navigate = useNavigate()
  const registerMerchant = useRegister()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterForm>({ resolver: zodResolver(registerSchema) })

  const onSubmit = (data: RegisterForm) => {
    registerMerchant.mutate(data, { onSuccess: () => navigate('/', { replace: true }) })
  }

  return (
    <div className="flex min-h-svh items-center justify-center px-4">
      <form onSubmit={handleSubmit(onSubmit)} className="w-full max-w-sm space-y-4">
        <div className="space-y-1 text-center">
          <h1 className="text-xl font-semibold">Register your restaurant</h1>
          <p className="text-muted-foreground text-sm">Creates your merchant account</p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="business_name">Business name</Label>
          <Input id="business_name" {...register('business_name')} />
          {errors.business_name && (
            <p className="text-destructive text-sm">{errors.business_name.message}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="owner_name">Your name</Label>
          <Input id="owner_name" {...register('owner_name')} />
          {errors.owner_name && (
            <p className="text-destructive text-sm">{errors.owner_name.message}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="owner_contact">Email</Label>
          <Input
            id="owner_contact"
            type="email"
            autoComplete="username"
            {...register('owner_contact')}
          />
          {errors.owner_contact && (
            <p className="text-destructive text-sm">{errors.owner_contact.message}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            {...register('password')}
          />
          {errors.password && <p className="text-destructive text-sm">{errors.password.message}</p>}
        </div>

        {registerMerchant.isError && (
          <p className="text-destructive text-sm">
            {registerMerchant.error instanceof ApiError && registerMerchant.error.status === 409
              ? 'An account with this email already exists.'
              : 'Something went wrong. Please try again.'}
          </p>
        )}

        <Button type="submit" className="w-full" disabled={registerMerchant.isPending}>
          {registerMerchant.isPending ? 'Creating account…' : 'Create account'}
        </Button>

        <p className="text-muted-foreground text-center text-sm">
          Already have an account?{' '}
          <Link to="/login" className="text-foreground underline underline-offset-4">
            Log in
          </Link>
        </p>
      </form>
    </div>
  )
}
