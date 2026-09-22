export const labFixture = {
  label: 'Patrimonio financiero',
  context: 'Ejemplo interno de laboratorio visual. Datos ficticios, no conectados.',
  value: '$128,420',
  delta: { label: '+2.8%', direction: 'positive' as const, detail: 'frente al mes anterior' },
  metrics: [
    { label: 'Cashflow', value: '$2,140', delta: '+$420', direction: 'positive' as const },
    { label: 'Ahorro', value: '31%', delta: '+4 pp', direction: 'positive' as const },
    { label: 'Cobertura', value: '78%', delta: 'parcial', direction: 'warning' as const },
  ],
  trajectory: [42, 45, 43, 49, 53, 51, 58, 61, 64, 68, 66, 73],
  contributors: [
    { label: 'Ingresos extraordinarios', value: '+$900', tone: 'positive' as const },
    { label: 'Viajes y ocio', value: '-$310', tone: 'negative' as const },
    { label: 'Mercado', value: '+$220', tone: 'analytical' as const },
  ],
  attention: [
    {
      id: 'budget-food',
      title: 'Alimentación va por encima del ritmo',
      state: 'PARTIAL' as const,
      summary: 'Faltan dos movimientos por clasificar antes de cerrar el mes.',
      evidence: ['Presupuesto usado: 84%', 'Días transcurridos: 68%', '2 transacciones sin categoría'],
    },
    {
      id: 'subscription',
      title: 'Suscripción anual próxima',
      state: 'READY' as const,
      summary: 'Pago detectado para los próximos 10 días.',
      evidence: ['Fecha estimada: 2026-10-01', 'Importe esperado: $120', 'Fuente: evento recurrente confirmado'],
    },
    {
      id: 'market',
      title: 'Precio de un activo está vencido',
      state: 'STALE' as const,
      summary: 'La valoración existe, pero necesita actualización.',
      evidence: ['Último precio: hace 18 días', 'Impacto estimado: bajo', 'Acción: refrescar market data'],
    },
  ],
  timeline: [
    { label: 'Cierre mensual', when: 'NOW' as const, detail: 'Revisar desviaciones' },
    { label: 'Pago tarjeta', when: 'FUTURE' as const, detail: 'En 6 días' },
    { label: 'Aporte inversión', when: 'FUTURE' as const, detail: 'En 12 días' },
  ],
  dataStates: [
    { state: 'READY' as const, title: 'Datos listos', detail: 'La base local tiene información suficiente.' },
    { state: 'PARTIAL' as const, title: 'Cobertura parcial', detail: 'Falta información de una fuente.' },
    { state: 'STALE' as const, title: 'Dato vencido', detail: 'Conviene actualizar antes de decidir.' },
    { state: 'EMPTY' as const, title: 'Sin datos', detail: 'No hay evidencia para esta sección.' },
    { state: 'UNEVALUABLE' as const, title: 'No evaluable', detail: 'La comparación no es justa todavía.' },
  ],
};
