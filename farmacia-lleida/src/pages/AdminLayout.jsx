import { Link, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

export default function AdminLayout() {
  const { logout, user } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', minHeight: '100vh' }}>
      <aside style={{ background: '#101915', color: '#fff', padding: 24, display: 'grid', alignContent: 'start', gap: 16 }}>
        <div>
          <strong>Panel Admin</strong>
          <div style={{ opacity: 0.7, fontSize: 14 }}>{user?.email}</div>
        </div>
        <nav style={{ display: 'grid', gap: 8 }}>
          <Link to="/admin/asignaciones" style={{ color: '#fff', textDecoration: 'none' }}>Vínculos</Link>
          <Link to="/admin/accesos-provisionales" style={{ color: '#fff', textDecoration: 'none' }}>Accesos provisionales</Link>
          <Link to="/admin/farmacias" style={{ color: '#fff', textDecoration: 'none' }}>Farmacias</Link>
        </nav>
        <button onClick={handleLogout} style={{ marginTop: 24 }}>Cerrar sesión</button>
      </aside>
      <main style={{ background: '#f7f9f8', padding: 32 }}>
        <Outlet />
      </main>
    </div>
  );
}
