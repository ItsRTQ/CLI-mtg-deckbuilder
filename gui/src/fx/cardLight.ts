// Card lighting model — the physical core of the foil FX system.
//
// The pointer does NOT carry a light around. It orients the CARD; a fixed
// virtual light then determines where the reflection lands and how strong
// the foil reads:
//
//   pointer (px,py in -1..1)
//     → card tilt (rotateX/rotateY)
//     → specular position (mirror of the fixed light: moves OPPOSITE the pointer)
//     → diffraction position/angle (same drift, slower rate)
//     → foil intensity (how far the card tilts TOWARD the light; 0 at rest)
//
// Values land as CSS custom properties on the .tilt element; styles.css
// registers them with @property so each layer eases at its own rate — the
// specular chases fast, the rainbow drifts slow, the texture barely moves.

export interface CardLightOpts {
  maxTilt: number;      // deg — grid tiles wobble more than the huge zoom card
  perspective: number;  // px
  scale?: number;       // grid tiles pop slightly on hover
}

// Calibration (conservative on purpose — printed cardstock, not a UI panel).
export const FX_CAL = {
  light: { x: -0.35, y: -0.55 }, // fixed virtual light: above the card, slightly left
  specTravel: 46,   // % of card the specular sweeps per unit of tilt
  foilRate: 0.45,   // the diffraction pattern drifts at 45% of the specular rate
  angleSwing: 16,   // deg the spectral-gradient angle shifts per unit of tilt
  restIntensity: 0, // neutral state: no reflection at all
};

const LIGHT = FX_CAL.light;
const NEUTRAL = {
  specX: 50 + LIGHT.x * 22,        // where the light would glint on a flat card
  specY: 42 + LIGHT.y * 22,
};

const reducedMotion =
  typeof matchMedia !== "undefined" &&
  matchMedia("(prefers-reduced-motion: reduce)").matches;

export function applyCardLight(
  el: HTMLElement, px: number, py: number, o: CardLightOpts,
): void {
  if (reducedMotion) {
    // no tilt, no chasing gradients — just a faint static metallic finish
    el.style.setProperty("--foil-intensity", "0.15");
    return;
  }
  el.style.transform =
    `perspective(${o.perspective}px) rotateY(${(px * o.maxTilt).toFixed(2)}deg) ` +
    `rotateX(${(-py * o.maxTilt).toFixed(2)}deg)` +
    (o.scale ? ` scale(${o.scale})` : "");

  // Reflection of the FIXED light in the tilted surface: tilting right sends
  // the glint left — the specular moves opposite the pointer, off-card at the
  // extremes, exactly like angling a real card out of the light.
  const specX = NEUTRAL.specX - px * FX_CAL.specTravel;
  const specY = NEUTRAL.specY - py * FX_CAL.specTravel;
  const foilX = 50 + (specX - 50) * FX_CAL.foilRate;
  const foilY = 50 + (specY - 50) * FX_CAL.foilRate;
  const angle = 115 + px * FX_CAL.angleSwing - py * FX_CAL.angleSwing * 0.6;

  // Intensity = amount of tilt × alignment with the light direction. Tilting
  // toward the light → strong foil; away → it dies down; flat → nothing.
  const t = Math.min(1, Math.hypot(px, py) * 1.35);
  const pm = Math.hypot(px, py), lm = Math.hypot(LIGHT.x, LIGHT.y);
  const align = pm > 0.02
    ? 0.5 + 0.5 * ((px * LIGHT.x + py * LIGHT.y) / (pm * lm))
    : 0.5;
  const intensity = t * (0.3 + 0.7 * align);

  const s = el.style;
  s.setProperty("--pointer-x", px.toFixed(3));
  s.setProperty("--pointer-y", py.toFixed(3));
  s.setProperty("--spec-x", `${specX.toFixed(1)}%`);
  s.setProperty("--spec-y", `${specY.toFixed(1)}%`);
  s.setProperty("--foil-x", `${foilX.toFixed(1)}%`);
  s.setProperty("--foil-y", `${foilY.toFixed(1)}%`);
  s.setProperty("--foil-angle", `${angle.toFixed(1)}deg`);
  s.setProperty("--foil-intensity", intensity.toFixed(3));
}

export function resetCardLight(el: HTMLElement): void {
  const s = el.style;
  el.style.transform = "";
  // intensity fades first (its transition is the slowest-out); the reflection
  // eases back toward the neutral light position instead of snapping
  s.setProperty("--foil-intensity", String(FX_CAL.restIntensity));
  s.setProperty("--pointer-x", "0");
  s.setProperty("--pointer-y", "0");
  s.setProperty("--spec-x", `${NEUTRAL.specX.toFixed(1)}%`);
  s.setProperty("--spec-y", `${NEUTRAL.specY.toFixed(1)}%`);
  s.setProperty("--foil-x", "50%");
  s.setProperty("--foil-y", "50%");
  s.setProperty("--foil-angle", "115deg");
}
