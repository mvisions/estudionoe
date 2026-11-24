import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import { ProtectedRoute } from './auth/ProtectedRoute';
import Login from './pages/Login';
import CambiarContrasena from './pages/CambiarContrasena';
import AdminLayout from './pages/AdminLayout';
import Asignaciones from './pages/admin/Asignaciones';
import AccesosProvisionales from './pages/admin/AccesosProvisionales';
import Usuarios from './pages/admin/Usuarios';
import Farmacias from './pages/admin/Farmacias';
import FarmaciaPanel from './pages/FarmaciaPanel';
import Mapa from './components/Mapa';
import './App.css';

function MapaPage() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <a className="brand" href="/" aria-label="Farmacia de guardia, inicio">
          <span className="brand-mark" aria-hidden="true">+</span>
          <span>
            <strong>Farmacia de guardia</strong>
            <small>Encuentra ayuda cerca de ti</small>
          </span>
        </a>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span className="header-note">
            <span className="status-dot" />
            Cobertura por provincias
          </span>
        </div>
      </header>
      <Mapa />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<MapaPage />} />
          <Route path="/login" element={<Login />} />
          <Route path="/cambiar-contrasena" element={<CambiarContrasena />} />

          <Route element={<ProtectedRoute requireAdmin />}>
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<Navigate to="asignaciones" replace />} />
              <Route path="asignaciones" element={<Asignaciones />} />
              <Route path="accesos-provisionales" element={<AccesosProvisionales />} />
              <Route path="usuarios" element={<Usuarios />} />
              <Route path="farmacias" element={<Farmacias />} />
            </Route>
          </Route>

          <Route element={<ProtectedRoute requireFarmacia />}>
            <Route path="/farmacia" element={<FarmaciaPanel />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
