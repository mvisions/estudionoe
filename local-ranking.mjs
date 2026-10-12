export const rankingKey = "noe-local-ranking-v1";

export function readRanking(storage) {
  const entries = JSON.parse(storage.getItem(rankingKey) ?? "[]");
  if (!Array.isArray(entries) || entries.some(entry =>
    !entry || typeof entry.id !== "string" || typeof entry.name !== "string"
    || typeof entry.course !== "string" || !["easy", "matching", "written"].includes(entry.mode)
    || !Number.isFinite(entry.grade) || entry.grade < 0 || entry.grade > 10
    || !Number.isFinite(entry.durationMs) || entry.durationMs < 0
    || !Number.isFinite(entry.finishedAt))) throw new Error("El ranking guardado no es válido.");
  return entries;
}

export function sortedRanking(entries, mode) {
  return entries.filter(entry => entry.mode === mode)
    .sort((a, b) => b.grade - a.grade || a.durationMs - b.durationMs || a.finishedAt - b.finishedAt)
    .slice(0, 50);
}

export function saveResult(storage, entry) {
  const entries = readRanking(storage);
  if (!entries.some(item => item.id === entry.id)) {
    entries.push(entry);
    const retained = ["easy", "matching", "written"].flatMap(mode => sortedRanking(entries, mode));
    storage.setItem(rankingKey, JSON.stringify(retained));
  }
}
