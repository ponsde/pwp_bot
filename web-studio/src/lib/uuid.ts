/** UUID v4 generator with fallback for non-secure contexts.
 *
 * `crypto.randomUUID()` is only available in secure contexts (HTTPS/localhost).
 * When served over plain HTTP + IP (e.g. dev/preview boxes) it is undefined,
 * so we fall back to a manual v4 using whatever randomness source exists.
 */
export function uuid(): string {
  const c = (globalThis as { crypto?: Crypto }).crypto
  if (c && typeof c.randomUUID === 'function') {
    return c.randomUUID()
  }
  const bytes = new Uint8Array(16)
  if (c && typeof c.getRandomValues === 'function') {
    c.getRandomValues(bytes)
  } else {
    for (let i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256)
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex: string[] = []
  for (const b of bytes) hex.push(b.toString(16).padStart(2, '0'))
  return (
    `${hex[0]}${hex[1]}${hex[2]}${hex[3]}-` +
    `${hex[4]}${hex[5]}-` +
    `${hex[6]}${hex[7]}-` +
    `${hex[8]}${hex[9]}-` +
    `${hex[10]}${hex[11]}${hex[12]}${hex[13]}${hex[14]}${hex[15]}`
  )
}
