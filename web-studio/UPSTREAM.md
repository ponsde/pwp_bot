# web-studio — upstream sync

The `web-studio/` directory is vendored from
[Ferry-200/OpenViking](https://github.com/Ferry-200/OpenViking), branch
`new-frontend`, as the base of our frontend.

## Files we modified from upstream (check on each pull)

- `src/routes/sessions/route.tsx` — replaced their placeholder with AskPage.
- `index.html` — `<title>` set to "财报智能问数".
- `src/components/app-shell.tsx` — removed the SidebarFooter Connection
  button + its imports. Embedded OV is same-origin, the baseUrl dialog
  is irrelevant. Search for `taidi-overlay:` comments to spot our hunks.

All other additions live under paths upstream leaves as `.gitkeep`:
`src/routes/sessions/-components/`, `-hooks/`, `-lib/`, etc.

- Upstream snapshot commit: see `.upstream-commit`
- License: `LICENSE.upstream` (upstream's license, vendored alongside)

## Sync strategy

Upstream is still evolving. To keep merges cheap we keep our own edits to
**exactly one of their files**:

- `src/routes/sessions/route.tsx` — they ship a placeholder specifically to
  let downstream projects plug in a bot; we replaced it with our ask page.

Everything else we add lives in new paths they don't touch:

- `src/routes/sessions/-components/` — our chat UI components (they leave
  this as empty `.gitkeep`s by convention)
- `src/routes/sessions/-hooks/`, `-lib/`, `-types/`, `-constants/` — same
- `src/api/` — our FastAPI client (new directory)

Also one-line edits:

- `index.html` `<title>` — page title

## Updating

Run the helper from repo root:

```bash
scripts/update_web_studio.sh
```

It sparse-checks out upstream `web-studio/` at `new-frontend`, rsyncs it over
ours, and warns about conflicts on the overlay file listed above.

After running, diff and re-apply our overlay changes by hand if the helper
reports conflicts.
