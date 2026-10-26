import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth'
import { Layout, RequireAuth } from './components'
import Account from './pages/Account'
import Attendances from './pages/admin/Attendances'
import Dashboard from './pages/admin/Dashboard'
import Events from './pages/admin/Events'
import Groups from './pages/admin/Groups'
import Users from './pages/admin/Users'
import CheckIn from './pages/CheckIn'
import Login from './pages/Login'
import Signup from './pages/Signup'
import MyEvents from './pages/MyEvents'
import MyHistory from './pages/MyHistory'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter basename={import.meta.env.BASE_URL}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route element={<RequireAuth />}>
            <Route element={<Layout />}>
              <Route path="/account" element={<Account />} />
              <Route element={<RequireAuth role="user" />}>
                <Route path="/" element={<MyEvents />} />
                <Route path="/check-in/:eventId" element={<CheckIn />} />
                <Route path="/history" element={<MyHistory />} />
              </Route>
              <Route element={<RequireAuth role="admin" />}>
                <Route path="/admin" element={<Dashboard />} />
                <Route path="/admin/attendances" element={<Attendances />} />
                <Route path="/admin/events" element={<Events />} />
                <Route path="/admin/users" element={<Users />} />
                <Route path="/admin/groups" element={<Groups />} />
              </Route>
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
