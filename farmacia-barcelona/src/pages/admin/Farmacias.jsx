import { useEffect, useState } from 'react';
import pb from '../../lib/pocketbase';

export default function Farmacias() {
  const [farmacias, setFarmacias] = useState([]);

  useEffect(() => {
    pb.collection('farmacias').getFullList({ sort: 'name' }).then(setFarmacias).catch(console.error);
  }, []);

  return (
    <div style={{ display: 'grid', gap: 24 }}>
      <header>
        <h1 style={{ margin: 0 }}>Farmacias</h1>
        <p style={{ margin: 0, opacity: 0.7 }}>Listado de farmacias disponibles para asignar</p>
      </header>

      <section style={{ background: '#fff', borderRadius: 12, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead style={{ background: '#f1f5f3' }}>
            <tr>
              <th style={{ textAlign: 'left', padding: 12 }}>Nombre</th>
              <th style={{ textAlign: 'left', padding: 12 }}>Dirección</th>
              <th style={{ textAlign: 'left', padding: 12 }}>Población</th>
              <th style={{ textAlign: 'left', padding: 12 }}>Provincia</th>
            </tr>
          </thead>
          <tbody>
            {farmacias.map((f) => (
              <tr key={f.id} style={{ borderTop: '1px solid #eef2ef' }}>
                <td style={{ padding: 12 }}>{f.name}</td>
                <td style={{ padding: 12 }}>{f.address}</td>
                <td style={{ padding: 12 }}>{f.town}</td>
                <td style={{ padding: 12 }}>{f.province}</td>
              </tr>
            ))}
            {farmacias.length === 0 && (
              <tr>
                <td colSpan={4} style={{ padding: 16, textAlign: 'center', opacity: 0.6 }}>Sin farmacias cargadas aún</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
