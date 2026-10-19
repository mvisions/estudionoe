export function createMemoryVisitorStore() {
  const visitors = new Set();
  return {
    async record(id, day) {
      const key = `${day}_${id}`;
      if (visitors.has(key)) return false;
      visitors.add(key);
      return true;
    },
    async count(day) {
      return [...visitors].filter(key => key.startsWith(`${day}_`)).length;
    },
  };
}

export function createFirestoreVisitorStore(database) {
  const visitors = database.collection("siteAnalyticsVisitors");
  const totals = database.collection("siteAnalytics");

  return {
    async record(id, day) {
      const visitor = visitors.doc(`${day}_${id}`);
      const total = totals.doc(`dailyVisitors_${day}`);
      return database.runTransaction(async transaction => {
        const [existing, currentTotal] = await Promise.all([
          transaction.get(visitor),
          transaction.get(total),
        ]);
        if (existing.exists) return false;
        transaction.create(visitor, { firstSeenAt: new Date() });
        const count = currentTotal.exists ? currentTotal.data().count : 0;
        transaction.set(total, { count: count + 1 });
        return true;
      });
    },
    async count(day) {
      const total = totals.doc(`dailyVisitors_${day}`);
      const snapshot = await total.get();
      return snapshot.exists ? snapshot.data().count : 0;
    },
  };
}
