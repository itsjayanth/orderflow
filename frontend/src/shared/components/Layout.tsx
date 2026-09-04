import type { LucideIcon } from 'lucide-react'
import {
  BookOpen,
  CalendarDays,
  ChevronsLeft,
  ChevronsRight,
  ClipboardList,
  HelpCircle,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Megaphone,
  Menu,
  Settings,
  Users,
  X,
} from 'lucide-react'
import type { Ref } from 'react'
import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'

import { OrderflowLogo } from '@/assets/logo'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useLogout, useMe } from '@/features/auth/useAuth'
import { cn } from '@/lib/utils'
import { Toaster } from '@/shared/components/Toaster'
import { ThemeToggle } from '@/shared/theme/ThemeToggle'

interface NavItem {
  to: string
  label: string
  end?: boolean
  icon: LucideIcon
}

const BASE_NAV_ITEMS: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', end: true, icon: LayoutDashboard },
]

const RESTAURANT_NAV_ITEMS: NavItem[] = [
  { to: '/orders', label: 'Orders', icon: ClipboardList },
  { to: '/catalog', label: 'Catalog', icon: BookOpen },
]

const APPOINTMENT_NAV_ITEMS: NavItem[] = [
  { to: '/appointments', label: 'Appointments', icon: CalendarDays },
  { to: '/services', label: 'Services', icon: BookOpen },
]

const TRAILING_NAV_ITEMS: NavItem[] = [
  { to: '/faq', label: 'FAQs', icon: HelpCircle },
  { to: '/customers', label: 'Customers', icon: Users },
  // Ungated by vertical (unlike Orders+Catalog/Appointments+Services above) --
  // campaigns aren't restaurant- or appointment-specific.
  { to: '/campaigns/templates', label: 'Campaigns', icon: Megaphone },
  { to: '/onboarding', label: 'Onboarding', icon: ListChecks },
  { to: '/settings', label: 'Settings', icon: Settings },
]

// Additive, not exclusive (VERTICAL_TOGGLE_PLAN.md): a merchant with both
// verticals enabled sees Orders + Catalog + Appointments + Services, one
// with just one enabled sees exactly that pair, and neither shows before
// the merchant has enabled anything (the brief window before the
// onboarding wizard's first step resolves) -- no flash-then-swap.
function navItemsForVerticals(restaurantEnabled: boolean, appointmentEnabled: boolean): NavItem[] {
  return [
    ...BASE_NAV_ITEMS,
    ...(restaurantEnabled ? RESTAURANT_NAV_ITEMS : []),
    ...(appointmentEnabled ? APPOINTMENT_NAV_ITEMS : []),
    ...TRAILING_NAV_ITEMS,
  ]
}

const SIDEBAR_STORAGE_KEY = 'orderflow-sidebar-collapsed'

