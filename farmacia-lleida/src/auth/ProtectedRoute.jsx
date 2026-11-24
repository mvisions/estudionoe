import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';

export function ProtectedRoute({ requireAdmin = false, requireFarmacia = false }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div style={{ padding: 24 }}>Cargando...</div>;
  if (!user) return <Navigate to="/login" replace />;

  if (requireFarmacia && user.role === 'farmacia' && user.mustChangePassword && location.pathname !== '/cambiar-contrasena') {
    return <Navigate to="/cambiar-contrasena" replace />;
  }

  if (requireAdmin && user.role !== 'admin') {
    return <Navigate to="/" replace />;
  }

  if (requireFarmacia && user.role !== 'farmacia') {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
