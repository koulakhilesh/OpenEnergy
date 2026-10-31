/** Attribution for the data on a page, one click away instead of under every chart. */
export function Sources({ texts }: { texts: string[] }) {
  if (!texts.length) return null;
  return (
    <details className="sources">
      <summary>Sources and licences</summary>
      {[...new Set(texts)].map((text) => (
        <p key={text}>{text}</p>
      ))}
    </details>
  );
}
