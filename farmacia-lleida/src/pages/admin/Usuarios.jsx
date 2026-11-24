import { useEffect, useState } from 'react';
import pb from '../../lib/pocketbase';

export default function Usuarios() {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ email: '', password: '', passwordConfirm: '', role: 'farmacia' });

  const load = async () => {
    try {
      const res = await pb.collection('users').getFullList({ sort: 'created' });
      setUsers(res);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await pb.collection('users').create({
        ...form,
        mustChangePassword: form.role === 'farmacia',
        emailVisibility: true,
        provisionalPassword: form.role === 'farmacia' ? form.password : '',
      });
      setForm({ email: '', password: '', passwordConfirm: '', role: 'farmacia' });
      await load();
      alert('Usuario creado. Si es farmacéutico, deberá cambiar la contraseña en su primer acceso.');
    } catch (err) {
      alert('Error al crear usuario');
    }
  };

  return (
    <div style={{ display: 'grid', gap: 24 }}>
      <header>
        <h1 style={{ margin: 0 }}>Usuarios</h1>
        <p style={{ margin: 0, opacity: 0.7 }}>Crear usuarios para asignarles farmacias</p>
      </header>

      <form onSubmit={handleSubmit} style={{ background: '#fff', padding: 24, borderRadius: 12, display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr auto', gap: 12, alignItems: 'end' }}>
        <input type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
        <input type="password" placeholder="Contraseña" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
        <input type="password" placeholder="Confirmar contraseña" value={form.passwordConfirm} onChange={(e) => setForm({ ...form, passwordConfirm: e.target.value })} required />
        <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
          <option value="farmacia">Farmacia</option>
          <option value="admin">Administrador</option>
        </select>
        <button>Crear usuario</button>
      </form>

      <section style={{ background: '#fff', borderRadius: 12, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead style={{ background: '#f1f5f3' }}>
            <tr>
              <th style={{ textAlign: 'left', padding: 12 }}>Email</th>
              <th style={{ textAlign: 'left', padding: 12 }}>Rol</th>
              <th style={{ textAlign: 'left', padding: 12 }}>Creado</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} style={{ borderTop: '1px solid #eef2ef' }}>
                <td style={{ padding: 12 }}>{u.email}</td>
                <td style={{ padding: 12 }}>{u.role}</td>
                <td style={{ padding: 12 }}>{new Date(u.created).toLocaleDateString('es-ES')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
