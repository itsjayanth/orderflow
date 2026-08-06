import { Route, Routes } from 'react-router-dom'

import { LoginPage } from '@/features/auth/LoginPage'
import { RegisterPage } from '@/features/auth/RegisterPage'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { CatalogPage } from '@/features/catalog/CatalogPage'
import { CustomersPage } from '@/features/customers/CustomersPage'
import { DashboardHomePage } from '@/features/dashboard/DashboardHomePage'
import { OnboardingPage } from '@/features/onboarding/OnboardingPage'
import { OrderingPage } from '@/features/ordering/OrderingPage'
import { OrderDetailPage } from '@/features/orders/OrderDetailPage'
import { OrdersPage } from '@/features/orders/OrdersPage'
import { SettingsPage } from '@/features/settings/SettingsPage'
import { Layout } from '@/shared/components/Layout'

export function App() {
  return (
    <Routes>
      <Route path="login" element={<LoginPage />} />
      <Route path="register" element={<RegisterPage />} />
      {/* Public customer-facing ordering webview -- no staff auth, no dashboard Layout. */}
      <Route path="order/:merchantId" element={<OrderingPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route index element={<DashboardHomePage />} />
          <Route path="orders" element={<OrdersPage />} />
          <Route path="orders/:orderId" element={<OrderDetailPage />} />
          <Route path="catalog" element={<CatalogPage />} />
          <Route path="customers" element={<CustomersPage />} />
          <Route path="onboarding" element={<OnboardingPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
