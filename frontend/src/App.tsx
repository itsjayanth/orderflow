import { Route, Routes } from 'react-router-dom'

import { LoginPage } from '@/features/auth/LoginPage'
import { RegisterPage } from '@/features/auth/RegisterPage'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { CatalogPage } from '@/features/catalog/CatalogPage'
import { CustomersPage } from '@/features/customers/CustomersPage'
import { DashboardHomePage } from '@/features/dashboard/DashboardHomePage'
import { FAQPage } from '@/features/faq/FAQPage'
import { HomePage } from '@/features/marketing/HomePage'
import { OnboardingPage } from '@/features/onboarding/OnboardingPage'
import { OrderingPage } from '@/features/ordering/OrderingPage'
import { OrderDetailPage } from '@/features/orders/OrderDetailPage'
import { OrdersPage } from '@/features/orders/OrdersPage'
import { SettingsPage } from '@/features/settings/SettingsPage'
import { Layout } from '@/shared/components/Layout'
import { NotFoundPage } from '@/shared/components/NotFoundPage'

export function App() {
  return (
    <Routes>
      {/* Public marketing home page -- no staff auth, no dashboard Layout. */}
      <Route index element={<HomePage />} />
      <Route path="login" element={<LoginPage />} />
      <Route path="register" element={<RegisterPage />} />
      {/* Public customer-facing ordering webview -- no staff auth, no dashboard Layout. */}
      <Route path="order/:merchantId" element={<OrderingPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route path="dashboard" element={<DashboardHomePage />} />
          <Route path="orders" element={<OrdersPage />} />
          <Route path="orders/:orderId" element={<OrderDetailPage />} />
          <Route path="catalog" element={<CatalogPage />} />
          <Route path="faq" element={<FAQPage />} />
          <Route path="customers" element={<CustomersPage />} />
          <Route path="onboarding" element={<OnboardingPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Route>
      {/* Outside <RequireAuth> -- a 404 shouldn't require login to see. */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
