# Zensical migration plan and look comparison

Status: plan only. Nothing here has been migrated. The live deploy still runs MkDocs.

Pinned version: `zensical==0.0.63`, the same pin the PR preview job already uses. Bump it deliberately, never float it.

## What was built and checked

Both theme variants built from the current `mkdocs.yml` (plus the tags page and author index from this PR) with `zensical==0.0.63` on Python 3.12, in a scratch venv outside the repo. The only config change per variant was adding `variant: modern` or `variant: classic` under `theme:`. Both builds finished with no error or warning output and produced 116 pages under `recipes/` (115 recipes plus Contact) plus `tags/` and `authors/`. Each variant was served locally and opened in Chrome to take the screenshots below.

`modern` is what Zensical uses when `variant` is unset.

## Screenshots

All are 1280x900 viewport shots, in `data/mason-browse-pages/`. The palette was switched with the site's own light/dark toggle.

| Page | Modern, light | Modern, dark | Classic, light | Classic, dark |
| ---- | ------------- | ------------ | -------------- | ------------- |
| Home | `zensical-modern-light-home.png` | `zensical-modern-dark-home.png` | `zensical-classic-light-home.png` | `zensical-classic-dark-home.png` |
| Recipe (Scott's Pot Roast) | `zensical-modern-light-recipe.png` | `zensical-modern-dark-recipe.png` | `zensical-classic-light-recipe.png` | `zensical-classic-dark-recipe.png` |
| Tags page | `zensical-modern-light-tags.png` | `zensical-modern-dark-tags.png` | `zensical-classic-light-tags.png` | `zensical-classic-dark-tags.png` |

Extra: `zensical-modern-search-janet.png` shows the Zensical search dialog for "janet".

Full paths, from the repo root:

- `data/mason-browse-pages/zensical-modern-light-home.png`
- `data/mason-browse-pages/zensical-modern-light-recipe.png`
- `data/mason-browse-pages/zensical-modern-light-tags.png`
- `data/mason-browse-pages/zensical-modern-dark-home.png`
- `data/mason-browse-pages/zensical-modern-dark-recipe.png`
- `data/mason-browse-pages/zensical-modern-dark-tags.png`
- `data/mason-browse-pages/zensical-classic-light-home.png`
- `data/mason-browse-pages/zensical-classic-light-recipe.png`
- `data/mason-browse-pages/zensical-classic-light-tags.png`
- `data/mason-browse-pages/zensical-classic-dark-home.png`
- `data/mason-browse-pages/zensical-classic-dark-recipe.png`
- `data/mason-browse-pages/zensical-classic-dark-tags.png`
- `data/mason-browse-pages/zensical-modern-search-janet.png`

## What classic and modern actually look like

Observed from the screenshots, not from documentation:

- **Classic** looks like today's site. The deep-orange header in light mode and the indigo header in dark mode carry over from the `palette` block in `mkdocs.yml`. Same Roboto type, same left navigation tree, same layout. The reader would notice little.
- **Modern** is a redesign. The header is a plain neutral bar, the `palette` primary and accent colours (deep-orange, indigo) are not applied, the type is a different sans, headings are bold, the active nav item is a highlighted pill, and the navigation shows only the current section's items instead of the whole tree. Dark mode is near-black rather than slate.
- Tag chips: on this site's recipe pages, MkDocs Material shows the tags (including the "By ..." author tag) above the title. In both Zensical variants the tag links are in the page but sit at the bottom of the page. So the byline is much less visible after the move, in either variant.

Recommendation for the captain to confirm: start on **classic**. It keeps the family's colours and the reader's habits, and it makes the migration a change of engine rather than a redesign. Switching to modern later is one line (`variant: modern`) and can be a separate decision.

## What the two cheap wins need to survive the move

Both wins in this PR use only documented Material features: the built-in `tags` plugin with a `<!-- material/tags -->` marker, and plain front-matter tags. There is no hook, no custom plugin, no theme override. That was deliberate, because Zensical maps a fixed list of MkDocs plugins to native code (its `config.py`) rather than running arbitrary hooks or plugins.

Observed on Zensical 0.0.63, using the pages from this PR:

| Feature | Survives? | Evidence |
| ------- | --------- | -------- |
| `docs/tags.md` listing every tag | Yes | Built page has all 33 tags (18 topic tags plus 15 `By` tags) |
| `docs/authors.md` with `include` filter | Yes | Built page has all 15 author headings; Janet Mason lists 22 recipes |
| "By Name" tag on each recipe page | Partly | Present in the HTML, but rendered at the page bottom, not above the title |
| Searching "janet" | Partly | Finds the Authors and Tags pages, with her recipe titles in the snippet. It does not return the individual recipe pages, which MkDocs search does |
| Nav entries `Tags` and `Authors` | Yes | Both appear in the Zensical nav |

What each would need:

1. **Tags and Authors pages**: nothing. Keep the marker comments and the `nav:` entries.
2. **Visible byline**: decide whether bottom-of-page is acceptable. If not, options are a one-line `*By Name*` under each recipe title in the Markdown (portable, searchable, but duplicates the author data), or wait for Zensical to expose tag placement. Do not build a hook.
3. **Search by name returning recipes**: the same one-line-under-title fix would also make each recipe page match the name in Zensical search. Decide at the byline step.
4. **The `author:` front matter** stays as the source of truth. The `By Name` tags duplicate it by hand, so a name in one place and not the other is possible in either engine. A small CI check comparing the two would be cheap but is not in this PR.

## Ordered migration steps

Each step lists what proves it, as a rendered page.

1. **Decide the variant and the byline question.** Captain looks at the screenshots above. Proof: a decision recorded in the PR for step 2.
2. **Add Zensical to a PR-only build with the real config** (done for the build; extend it to set `variant: classic`). Proof: download the `zensical-site` artifact from the PR, open `index.html`, a recipe, `tags/`, `authors/`. Nav, search box, light/dark toggle and the images in `assets/` all present.
3. **Compare page by page against the MkDocs build.** Proof: open the same ten pages in both (home, one recipe per category, one with an image, one with a co-author list, `tags/`, `authors/`, contact, a 404). Nothing missing, no broken image, no missing nav entry. The recipe count matches (115).
4. **Check the two git plugins.** `git-revision-date-localized` and `git-authors` are in `mkdocs.yml`. This plan did not verify what Zensical does with them. Proof: open a recipe in the Zensical build and check whether "last updated" or contributor information still shows as it does today. If it does not, that is a known loss; record it.
5. **Check search.** Proof: in the Zensical build search for a recipe title, an ingredient, "janet", and a tag word. Compare with MkDocs. The "janet" difference above is the known gap.
6. **Point the deploy at Zensical on a branch, not `main`.** Copy `build.yml` to a branch-only workflow that publishes to a test location (a fork's Pages or an artifact), leaving the live job alone. Proof: browse the served site on real URLs, not a local file, including deep links to recipes (bookmarks people already have).
7. **Cut over.** After the captain says so: change `build.yml` to install `zensical==<pin>` and run `zensical build`, keep `.nojekyll`, keep `force_orphan`. Update `requirements.txt` and the README install line in the same PR. Proof: the live URL renders the same recipes, an old recipe link still works, and the Pages deploy run is green.
8. **Remove MkDocs-only leftovers** after a week of stable running: MkDocs and Material from `requirements.txt` if still listed, the MegaLinter exclusion for `mkdocs.yml` if config moves to `zensical.toml`. Config conversion to `zensical.toml` is optional; Zensical reads `mkdocs.yml` today.

## What is lost and when

- **Step 2 or 3 (visible immediately in the preview)**: with `modern`, the orange/indigo colours and the full nav tree. With either variant, the byline chip moves to the bottom of recipe pages.
- **Step 5**: search by family name returns the Authors/Tags pages rather than each recipe.
- **Step 4 (unverified)**: possibly the "last updated" and contributor information from the two git plugins.
- **Never lost**: the 115 recipe files, the front matter, the images, the tags and authors pages.

Not lost by staying: nothing today, but Material for MkDocs is critical-fixes-only with a published end of life of 2027-05-05, and MkDocs core has had no stable release since August 2024.

## What should stop the work mid-flight

- Any recipe count other than 115 in the Zensical build.
- A broken or missing image, or an old recipe URL that no longer resolves.
- A new Zensical alpha changing the tags or search behaviour between two builds: stop, re-run steps 3 and 5 on the new pin, and only then continue.
- The git plugins failing the build rather than being ignored.
- The captain preferring a visible byline and there being no portable way to get it that does not need a hook or plugin.
- The pinned version disappearing from PyPI or being yanked.

## Rollback

Until step 7 nothing live changes. After step 7, reverting the `build.yml` PR and re-running the deploy returns the site to MkDocs, because the recipe files were never changed for Zensical.

## Not verified

- Behaviour of `git-revision-date-localized` and `git-authors` under Zensical.
- Deploy to real GitHub Pages under Zensical.
- Mobile layouts in either variant.
