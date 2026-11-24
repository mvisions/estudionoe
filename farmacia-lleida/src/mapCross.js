export function pharmacyCrossVertices(radius) {
  const arm = radius * 0.34;
  return [
    [-arm, -radius], [arm, -radius], [arm, -arm], [radius, -arm],
    [radius, arm], [arm, arm], [arm, radius], [-arm, radius],
    [-arm, arm], [-radius, arm], [-radius, -arm], [-arm, -arm],
  ];
}

export function pharmacyCrossPath(point, radius) {
  return pharmacyCrossVertices(radius)
    .map(([dx, dy], index) => `${index === 0 ? 'M' : 'L'}${point.x + dx},${point.y + dy}`)
    .join(' ') + ' Z';
}
