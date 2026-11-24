import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import pb from '../../lib/pocketbase';

export default function Asignaciones() {
  const navigate = useNavigate();
  const [asignaciones, setAsignaciones] = useState([]);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ email: '', password: '', phone: '' });

  const loadData = async () => {
    try {
      const [a, users, farmacias] = await Promise.all([
        pb.collection('asignaciones').getFullList({ expand: 'user,farmacia' }),
        pb.collection('users').getFullList(),
        pb.collection('farmacias').getFullList(),
      ]);
      const userMap = Object.fromEntries(users.map((u) => [u.id, u]));
      const farmaciaMap = Object.fromEntries(farmacias.map((f) => [f.id, f]));
      const enriched = a.map((asig) => ({
        ...asig,
        expand: {
          ...(asig.expand || {}),
          user: asig.expand?.user || userMap[asig.user] || null,
          farmacia: asig.expand?.farmacia || farmaciaMap[asig.farmacia] || null,
        },
      }));
      setAsignaciones(enriched);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await pb.collection('users').create({
        email: form.email,
        password: form.password,
        passwordConfirm: form.password,
        role: 'farmacia',
        mustChangePassword: true,
        emailVisibility: true,
        provisionalPassword: form.password,
        phone: form.phone,
      });
      setForm({ email: '', password: '', phone: '' });
      await loadData();
      alert('Acceso creado. El farmacéutico deberá cambiar la contraseña en su primer acceso y vincular su farmacia desde el mapa.');
    } catch (err) {
      alert('Error al crear el acceso. Revisa que el correo no esté ya registrado.');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('¿Eliminar el vínculo entre este farmacéutico y su farmacia?')) return;
    setLoading(true);
    try {
      await pb.collection('asignaciones').delete(id);
      await loadData();
    } catch (e) {
      alert('Error al eliminar el vínculo');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'grid', gap: 24 }}>
      <header>
        <h1 style={{ margin: 0 }}>Vínculos farmacia - farmacéutico</h1>
        <p style={{ margin: 0, opacity: 0.7 }}>
          Crea un acceso (correo + contraseña provisional) para un farmacéutico. El farmacéutico entrará, cambiará la contraseña y vinculará su farmacia desde el mapa.
          Si un vínculo es incorrecto, puedes eliminarlo abajo.
        </p>
      </header>

      <form onSubmit={handleCreateUser} style={{ background: '#fff', padding: 24, borderRadius: 12, display: 'grid', gap: 12, gridTemplateColumns: '2fr 1fr 1fr auto', alignItems: 'end' }}>
        <label style={{ display: 'grid', gap: 6 }}>
          <span>Correo del farmacéutico</span>
          <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
        </label>
        <label style={{ display: 'grid', gap: 6 }}>
          <span>Contraseña provisional</span>
          <input type="text" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="Mínimo 8 caracteres" required />
        </label>
        <label style={{ display: 'grid', gap: 6 }}>
          <span>Teléfono</span>
          <input type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="Opcional" />
        </label>
        <button disabled={loading}>{loading ? 'Creando...' : 'Crear acceso'}</button>
      </form>

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button onClick={() => navigate('/admin/accesos-provisionales')} style={{ padding: '8px 16px' }}>Ver accesos provisionales pendientes</button>
      </div>

      <section style={{ background: '#fff', borderRadius: 12, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead style={{ background: '#f1f5f3' }}>
            <tr>
              <th style={{ textAlign: 'left', padding: 12 }}>Farmacéutico</th>
              <th style={{ textAlign: 'left', padding: 12 }}>Farmacia asociada</th>
              <th style={{ textAlign: 'left', padding: 12 }}>Dirección / Población</th>
              <th style={{ textAlign: 'right', padding: 12 }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {asignaciones.map((a) => (
              <tr key={a.id} style={{ borderTop: '1px solid #eef2ef' }}>
                <td style={{ padding: 12 }}>{a.expand?.user?.email}</td>
                <td style={{ padding: 12 }}>{a.expand?.farmacia?.name}</td>
                <td style={{ padding: 12 }}>{a.expand?.farmacia?.address} {a.expand?.farmacia?.town ? `, ${a.expand?.farmacia?.town}` : ''}</td>
                <td style={{ padding: 12, textAlign: 'right' }}>
                  <button onClick={() => handleDelete(a.id)} disabled={loading}>Eliminar vínculo</button>
                </td>
              </tr>
            ))}
            {asignaciones.length === 0 && (
              <tr>
                <td colSpan={4} style={{ padding: 16, textAlign: 'center', opacity: 0.6 }}>Aún no hay vínculos creados</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}