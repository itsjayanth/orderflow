import { Route, Routes } from 'react-router-dom'

import { CatalogPage } from '@/features/catalog/CatalogPage'
import { CustomersPage } from '@/features/customers/CustomersPage'
import { DashboardHomePage } from '@/features/dashboard/DashboardHomePage'
import { OnboardingPage } from '@/features/onboarding/OnboardingPage'
import { OrdersPage } from '@/features/orders/OrdersPage'
import { Layout } from '@/shared/components/Layout'

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardHomePage />} />
        <Route path="orders" element={<OrdersPage />} />
        <Route path="catalog" element={<CatalogPage />} />
        <Route path="customers" element={<CustomersPage />} />
        <Route path="onboarding" element={<OnboardingPage />} />
      </Route>
    </Routes>
  )
}
