import { Route, Routes } from 'react-router-dom'

import { AppointmentDetailPage } from '@/features/appointments/AppointmentDetailPage'
import { AppointmentsPage } from '@/features/appointments/AppointmentsPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { RegisterPage } from '@/features/auth/RegisterPage'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { BookingPage } from '@/features/booking/BookingPage'
import { TemplatesPage } from '@/features/campaigns/TemplatesPage'
import { CatalogPage } from '@/features/catalog/CatalogPage'
import { CustomersPage } from '@/features/customers/CustomersPage'
import { DashboardHomePage } from '@/features/dashboard/DashboardHomePage'
import { FAQPage } from '@/features/faq/FAQPage'
import { HomePage } from '@/features/marketing/HomePage'
import { OnboardingPage } from '@/features/onboarding/OnboardingPage'
import { OrderingPage } from '@/features/ordering/OrderingPage'
import { OrderDetailPage } from '@/features/orders/OrderDetailPage'
import { OrdersPage } from '@/features/orders/OrdersPage'
import { ServicesPage } from '@/features/services/ServicesPage'
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
      {/* Public customer-facing appointment booking webview -- no staff auth, no dashboard Layout. */}
      <Route path="book/:merchantId" element={<BookingPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route path="dashboard" element={<DashboardHomePage />} />
          <Route path="orders" element={<OrdersPage />} />
          <Route path="orders/:orderId" element={<OrderDetailPage />} />
          <Route path="appointments" element={<AppointmentsPage />} />
          <Route path="appointments/:appointmentId" element={<AppointmentDetailPage />} />
          <Route path="catalog" element={<CatalogPage />} />
          <Route path="services" element={<ServicesPage />} />
          <Route path="faq" element={<FAQPage />} />
          <Route path="customers" element={<CustomersPage />} />
          <Route path="campaigns/templates" element={<TemplatesPage />} />
          <Route path="onboarding" element={<OnboardingPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Route>
      {/* Outside <RequireAuth> -- a 404 shouldn't require login to see. */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
