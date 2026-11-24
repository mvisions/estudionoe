import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import pb from '../lib/pocketbase';

const TURNOS = [
  { value: 'none', label: 'Sin guardia' },
  { value: 'day', label: 'Turno de día' },
  { value: 'night', label: 'Turno de noche' },
  { value: '24h', label: '24 horas' },
];

function getDaysOfMonth(year, month) {
  const date = new Date(year, month, 1);
  const days = [];
  while (date.getMonth() === month) {
    days.push(new Date(date));
    date.setDate(date.getDate() + 1);
  }
  return days;
}

export default function FarmaciaPanel() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [asignacion, setAsignacion] = useState(null);
  const [farmacias, setFarmacias] = useState([]);
  const [filtro, setFiltro] = useState({ pais: 'España', ciudad: '', pueblo: '', calle: '' });
  const [selectedFarmacia, setSelectedFarmacia] = useState('');
  const [linking, setLinking] = useState(false);
  const [guardias, setGuardias] = useState({});
  const [current, setCurrent] = useState(new Date());
  const [saving, setSaving] = useState(false);
  const year = current.getFullYear();
  const month = current.getMonth();
  const days = getDaysOfMonth(year, month);

  const loadFarmacias = async () => {
    try {
      const f = await pb.collection('farmacias').getFullList({ sort: 'name' });
      setFarmacias(f);
    } catch (e) {
      console.error(e);
    }
  };

  const loadAsignacion = async () => {
    try {
      const res = await pb.collection('asignaciones').getFirstListItem(`user="${user.id}"`, { expand: 'farmacia' });
      let farmacia = res.expand?.farmacia;
      if (!farmacia && res.farmacia) {
        try { farmacia = await pb.collection('farmacias').getOne(res.farmacia); } catch {}
      }
      setAsignacion({ ...res, expand: { ...(res.expand || {}), farmacia } });
      const guardiasRes = await pb.collection('guardias').getFullList({ filter: `farmacia="${res.farmacia}" && fecha >= "${year}-${String(month + 1).padStart(2, '0')}-01" && fecha <= "${year}-${String(month + 1).padStart(2, '0')}-31"` });
      const map = {};
      guardiasRes.forEach(g => { map[g.fecha] = g.turno; });
      setGuardias(map);
    } catch (e) {
      setAsignacion(null);
      setGuardias({});
    }
  };

  const vincularPendiente = async () => {
    const raw = localStorage.getItem('pendingPharmacyLink');
    if (!raw) return false;
    let pending;
    try { pending = JSON.parse(raw); } catch { localStorage.removeItem('pendingPharmacyLink'); return false; }
    if (!pending.external_id) { localStorage.removeItem('pendingPharmacyLink'); return false; }
    try {
      let farmacia;
      try {
        farmacia = await pb.collection('farmacias').getFirstListItem(`external_id="${pending.external_id}"`);
      } catch {
        farmacia = await pb.collection('farmacias').create({
          name: pending.nombre || 'Farmacia',
          address: pending.nombre || '',
          town: pending.localidad || '',
          province: pending.provincia || '',
          country: 'España',
          external_id: pending.external_id,
        });
      }
      await pb.collection('asignaciones').create({ user: user.id, farmacia: farmacia.id });
      localStorage.removeItem('pendingPharmacyLink');
      return true;
    } catch (e) {
      console.error('Error vinculando farmacia pendiente', e);
      return false;
    }
  };

  useEffect(() => {
    loadFarmacias();
    (async () => {
      const found = await loadAsignacion();
      if (!found) {
        const linked = await vincularPendiente();
        if (linked) await loadAsignacion();
      }
    })();
  }, [user, year, month]);

  const paises = ['España', 'Portugal', 'Francia'];
  const ciudades = [...new Set(farmacias.filter((f) => {
    const pais = f.country || f.pais || 'España';
    return !filtro.pais || pais.toLowerCase() === filtro.pais.toLowerCase();
  }).map((f) => f.province || f.city || f.locality).filter(Boolean))].sort();
  const pueblos = [...new Set(farmacias.filter((f) => {
    const pais = f.country || f.pais || 'España';
    const ciudad = f.province || f.city || f.locality;
    return (!filtro.pais || pais.toLowerCase() === filtro.pais.toLowerCase()) && (!filtro.ciudad || ciudad === filtro.ciudad);
  }).map((f) => f.town).filter(Boolean))].sort();
  const calles = [...new Set(farmacias.filter((f) => {
    const pais = f.country || f.pais || 'España';
    const ciudad = f.province || f.city || f.locality;
    const pueblo = f.town;
    return (!filtro.pais || pais.toLowerCase() === filtro.pais.toLowerCase()) && (!filtro.ciudad || ciudad === filtro.ciudad) && (!filtro.pueblo || pueblo === filtro.pueblo);
  }).map((f) => f.address).filter(Boolean))].sort();

  const farmaciasFiltradas = farmacias.filter((f) => {
    const pais = f.country || f.pais || 'España';
    const ciudad = f.province || f.city || f.locality;
    const pueblo = f.town;
    const calle = f.address;
    if (filtro.pais && pais.toLowerCase() !== filtro.pais.toLowerCase()) return false;
    if (filtro.ciudad && ciudad !== filtro.ciudad) return false;
    if (filtro.pueblo && pueblo !== filtro.pueblo) return false;
    if (filtro.calle && calle !== filtro.calle) return false;
    return true;
  });

  const vincularFarmacia = async () => {
    if (!selectedFarmacia) return;
    setLinking(true);
    try {
      await pb.collection('asignaciones').create({ user: user.id, farmacia: selectedFarmacia });
      await loadAsignacion();
      alert('Farmacia vinculada correctamente.');
    } catch (e) {
      alert('Error al vincular la farmacia. Puede que ya tengas una vinculada.');
    } finally {
      setLinking(false);
    }
  };

  const setTurno = async (dateStr, turno) => {
    if (!asignacion) return;
    setGuardias({ ...guardias, [dateStr]: turno });
    try {
      const existing = await pb.collection('guardias').getFirstListItem(`farmacia="${asignacion.farmacia}" && fecha="${dateStr}"`).catch(() => null);
      if (existing) {
        await pb.collection('guardias').update(existing.id, { turno });
      } else {
        await pb.collection('guardias').create({ farmacia: asignacion.farmacia, fecha: dateStr, turno });
      }
    } catch (e) {
      alert('Error al guardar');
    }
  };

  const guardarGuardias = async () => {
    if (!asignacion) return;
    setSaving(true);
    try {
      for (const day of days) {
        const dateStr = day.toISOString().split('T')[0];
        const turno = guardias[dateStr] || 'none';
        const existing = await pb.collection('guardias').getFirstListItem(`farmacia="${asignacion.farmacia}" && fecha="${dateStr}"`).catch(() => null);
        if (turno === 'none') {
          if (existing) {
            await pb.collection('guardias').delete(existing.id);
          }
          continue;
        }
        if (existing) {
          if (existing.turno !== turno) {
            await pb.collection('guardias').update(existing.id, { turno });
          }
        } else {
          await pb.collection('guardias').create({ farmacia: asignacion.farmacia, fecha: dateStr, turno });
        }
      }
      alert('Guardias guardadas correctamente');
    } catch (e) {
      alert('Error al guardar las guardias');
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const farmacia = asignacion?.expand?.farmacia;

  return (
    <div style={{ minHeight: '100vh', background: '#f7f9f8' }}>
      <header style={{ background: '#fff', borderBottom: '1px solid #eef2ef', padding: '16px 32px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: 12, background: 'linear-gradient(135deg, #167747 0%, #1fa65a 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 700, fontSize: 18 }}>
            +
          </div>
          <div>
            <div style={{ fontWeight: 700 }}>Farmacia de guardia</div>
            <div style={{ opacity: 0.7, fontSize: 14 }}>Panel del farmacéutico</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 14 }}>{user?.email}</div>
            <div style={{ opacity: 0.7, fontSize: 13 }}>Farmacéutico</div>
          </div>
          <button onClick={handleLogout}>Cerrar sesión</button>
        </div>
      </header>

      <main style={{ padding: 32, display: 'grid', gap: 24, maxWidth: 1100, margin: '0 auto' }}>
        {farmacia ? (
          <section style={{ background: '#fff', padding: 28, borderRadius: 16, boxShadow: '0 10px 30px rgba(0,0,0,0.03)', display: 'grid', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
              <div style={{ display: 'grid', gap: 6 }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: '#f1f8f4', color: '#167747', padding: '4px 10px', borderRadius: 999, fontSize: 13, fontWeight: 600, width: 'fit-content' }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#1fa65a' }} />
                  Farmacia vinculada
                </span>
                <h1 style={{ margin: 0, fontSize: 28 }}>{farmacia.name}</h1>
                <p style={{ margin: 0, opacity: 0.8, fontSize: 16 }}>{farmacia.address}{farmacia.town ? `, ${farmacia.town}` : ''}{farmacia.postcode ? `, ${farmacia.postcode}` : ''}</p>
                {farmacia.province && <p style={{ margin: 0, opacity: 0.7 }}>Provincia: {farmacia.province}</p>}
                {farmacia.phone && <p style={{ margin: 0, opacity: 0.7 }}>Teléfono: {farmacia.phone}</p>}
              </div>
              <div style={{ textAlign: 'right', opacity: 0.7 }}>
                <div>Usuario: {user?.email}</div>
              </div>
            </div>
          </section>
        ) : (
          <section style={{ background: '#fff', padding: 24, borderRadius: 12, display: 'grid', gap: 16 }}>
            <h2 style={{ margin: 0 }}>Vincular tu farmacia</h2>
            <p style={{ margin: 0, opacity: 0.7 }}>Busca tu farmacia por ubicación y vincúlala a tu cuenta.</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
              <label style={{ display: 'grid', gap: 6 }}>
                <span>País</span>
                <select value={filtro.pais} onChange={(e) => setFiltro({ pais: e.target.value, ciudad: '', pueblo: '', calle: '' })}>
                  <option value="">Todos</option>
                  {paises.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </label>
              <label style={{ display: 'grid', gap: 6 }}>
                <span>Ciudad / Provincia</span>
                <select value={filtro.ciudad} onChange={(e) => setFiltro({ ...filtro, ciudad: e.target.value, pueblo: '', calle: '' })}>
                  <option value="">Todas</option>
                  {ciudades.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
              <label style={{ display: 'grid', gap: 6 }}>
                <span>Pueblo / Localidad</span>
                <select value={filtro.pueblo} onChange={(e) => setFiltro({ ...filtro, pueblo: e.target.value, calle: '' })}>
                  <option value="">Todos</option>
                  {pueblos.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </label>
              <label style={{ display: 'grid', gap: 6 }}>
                <span>Calle</span>
                <select value={filtro.calle} onChange={(e) => setFiltro({ ...filtro, calle: e.target.value })}>
                  <option value="">Todas</option>
                  {calles.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
            </div>
            <label style={{ display: 'grid', gap: 6 }}>
              <span>Farmacia</span>
              <select value={selectedFarmacia} onChange={(e) => setSelectedFarmacia(e.target.value)}>
                <option value="">Seleccionar farmacia</option>
                {farmaciasFiltradas.map((f) => (
                  <option key={f.id} value={f.id}>{f.name} {f.town ? `- ${f.town}` : ''} {f.address ? `· ${f.address}` : ''}</option>
                ))}
              </select>
            </label>
            <button onClick={vincularFarmacia} disabled={linking || !selectedFarmacia} style={{ padding: '10px 20px', background: '#167747', color: '#fff', border: 'none', borderRadius: 8, width: 'fit-content' }}>
              {linking ? 'Vinculando...' : 'Vincular farmacia'}
            </button>
          </section>
        )}

        {farmacia && (
          <section style={{ background: '#fff', padding: 28, borderRadius: 16, boxShadow: '0 10px 30px rgba(0,0,0,0.03)', display: 'grid', gap: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <h2 style={{ margin: 0 }}>Marcar guardias</h2>
                <p style={{ margin: 0, opacity: 0.7 }}>Selecciona el turno para cada día del mes.</p>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <button onClick={() => setCurrent(new Date(year, month - 1, 1))}>← Mes anterior</button>
                <button onClick={() => setCurrent(new Date())}>Hoy</button>
                <button onClick={() => setCurrent(new Date(year, month + 1, 1))}>Mes siguiente →</button>
                <div style={{ marginLeft: 12, fontWeight: 600 }}>{current.toLocaleDateString('es-ES', { month: 'long', year: 'numeric' })}</div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 10 }}>
              {['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'].map(d => (
                <div key={d} style={{ textAlign: 'center', opacity: 0.6, padding: 8, fontWeight: 600 }}>{d}</div>
              ))}
              {days.map((day) => {
                const dateStr = day.toISOString().split('T')[0];
                const turno = guardias[dateStr] || 'none';
                return (
                  <div key={dateStr} style={{ border: '1px solid #eef2ef', borderRadius: 12, padding: 14, display: 'grid', gap: 10, background: turno === 'none' ? '#fff' : turno === 'day' ? '#f7fff9' : turno === 'night' ? '#f7f9ff' : '#fff7f7' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ fontWeight: 700, fontSize: 18 }}>{day.getDate()}</div>
                      {turno !== 'none' && <span style={{ fontSize: 12, opacity: 0.7 }}>{TURNOS.find(t => t.value === turno)?.label}</span>}
                    </div>
                    <select value={turno} onChange={(e) => setTurno(dateStr, e.target.value)}>
                      {TURNOS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                    </select>
                  </div>
                );
              })}
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button onClick={guardarGuardias} disabled={saving} style={{ padding: '10px 20px', background: '#167747', color: '#fff', border: 'none', borderRadius: 8 }}>{saving ? 'Guardando...' : 'Guardar guardias'}</button>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
