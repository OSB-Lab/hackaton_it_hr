// Графика «линии объединяют точки» из брендбука ФСП, нарисованная как сеть:
// кандидаты (белые точки), работодатель (красная точка) и найденная связь между ними.
// Декоративный элемент, поэтому скрыт от скринридеров.

// [x, y, радиус]
const NODES: [number, number, number][] = [
  [70, 90, 5],
  [170, 210, 8],
  [80, 330, 5],
  [220, 430, 6],
  [300, 80, 6],
  [390, 210, 11],
  [300, 330, 7],
  [470, 440, 5],
  [540, 110, 6],
  [520, 300, 8],
  [230, 20, 4],
  [590, 420, 4],
  [440, 60, 4],
  [30, 210, 4],
];

const EDGES: [number, number][] = [
  [0, 1], [1, 2], [1, 4], [1, 6], [2, 3], [3, 6], [4, 5], [4, 10], [4, 12], [5, 6],
  [5, 8], [5, 9], [6, 7], [7, 9], [8, 12], [9, 11], [0, 13], [13, 1], [7, 11], [3, 7],
];

// Путь от работодателя (узел 5) к найденному кандидату (узел 1).
const FOUND_PATH: [number, number][] = [
  [5, 6],
  [6, 1],
];

const EMPLOYER_NODE = 5;

// tone="dark" — белые линии и точки (для фиолетового/тёмного фона);
// tone="light" — фиолетовые линии и точки (для светлого фона, как в брендбуке).
export function NetworkArt({
  className = '',
  tone = 'dark',
}: {
  className?: string;
  tone?: 'dark' | 'light';
}) {
  const node = tone === 'dark' ? '#ffffff' : '#402FFF';
  const edge = tone === 'dark' ? '#ffffff' : '#402FFF';
  const edgeOpacity = tone === 'dark' ? 0.22 : 0.3;
  return (
    <svg
      viewBox="0 0 600 520"
      preserveAspectRatio="xMidYMid slice"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      {EDGES.map(([a, b]) => (
        <line
          key={`${a}-${b}`}
          x1={NODES[a][0]}
          y1={NODES[a][1]}
          x2={NODES[b][0]}
          y2={NODES[b][1]}
          stroke={edge}
          strokeOpacity={edgeOpacity}
        />
      ))}
      {FOUND_PATH.map(([a, b]) => (
        <line
          key={`found-${a}-${b}`}
          x1={NODES[a][0]}
          y1={NODES[a][1]}
          x2={NODES[b][0]}
          y2={NODES[b][1]}
          stroke={edge}
          strokeWidth="2.5"
        />
      ))}
      {NODES.map(([x, y, r], index) =>
        index === EMPLOYER_NODE ? (
          <g key={index}>
            <circle cx={x} cy={y} r={r + 9} stroke={node} strokeOpacity="0.5" />
            <circle cx={x} cy={y} r={r} fill="#EC1D35" />
          </g>
        ) : (
          <circle key={index} cx={x} cy={y} r={r} fill={node} fillOpacity={r > 5 ? 0.95 : 0.5} />
        ),
      )}
    </svg>
  );
}
