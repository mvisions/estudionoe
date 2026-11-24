import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import pb from '../../lib/pocketbase';

export default function AccesosProvisionales() {
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    try {
      const res = await pb.collection('users').getFullList();
      setUsers(res.filter((u) => u.role === 'farmacia' && u.mustChangePassword));
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (id) => {
    if (!confirm('¿Eliminar este acceso provisional?')) return;
    setLoading(true);
    try {
      await pb.collection('users').delete(id);
      await load();
    } catch (e) {
      alert('Error al eliminar');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'grid', gap: 24 }}>
      <header style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <button onClick={() => navigate(-1)}>← Volver</button>
        <div>
          <h1 style={{ margin: 0 }}>Accesos provisionales pendientes</h1>
          <p style={{ margin: 0, opacity: 0.7 }}>Farmacéuticos que aún no han cambiado la contraseña provisional.</p>
        </div>
      </header>

      <section style={{ background: '#fff', borderRadius: 12, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead style={{ background: '#f1f5f3' }}>
            <tr>
              <th style={{ textAlign: 'left', padding: 12 }}>Correo</th>
              <th style={{ textAlign: 'left', padding: 12 }}>Contraseña provisional</th>
              <th style={{ textAlign: 'left', padding: 12 }}>Teléfono</th>
              <th style={{ textAlign: 'left', padding: 12 }}>Creado</th>
              <th style={{ textAlign: 'right', padding: 12 }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} style={{ borderTop: '1px solid #eef2ef' }}>
                <td style={{ padding: 12 }}>{u.email}</td>
                <td style={{ padding: 12, fontFamily: 'monospace' }}>{u.provisionalPassword || '—'}</td>
                <td style={{ padding: 12 }}>{u.phone || '—'}</td>
                <td style={{ padding: 12 }}>{u.created ? new Date(u.created).toLocaleDateString('es-ES') : '—'}</td>
                <td style={{ padding: 12, textAlign: 'right' }}>
                  <button onClick={() => handleDelete(u.id)} disabled={loading}>Eliminar</button>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td colSpan={5} style={{ padding: 16, textAlign: 'center', opacity: 0.6 }}>No hay accesos provisionales pendientes</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}