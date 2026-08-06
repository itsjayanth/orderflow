import {
  Bell,
  ClipboardList,
  CreditCard,
  LayoutDashboard,
  MessageCircle,
  ShoppingCart,
  Smartphone,
  UtensilsCrossed,
} from 'lucide-react'
import type { ComponentType } from 'react'
import { Link } from 'react-router-dom'

import { OrderflowLogo } from '@/assets/logo'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

import { ChatMockup } from './components/ChatMockup'
import { DashboardPreview } from './components/DashboardPreview'

const ORDER_STEPS: {
  icon: ComponentType<{ className?: string }>
  title: string
  description: string
}[] = [
  {
    icon: MessageCircle,
    title: 'Browse',
    description:
      'Customers open a chat and browse your live menu as an interactive catalog — categories, photos, and prices, always up to date.',
  },
  {
    icon: ShoppingCart,
    title: 'Add to cart',
    description:
      'They pick items and quantities right inside WhatsApp — no app to download, no account to create.',
  },
  {
    icon: ClipboardList,
    title: 'Review & confirm',
    description:
      'A clear order summary shows exactly what’s being ordered and the total, before anything is charged.',
  },
  {
    icon: CreditCard,
    title: 'Pay',
    description:
      'A secure payment link lands right in the chat — card details never travel over WhatsApp itself.',
  },
  {
    icon: Bell,
    title: 'Track',
    description:
      'Once payment clears, the customer gets automatic updates — confirmed, preparing, ready for pickup.',
  },
]

const DASHBOARD_FEATURES: {
  icon: ComponentType<{ className?: string }>
  title: string
  description: string
}[] = [
  {
    icon: LayoutDashboard,
    title: 'Live order queue',
    description:
      'New orders appear within seconds of payment, sorted by status — New, Preparing, Ready, Completed.',
  },
  {
    icon: Bell,
    title: 'One-tap status updates',
    description:
      'Move an order forward and Orderflow messages the customer on WhatsApp automatically — no separate notification step.',
  },
  {
    icon: UtensilsCrossed,
    title: 'Menu & catalog control',
    description:
      'Add items, update prices, and mark things out of stock. Changes reflect in the WhatsApp catalog immediately.',
  },
  {
    icon: Smartphone,
    title: 'Works on any device',
    description:
      'No native app to install for staff either — the dashboard is a responsive web app that works on a phone behind the counter.',
  },
]

