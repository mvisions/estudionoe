import provincias from '../../data/provincias.json';

export default function SelectorProvincia({ provincia, onChange }) {
  return (
    <select
      className="province-select"
      value={provincia}
      onChange={(event) => onChange(event.target.value)}
      aria-label="Filtrar por provincia"
    >
      <option value="">Toda España</option>
      {provincias.map((item) => (
        <option key={item.id} value={item.nombre}>{item.nombre}</option>
      ))}
    </select>
  );
}
