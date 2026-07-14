import { useState } from "react";

// Mana symbols as inline SVGs, bundled locally in /mana/<SYMBOL>.svg (offline —
// no CDN). Token -> filename: strip braces, drop the hybrid slash ({W/U} -> WU).
const TOKEN_RE = /\{[^}]+\}/g;

export function symbolSrc(token: string): string {
  return `/mana/${token.slice(1, -1).replace(/\//g, "")}.svg`;
}

function Symbol({ token }: { token: string }) {
  const [broken, setBroken] = useState(false);
  if (broken) return <>{token}</>;   // unknown symbol -> keep the text form
  return (
    <img className="mana-symbol" src={symbolSrc(token)} alt={token}
         title={token} onError={() => setBroken(true)} />
  );
}

// A mana cost string ("{2}{R}{R}") rendered as symbol images.
export default function ManaCost({ cost }: { cost?: string | null }) {
  if (!cost) return null;
  const tokens = cost.match(TOKEN_RE);
  if (!tokens) return <>{cost}</>;
  return (
    <span className="mana">
      {tokens.map((t, i) => <Symbol key={i} token={t} />)}
    </span>
  );
}

// Free text with embedded symbols ("{T}: Add {R}.") -> text + inline images.
export function TextWithMana({ text }: { text?: string | null }) {
  if (!text) return null;
  const parts = text.split(TOKEN_RE);
  const tokens = text.match(TOKEN_RE) ?? [];
  return (
    <>
      {parts.map((p, i) => (
        <span key={i}>
          {p}
          {i < tokens.length && <Symbol token={tokens[i]} />}
        </span>
      ))}
    </>
  );
}

// For HTML strings (rendered markdown): replace {X} tokens with <img> tags.
export function manaHtml(html: string): string {
  return html.replace(TOKEN_RE, (t) =>
    `<img class="mana-symbol" src="${symbolSrc(t)}" alt="${t}" title="${t}">`);
}