export function HomePage() {
  return (
    <div className="min-h-svh">
      <header className="border-border/70 bg-background/85 sticky top-0 z-10 border-b backdrop-blur-sm">
        <nav className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <span className="flex shrink-0 items-center gap-2">
            <OrderflowLogo className="size-6" />
            <span className="text-primary font-serif text-lg tracking-tight">Orderflow</span>
          </span>
          <div className="flex shrink-0 items-center gap-2">
            <Button asChild variant="ghost" size="sm">
              <Link to="/login">Log in</Link>
            </Button>
            <Button asChild size="sm">
              <Link to="/register">Get started</Link>
            </Button>
          </div>
        </nav>
      </header>

      <main>
        {/* Hero */}
        <section className="from-background to-secondary/40 bg-gradient-to-b">
          <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-2 lg:py-28">
            <div className="space-y-6 text-center lg:text-left">
              <h1 className="font-serif text-4xl leading-tight font-semibold tracking-tight text-balance sm:text-5xl">
                Take orders where your customers already are — WhatsApp.
              </h1>
              <p className="text-muted-foreground mx-auto max-w-xl text-lg text-balance lg:mx-0">
                Orderflow turns WhatsApp into a full ordering channel for your restaurant: guided
                menu browsing, cart, secure payment links, and live status updates — with every
                order landing in one dashboard your staff already knows how to use.
              </p>
              <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center lg:justify-start">
                <Button asChild size="lg" className="w-full sm:w-auto">
                  <Link to="/register">Register your restaurant</Link>
                </Button>
                <Button asChild variant="outline" size="lg" className="w-full sm:w-auto">
                  <Link to="/login">Log in</Link>
                </Button>
              </div>
              <p className="text-muted-foreground text-sm">
                Built for independent restaurants. No app for customers to install, no POS lock-in —
                Orderflow works alongside the kitchen setup you already have.
              </p>
            </div>

            <ChatMockup />
          </div>
        </section>

        {/* Customer ordering flow */}
        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
          <div className="mx-auto max-w-2xl space-y-3 text-center">
            <h2 className="font-serif text-3xl font-semibold tracking-tight">
              From “hi” to hot food, without leaving the chat
            </h2>
            <p className="text-muted-foreground text-lg">
              Customers already have WhatsApp open. Orderflow guides them through a structured order
              — no free-text chatbot guesswork, no separate app.
            </p>
          </div>

          <ol className="mt-12 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
            {ORDER_STEPS.map((step, index) => (
              <li key={step.title}>
                <Card className="h-full space-y-3 p-5">
                  <div className="flex items-center gap-3">
                    <span className="bg-primary/10 text-primary flex size-9 shrink-0 items-center justify-center rounded-full">
                      <step.icon className="size-4.5" />
                    </span>
                    <span className="text-muted-foreground text-xs font-medium">
                      Step {index + 1}
                    </span>
                  </div>
                  <h3 className="font-serif text-lg font-semibold">{step.title}</h3>
                  <p className="text-muted-foreground text-sm leading-relaxed">
                    {step.description}
                  </p>
                </Card>
              </li>
            ))}
          </ol>
        </section>

        {/* Merchant dashboard */}
        <section className="bg-secondary/30 border-border/70 border-y">
          <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-2 lg:py-24">
            <div className="order-2 space-y-8 lg:order-1">
              <div className="space-y-3 text-center lg:text-left">
                <h2 className="font-serif text-3xl font-semibold tracking-tight">
                  One dashboard for every order, from payment to pickup
                </h2>
                <p className="text-muted-foreground text-lg">
                  The moment a customer pays, the order appears on your screen — no refreshing a
                  chat thread, no orders slipping through.
                </p>
              </div>

              <ul className="grid gap-6 sm:grid-cols-2">
                {DASHBOARD_FEATURES.map((feature) => (
                  <li key={feature.title} className="flex gap-3">
                    <span className="bg-primary/10 text-primary flex size-9 shrink-0 items-center justify-center rounded-full">
                      <feature.icon className="size-4.5" />
                    </span>
                    <div>
                      <p className="font-medium">{feature.title}</p>
                      <p className="text-muted-foreground mt-0.5 text-sm leading-relaxed">
                        {feature.description}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            <div className="order-1 lg:order-2">
              <DashboardPreview />
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
          <Card className="from-primary to-primary/85 text-primary-foreground border-none bg-gradient-to-br px-6 py-12 text-center shadow-xl sm:px-12">
            <h2 className="font-serif text-3xl font-semibold tracking-tight sm:text-4xl">
              Ready to move your ordering onto WhatsApp?
            </h2>
            <p className="text-primary-foreground/85 mx-auto mt-3 max-w-xl text-lg text-balance">
              Set up your restaurant in minutes — connect WhatsApp, add your menu, and start taking
              orders today.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Button asChild size="lg" variant="secondary" className="w-full sm:w-auto">
                <Link to="/register">Register your restaurant</Link>
              </Button>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="border-primary-foreground/30 bg-transparent text-primary-foreground hover:bg-primary-foreground/10 hover:text-primary-foreground w-full sm:w-auto"
              >
                <Link to="/login">Log in</Link>
              </Button>
            </div>
          </Card>
        </section>
      </main>

      <footer className="border-border/70 border-t">
        <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
          <div className="flex flex-col items-center gap-4 text-center sm:flex-row sm:justify-between sm:text-left">
            <div>
              <span className="flex items-center justify-center gap-2 sm:justify-start">
                <OrderflowLogo className="size-6" />
                <p className="text-primary font-serif text-lg tracking-tight">Orderflow</p>
              </span>
              <p className="text-muted-foreground mt-1 text-sm">
                WhatsApp ordering for independent restaurants.
              </p>
            </div>
            <div className="text-muted-foreground flex items-center gap-6 text-sm">
              <Link to="/login" className="hover:text-foreground hover:underline">
                Merchant log in
              </Link>
              <Link to="/register" className="hover:text-foreground hover:underline">
                Get started
              </Link>
            </div>
          </div>
          <p className="text-muted-foreground mt-8 text-center text-xs sm:text-left">
            © {new Date().getFullYear()} Orderflow. Built for restaurants in Bangalore.
          </p>
        </div>
      </footer>
    </div>
  )
}
