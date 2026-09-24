import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from '@/context/ThemeContext';
import { ToastProvider } from '@/context/ToastContext';
import { AuthProvider } from '@/context/AuthContext';
import ToastContainer from '@/components/common/ToastContainer';
import PrivateRoute from '@/components/common/PrivateRoute';
import Home from '@/pages/Home';
import Login from '@/pages/Login';
import Dashboard from '@/pages/Dashboard';
import Users from '@/pages/Users';
import Roles from '@/pages/Roles';
import Permissions from '@/pages/Permissions';
import Profile from '@/pages/Profile';
import Audit from '@/pages/Audit';
import ForgotPassword from '@/pages/ForgotPassword';
import ResetPassword from '@/pages/ResetPassword';
import ResourcePage from '@/pages/ResourcePage';
import LiquidacionPlanilla from '@/pages/LiquidacionPlanilla';
import { RESOURCES } from '@/lib/resources';

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <ToastProvider>
          <AuthProvider>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/login" element={<Login />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/reset-password" element={<ResetPassword />} />
              <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
              <Route path="/users" element={<PrivateRoute><Users /></PrivateRoute>} />
              <Route path="/roles" element={<PrivateRoute><Roles /></PrivateRoute>} />
              <Route path="/permissions" element={<PrivateRoute><Permissions /></PrivateRoute>} />
              <Route path="/profile" element={<PrivateRoute><Profile /></PrivateRoute>} />
              <Route path="/audit" element={<PrivateRoute><Audit /></PrivateRoute>} />
              {RESOURCES.map((r) => (
                <Route key={r.key} path={`/${r.path}`} element={<PrivateRoute><ResourcePage key={r.key} resourceKey={r.key} /></PrivateRoute>} />
              ))}
              <Route path="/liquidaciones/:id/planilla" element={<PrivateRoute><LiquidacionPlanilla /></PrivateRoute>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            <ToastContainer />
          </AuthProvider>
        </ToastProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