function readStoredCollapsed(): boolean {
  if (typeof window === 'undefined') return false
  // localStorage access can throw (Safari private browsing, some sandboxed
  // test/embed environments) -- collapse state is a nice-to-have, not worth
  // crashing the shell over.
  try {
    return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

function initials(name: string) {
  return name
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

function SidebarLink({
  item,
  collapsed,
  onNavigate,
}: {
  item: NavItem
  collapsed: boolean
  onNavigate?: () => void
}) {
  const link = (
    <NavLink
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 rounded-lg border-l-2 py-2 text-sm font-medium transition-colors duration-150',
          collapsed ? 'justify-center px-2' : 'px-3',
          isActive
            ? 'border-primary bg-secondary text-foreground'
            : 'border-transparent text-muted-foreground hover:bg-secondary/60 hover:text-foreground',
        )
      }
    >
      <item.icon className="size-5 shrink-0" />
      {!collapsed && <span className="truncate">{item.label}</span>}
    </NavLink>
  )

  if (!collapsed) return link

  return (
    <Tooltip>
      <TooltipTrigger asChild>{link}</TooltipTrigger>
      <TooltipContent side="right">{item.label}</TooltipContent>
    </Tooltip>
  )
}

function UserMenu({
  businessName,
  collapsed,
  onLogoutRequest,
  align,
  side,
  triggerRef,
}: {
  businessName: string
  collapsed?: boolean
  onLogoutRequest: () => void
  align: 'start' | 'end'
  side: 'top' | 'bottom'
  triggerRef?: Ref<HTMLButtonElement>
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          ref={triggerRef}
          type="button"
          className={cn(
            'hover:bg-accent focus-visible:ring-ring/30 flex min-w-0 items-center gap-2 rounded-lg p-1.5 text-left outline-none transition-colors duration-150 focus-visible:ring-4',
            collapsed ? 'justify-center' : 'flex-1',
          )}
        >
          <Avatar className="size-8">
            <AvatarFallback>{initials(businessName)}</AvatarFallback>
          </Avatar>
          {!collapsed && (
            <span className="min-w-0 flex-1 truncate text-sm font-medium">{businessName}</span>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align={align} side={side} className="w-56">
        <DropdownMenuLabel className="truncate text-sm font-medium tracking-normal normal-case">
          {businessName}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <NavLink to="/settings">
            <Settings />
            Settings
          </NavLink>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onSelect={onLogoutRequest}>
          <LogOut />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function Brand({ collapsed, onNavigate }: { collapsed?: boolean; onNavigate?: () => void }) {
  return (
    <Link to="/dashboard" onClick={onNavigate} className="flex min-w-0 items-center gap-2">
      <OrderflowLogo className="size-7 shrink-0" />
      {!collapsed && (
        <span className="text-primary truncate font-serif text-lg tracking-tight">Orderflow</span>
      )}
    </Link>
  )
}

export function Layout() {
  const me = useMe()
  const logout = useLogout()
  const [collapsed, setCollapsed] = useState(readStoredCollapsed)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [logoutConfirmOpen, setLogoutConfirmOpen] = useState(false)
  // The logout confirmation is opened from a DropdownMenuItem, which
  // unmounts as soon as the menu closes (selecting it closes the menu
  // before the AlertDialog even opens) -- Radix's default close-focus
  // restoration has nothing left to return to at that point and falls back
  // to <body>, silently dropping a keyboard user back at the top of the
  // document. Refocusing the still-mounted trigger button explicitly (via
  // AlertDialogContent's onCloseAutoFocus below) keeps focus somewhere
  // sensible instead. Only one of these two triggers is ever visible at a
  // given viewport width (desktop sidebar vs. mobile header), so both refs
  // are tried and whichever is actually on-screen wins.
  const desktopUserMenuTriggerRef = useRef<HTMLButtonElement>(null)
  const mobileUserMenuTriggerRef = useRef<HTMLButtonElement>(null)
  // Same close-focus problem as above, on the mobile nav drawer: it's a
  // plain state-controlled Dialog (`open`/`onOpenChange`, no
  // `<DialogTrigger>`), and Radix's default restore-focus-to-previous-
  // active-element doesn't reliably land back on the hamburger button once
  // the slide-out close animation finishes -- observed landing on <body>
  // instead, stranding keyboard focus at the top of the document.
  const mobileNavTriggerRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    try {
      window.localStorage.setItem(SIDEBAR_STORAGE_KEY, collapsed ? '1' : '0')
    } catch {
      // See readStoredCollapsed -- persistence is best-effort.
    }
  }, [collapsed])

  const businessName = me.data?.merchant.business_name
  const navItems = navItemsForVerticals(
    me.data?.merchant.restaurant_enabled ?? false,
    me.data?.merchant.appointment_enabled ?? false,
  )
  const requestLogout = () => setLogoutConfirmOpen(true)

  return (
    <div className="flex min-h-svh">
      {/* Desktop sidebar */}
      <aside
        className={cn(
          'sticky top-0 hidden h-svh shrink-0 flex-col border-r transition-[width] duration-200 lg:flex',
          collapsed ? 'w-[4.5rem]' : 'w-64',
        )}
      >
        <div className={cn('flex items-center px-4 py-4', collapsed && 'justify-center px-2')}>
          <Brand collapsed={collapsed} />
        </div>

        <nav className={cn('flex flex-1 flex-col gap-1 overflow-y-auto px-3', collapsed && 'px-2')}>
          {navItems.map((item) => (
            <SidebarLink key={item.to} item={item} collapsed={collapsed} />
          ))}
        </nav>

        <div className="px-3 pb-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className={cn(
              'text-muted-foreground w-full',
              !collapsed && 'w-full justify-start gap-2 px-3',
            )}
            onClick={() => setCollapsed((prev) => !prev)}
          >
            {collapsed ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />}
            {!collapsed && <span className="text-sm font-medium">Collapse</span>}
          </Button>
        </div>

        <div
          className={cn(
            'flex items-center gap-1 border-t p-2',
            collapsed && 'flex-col-reverse gap-2',
          )}
        >
          {businessName && (
            <UserMenu
              businessName={businessName}
              collapsed={collapsed}
              onLogoutRequest={requestLogout}
              align="start"
              side="top"
              triggerRef={desktopUserMenuTriggerRef}
            />
          )}
          <ThemeToggle />
        </div>
      </aside>

      {/* Mobile nav drawer */}
      <Dialog open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
        <DialogContent
          side="left"
          showCloseButton={false}
          className="w-72 max-w-[85vw] gap-0 p-0"
          onCloseAutoFocus={(event) => {
            if (mobileNavTriggerRef.current) {
              event.preventDefault()
              mobileNavTriggerRef.current.focus()
            }
          }}
        >
          <DialogTitle className="sr-only">Navigation menu</DialogTitle>
          <DialogDescription className="sr-only">
            Links to every section of the dashboard
          </DialogDescription>
          <div className="flex items-center justify-between border-b px-4 py-3.5">
            <Brand onNavigate={() => setMobileNavOpen(false)} />
            <DialogClose asChild>
              <Button type="button" variant="ghost" size="icon" aria-label="Close menu">
                <X className="size-4" />
              </Button>
            </DialogClose>
          </div>
          <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3">
            {navItems.map((item) => (
              <SidebarLink
                key={item.to}
                item={item}
                collapsed={false}
                onNavigate={() => setMobileNavOpen(false)}
              />
            ))}
          </nav>
        </DialogContent>
      </Dialog>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-border/70 bg-background/85 sticky top-0 z-10 flex items-center gap-2 border-b px-4 py-3 backdrop-blur-sm sm:px-6">
          <Button
            ref={mobileNavTriggerRef}
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Open menu"
            className="lg:hidden"
            onClick={() => setMobileNavOpen(true)}
          >
            <Menu className="size-5" />
          </Button>
          <div className="lg:hidden">
            <Brand />
          </div>
          <div className="flex-1" />
          <div className="flex items-center gap-1 lg:hidden">
            <ThemeToggle />
            {businessName && (
              <UserMenu
                businessName={businessName}
                onLogoutRequest={requestLogout}
                align="end"
                side="bottom"
                triggerRef={mobileUserMenuTriggerRef}
              />
            )}
          </div>
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-10">
          <Outlet />
        </main>
      </div>

      <AlertDialog open={logoutConfirmOpen} onOpenChange={setLogoutConfirmOpen}>
        <AlertDialogContent
          onCloseAutoFocus={(event) => {
            const trigger = [
              desktopUserMenuTriggerRef.current,
              mobileUserMenuTriggerRef.current,
            ].find((el) => el && el.offsetParent !== null)
            if (trigger) {
              event.preventDefault()
              trigger.focus()
            }
          }}
        >
          <AlertDialogHeader>
            <AlertDialogTitle>Log out?</AlertDialogTitle>
            <AlertDialogDescription>
              You'll need to sign in again to access the dashboard.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={() => logout.mutate()}>
              Log out
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Toaster />
    </div>
  )
}
