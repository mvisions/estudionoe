const DIAS_SEMANA = ['L', 'M', 'X', 'J', 'V', 'S', 'D'];

function cambiarMes(fecha, cambio) {
  const [year, month, day] = fecha.split('-').map(Number);
  const destino = new Date(year, month - 1 + cambio, 1);
  const ultimoDia = new Date(destino.getFullYear(), destino.getMonth() + 1, 0).getDate();
  destino.setDate(Math.min(day, ultimoDia));

  return [
    destino.getFullYear(),
    String(destino.getMonth() + 1).padStart(2, '0'),
    String(destino.getDate()).padStart(2, '0'),
  ].join('-');
}

export default function Calendario({ fecha, hoy, onSelect }) {
  const [year, month] = fecha.split('-').map(Number);
  const primerDia = new Date(year, month - 1, 1);
  const inicioSemana = (primerDia.getDay() + 6) % 7;
  const diasMes = new Date(year, month, 0).getDate();
  const mesNombre = primerDia.toLocaleString('es-ES', { month: 'long', year: 'numeric' });
  const dias = [
    ...Array(inicioSemana).fill(null),
    ...Array.from({ length: diasMes }, (_, index) => index + 1),
  ];

  function seleccionarDia(dia) {
    if (!dia) return;
    onSelect(`${year}-${String(month).padStart(2, '0')}-${String(dia).padStart(2, '0')}`);
  }

  return (
    <div className="calendar-card">
      <div className="calendar-heading">
        <button
          className="calendar-nav"
          type="button"
          aria-label="Mes anterior"
          onClick={() => onSelect(cambiarMes(fecha, -1))}
        >
          ‹
        </button>
        <span className="calendar-month">{mesNombre}</span>
        <button
          className="calendar-nav"
          type="button"
          aria-label="Mes siguiente"
          onClick={() => onSelect(cambiarMes(fecha, 1))}
        >
          ›
        </button>
      </div>
      <div className="calendar-grid" role="grid" aria-label={mesNombre}>
        {DIAS_SEMANA.map((dia, index) => (
          <span className="calendar-weekday" key={`${dia}-${index}`} role="columnheader">
            {dia}
          </span>
        ))}
        {dias.map((dia, index) => {
          if (!dia) return <span className="calendar-empty" key={`empty-${index}`} role="gridcell" />;

          const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
          const isSelected = dateStr === fecha;
          const isToday = dateStr === hoy;
          const classNames = [
            'calendar-day',
            isToday && 'calendar-day--today',
            isSelected && 'calendar-day--selected',
          ].filter(Boolean).join(' ');

          return (
            <button
              className={classNames}
              key={dateStr}
              type="button"
              role="gridcell"
              aria-label={new Date(year, month - 1, dia).toLocaleDateString('es-ES', {
                day: 'numeric',
                month: 'long',
                year: 'numeric',
              })}
              aria-pressed={isSelected}
              onClick={() => seleccionarDia(dia)}
            >
              {dia}
            </button>
          );
        })}
      </div>
    </div>
  );
}
