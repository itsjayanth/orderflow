import {
  Bell,
  Check,
  ClipboardList,
  CreditCard,
  LayoutDashboard,
  MessageCircle,
  Package,
  Percent,
  ShieldCheck,
  ShoppingCart,
  Smartphone,
  SmartphoneNfc,
  Sparkles,
  Store,
  X,
} from 'lucide-react'
import type { ComponentType } from 'react'
import { Link } from 'react-router-dom'

import { OrderflowLogo } from '@/assets/logo'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { Reveal } from '@/shared/components/Reveal'

import { ChatMockup } from './components/ChatMockup'
import { DashboardPreview } from './components/DashboardPreview'

const TRUST_POINTS: { icon: ComponentType<{ className?: string }>; label: string }[] = [
  { icon: SmartphoneNfc, label: 'No app for customers to install' },
  { icon: Store, label: 'Works alongside how you already run your business' },
  { icon: ShieldCheck, label: 'Payments verified before orders confirm' },
]

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
      'Once payment clears, the customer gets automatic updates — confirmed, processing, ready for pickup.',
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
      'New orders appear within seconds of payment, sorted by status — New, Processing, Ready, Completed.',
  },
  {
    icon: Bell,
    title: 'One-tap status updates',
    description:
      'Move an order forward and Orderflow messages the customer on WhatsApp automatically — no separate notification step.',
  },
  {
    icon: Package,
    title: 'Catalog control',
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

type CompareTone = 'muted' | 'primary'

const COMPARE_COLUMNS: {
  title: string
  subtitle: string
  tone: CompareTone
  highlight?: boolean
  points: string[]
}[] = [
  {
    title: 'Phone calls & DMs',
    subtitle: 'The status quo',
    tone: 'muted',
    points: [
      'Orders scribbled by hand or half-remembered',
      'No record when something goes wrong',
      'Staff tied up on calls during the rush',
    ],
  },
  {
    title: 'Delivery apps',
    subtitle: 'Third-party marketplaces',
    tone: 'muted',
    points: [
      'A cut taken out of every single order',
      'The customer relationship belongs to the platform',
      'Your menu sits next to every competitor’s',
    ],
  },
  {
    title: 'Orderflow',
    subtitle: 'Your number, your customers',
    tone: 'primary',
    highlight: true,
    points: [
      'Structured ordering on WhatsApp, which customers already have open',
      'Payment confirmed automatically before it reaches your kitchen',
      'Every order and every customer relationship stays yours',
    ],
  },
]

const FAQ_ITEMS: { question: string; answer: string }[] = [
  {
    question: 'Do my customers need to install anything?',
    answer:
      'No. The entire ordering experience — browsing the menu, building a cart, paying, and getting status updates — happens inside WhatsApp, which almost every customer already has open.',
  },
  {
    question: 'Does this replace my existing systems?',
    answer:
      'No. Paid orders land in one clear dashboard your staff act on manually today — nothing about your existing workflow has to change to get started. POS integration (Petpooja) is on the roadmap for restaurants that want it later, not a requirement now.',
  },
  {
    question: 'How does payment actually work?',
    answer:
      'A secure Razorpay/UPI payment link is sent in the same WhatsApp chat. The order only moves into your kitchen queue once that payment is confirmed — no staff member has to manually check or guess.',
  },
  {
    question: 'Will customers know their order status?',
    answer:
      'Yes. As your staff move an order forward on the dashboard, Orderflow automatically messages the customer on WhatsApp — at minimum when it’s ready — so nobody has to send that update by hand.',
  },
  {
    question: 'Is my business’s data kept separate from others?',
    answer:
      'Yes. Every restaurant’s orders, menu, and customers are isolated from every other restaurant on the platform, and sensitive credentials like your WhatsApp and payment keys are encrypted at rest.',
  },
]

function TrustPill({
  icon: Icon,
  label,
}: {
  icon: ComponentType<{ className?: string }>
  label: string
}) {
  return (
    <span className="border-border/70 bg-card/70 text-foreground/80 inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs font-medium shadow-sm backdrop-blur-sm sm:text-sm">
      <Icon className="text-primary size-3.5 shrink-0 sm:size-4" />
      {label}
    </span>
  )
}

function CompareCard({
  column,
  index,
}: {
  column: (typeof COMPARE_COLUMNS)[number]
  index: number
}) {
  return (
    <Reveal as="li" delayMs={index * 100} className="h-full list-none">
      <Card
        className={cn(
          'flex h-full flex-col gap-5 p-6 transition-all duration-300',
          column.highlight
            ? 'border-primary/40 ring-primary/15 bg-primary/[0.03] shadow-lg ring-2'
            : 'hover:border-border hover:-translate-y-1 hover:shadow-md',
        )}
      >
        <div>
          <p
            className={cn(
              'text-xs font-medium tracking-wide uppercase',
              column.highlight ? 'text-primary' : 'text-muted-foreground',
            )}
          >
            {column.subtitle}
          </p>
          <h3 className="font-serif text-xl font-semibold">{column.title}</h3>
        </div>
        <ul className="space-y-3">
          {column.points.map((point) => (
            <li key={point} className="flex items-start gap-2.5 text-sm leading-relaxed">
              {column.tone === 'primary' ? (
                <Check className="text-primary mt-0.5 size-4 shrink-0" />
              ) : (
                <X className="text-muted-foreground/60 mt-0.5 size-4 shrink-0" />
              )}
              <span className={column.tone === 'muted' ? 'text-muted-foreground' : ''}>
                {point}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </Reveal>
  )
}

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
        <section className="from-background to-secondary/40 bg-grain relative overflow-hidden bg-gradient-to-b">
          <div
            className="bg-primary/15 animate-float-slow pointer-events-none absolute top-0 -left-24 -z-10 size-[26rem] rounded-full blur-3xl"
            aria-hidden="true"
          />
          <div
            className="bg-brand-gold/20 animate-float-slow pointer-events-none absolute -right-24 bottom-0 -z-10 size-[24rem] rounded-full blur-3xl [animation-delay:-3.5s]"
            aria-hidden="true"
          />

          <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-2 lg:py-28">
            <Reveal className="space-y-6 text-center lg:text-left">
              <span className="border-brand-gold/40 bg-brand-gold/15 text-brand-gold-foreground mx-auto inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium lg:mx-0">
                <Sparkles className="size-3.5" />
                WhatsApp-native ordering
              </span>
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
              <div className="flex flex-wrap items-center justify-center gap-2 lg:justify-start">
                {TRUST_POINTS.map((point) => (
                  <TrustPill key={point.label} icon={point.icon} label={point.label} />
                ))}
              </div>
            </Reveal>

            <Reveal delayMs={150}>
              <ChatMockup />
            </Reveal>
          </div>
        </section>

        {/* Why Orderflow */}
        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
          <Reveal className="mx-auto max-w-2xl space-y-3 text-center">
            <h2 className="font-serif text-3xl font-semibold tracking-tight">
              Built for restaurants, not another marketplace
            </h2>
            <p className="text-muted-foreground text-lg">
              Orderflow isn’t a food-delivery app competing for your customer’s attention — it’s
              your own ordering channel, running on the app they already use every day.
            </p>
          </Reveal>

          <ul className="mt-12 grid grid-cols-1 gap-5 md:grid-cols-3">
            {COMPARE_COLUMNS.map((column, index) => (
              <CompareCard key={column.title} column={column} index={index} />
            ))}
          </ul>
        </section>

        {/* Customer ordering flow */}
        <section className="bg-secondary/20 border-border/70 border-y">
          <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
            <Reveal className="mx-auto max-w-2xl space-y-3 text-center">
              <h2 className="font-serif text-3xl font-semibold tracking-tight">
                From “hi” to hot food, without leaving the chat
              </h2>
              <p className="text-muted-foreground text-lg">
                Customers already have WhatsApp open. Orderflow guides them through a structured
                order — no free-text chatbot guesswork, no separate app.
              </p>
            </Reveal>

            <ol className="mt-12 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
              {ORDER_STEPS.map((step, index) => (
                <Reveal as="li" key={step.title} delayMs={index * 80} className="h-full">
                  <Card className="h-full space-y-3 p-5 transition-all duration-300 hover:-translate-y-1 hover:shadow-md">
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
                </Reveal>
              ))}
            </ol>
          </div>
        </section>

        {/* Merchant dashboard */}
        <section>
          <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-2 lg:py-24">
            <Reveal className="order-2 space-y-8 lg:order-1">
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
            </Reveal>

            <Reveal delayMs={150} className="order-1 lg:order-2">
              <DashboardPreview />
            </Reveal>
          </div>
        </section>

        {/* FAQ */}
        <section className="bg-secondary/20 border-border/70 border-y">
          <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6 sm:py-20">
            <Reveal className="space-y-3 text-center">
              <h2 className="font-serif text-3xl font-semibold tracking-tight">
                Questions restaurant owners ask
              </h2>
              <p className="text-muted-foreground text-lg">
                The practical details before you hand this to your team.
              </p>
            </Reveal>

            <Reveal delayMs={100} className="mt-10">
              <Accordion type="multiple">
                {FAQ_ITEMS.map((item) => (
                  <AccordionItem
                    key={item.question}
                    value={item.question}
                    className="border-border/70"
                  >
                    <AccordionTrigger className="py-5 text-base font-medium hover:no-underline">
                      {item.question}
                    </AccordionTrigger>
                    <AccordionContent>
                      <p className="text-muted-foreground text-sm leading-relaxed">{item.answer}</p>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </Reveal>
          </div>
        </section>

        {/* Final CTA */}
        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
          <Reveal>
            <Card className="from-primary to-primary/85 text-primary-foreground bg-grain relative overflow-hidden border-none bg-gradient-to-br px-6 py-12 text-center shadow-xl sm:px-12">
              <div
                className="bg-brand-gold/25 animate-float-slow pointer-events-none absolute -top-16 -right-16 size-64 rounded-full blur-3xl"
                aria-hidden="true"
              />
              <h2 className="font-serif text-3xl font-semibold tracking-tight sm:text-4xl">
                Ready to move your ordering onto WhatsApp?
              </h2>
              <p className="text-primary-foreground/85 mx-auto mt-3 max-w-xl text-lg text-balance">
                Set up your restaurant in minutes — connect WhatsApp, add your menu, and start
                taking orders today.
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
              <p className="text-primary-foreground/70 mt-6 flex items-center justify-center gap-1.5 text-xs">
                <Percent className="size-3.5" />
                No marketplace commission — this is your ordering channel, not ours.
              </p>
            </Card>
          </Reveal>
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
