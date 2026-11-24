export async function fetchDutyCoverage(province, slug, date, signal, fetchData = fetch) {
  try {
    const response = await fetchData(`/data/cobertura-${slug}-${date}.json`, { signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('json')) throw new Error('respuesta que no es JSON');
    const coverage = await response.json();
    if (!Array.isArray(coverage?.consultas) ||
        coverage.consultas.some((item) => !item || typeof item.estado !== 'string')) {
      throw new Error('formato de cobertura no válido');
    }
    return { coverage, error: '' };
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    return { coverage: null, error: `${province}: no se pudo consultar la cobertura (${error.message}).` };
  }
}
