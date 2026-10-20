const DAY_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const HASH_PATTERN = /^[0-9a-f]{64}$/i;

export function parseVisitorLog(text) {
  const entries = new Set();
  for (const line of text.split("\n").filter(line => line.trim())) {
    const event = JSON.parse(line);
    if (!event || !DAY_PATTERN.test(event.day ?? "") || !HASH_PATTERN.test(event.hash ?? ""))
      throw new Error("El log de visitantes contiene una línea inválida.");
    entries.add(`${event.day}:${event.hash}`);
  }
  return entries;
}

function prune(entries, referenceDay, retentionDays) {
  const cutoff = new Date(`${referenceDay}T00:00:00Z`);
  cutoff.setUTCDate(cutoff.getUTCDate() - retentionDays);
  const limit = cutoff.toISOString().slice(0, 10);
  return [...entries].filter(key => key.slice(0, 10) >= limit);
}

export function createGitHubVisitorStore({
  token, repository, branch = "ranking-data", retentionDays = 35, maxBytes = 200000, fetcher = fetch,
}) {
  if (!token || !/^[\w.-]+\/[\w.-]+$/.test(repository)) throw new Error("Configura GITHUB_TOKEN y GITHUB_REPOSITORY.");
  const endpoint = `https://api.github.com/repos/${repository}/contents/visitors.txt`;
  const headers = {
    Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json",
  };
  async function read() {
    const response = await fetcher(`${endpoint}?ref=${encodeURIComponent(branch)}`, { headers, signal: AbortSignal.timeout(20000) });
    if (response.status === 404) return { sha: undefined, entries: new Set() };
    if (!response.ok) throw new Error(`GitHub no permite leer el log de visitantes (${response.status}).`);
    const file = await response.json();
    if (file.encoding !== "base64") throw new Error("El log de visitantes excede el tamaño admitido por la API de GitHub.");
    return { sha: file.sha, entries: parseVisitorLog(Buffer.from(file.content, "base64").toString("utf8")) };
  }
  async function record(hash, day) {
    for (let attempt = 0; attempt < 5; attempt++) {
      const file = await read();
      const live = prune(file.entries, day, retentionDays);
      const key = `${day}:${hash}`;
      if (live.includes(key)) return false;
      live.push(key);
      const text = `${live.map(key => {
        const [day, hash] = key.split(":");
        return JSON.stringify({ day, hash });
      }).join("\n")}\n`;
      if (Buffer.byteLength(text) > maxBytes)
        throw new Error("El log de visitantes ha alcanzado su límite. El administrador debe archivarlo.");
      const body = { message: "Count unique visitor", branch, content: Buffer.from(text).toString("base64") };
      if (file.sha) body.sha = file.sha;
      const response = await fetcher(endpoint, {
        method: "PUT", headers, signal: AbortSignal.timeout(20000), body: JSON.stringify(body),
      });
      if (response.status === 409 || response.status === 422) continue;
      if (!response.ok) throw new Error(`No se pudo guardar el visitante en GitHub (${response.status}).`);
      return true;
    }
    throw new Error("Hay visitantes simultáneos. Reintentaremos contar el visitante.");
  }
  return {
    async record(hash, day) {
      if (!HASH_PATTERN.test(hash ?? "") || !DAY_PATTERN.test(day ?? ""))
        throw new Error("Datos de visitante no válidos.");
      return record(hash, day);
    },
    async count(day) {
      const { entries } = await read();
      return prune(entries, day, retentionDays).filter(key => key.startsWith(`${day}:`)).length;
    },
  };
}
