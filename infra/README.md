# infra

Support files for the Docker Compose stack: service init scripts, seed data and, later,
Grafana dashboards. The Compose file itself sits at the repo root so `docker compose up`
runs from there.

## seed/sample_novel

The novel the seed step publishes for `author@example.com`, written for this project.

- `novel.toml`: title, synopsis, genres, tags, the chapter titles in order, and the glossary.
- `01.md` to `05.md`: one chapter each, as Markdown. A blank line ends a paragraph.

Compose mounts `infra/seed` read-only into the `seed` container; the image does not contain it.
`python -m api.scripts.seed` on the host reads the same directory.

Rules for editing it, checked by `api/tests/test_seed_sample_novel.py`:

- The text stays consistent with the glossary. Planted contradictions for the AI eval go into
  copies under `eval/`, never here.
- Every glossary entry is named, by its name or an alias, in at least two chapters.
- Every chapter has at least eight paragraphs.
- The data passes the same validation as a request to the author API.
