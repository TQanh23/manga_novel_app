# infra

Support files for the Docker Compose stack: service init scripts, seed data and, later,
Grafana dashboards. The Compose file itself sits at the repo root so `docker compose up`
runs from there.

## seed/sample_novel

The novel the seed step publishes for `author@example.com`, written for this project.

- `novel.toml`: title, synopsis, genres, tags, the chapter titles in order, and the glossary.
- `01.html` to `05.html`: one chapter each, as sanitized HTML, one paragraph per line.

Compose mounts `infra/seed` read-only into the `seed` container; the image does not contain it.
`python -m api.scripts.seed` on the host reads the same directory.

Rules for editing it, checked by `api/tests/test_seed_sample_novel.py`:

- The text stays consistent with the glossary. Planted contradictions for the AI eval go into
  copies under `eval/`, never here.
- Every glossary entry is named, by its name or an alias, in at least two chapters.
- Every chapter has at least eight paragraphs.
- The data passes the same validation as a request to the author API.

## seed/catalogue

Six short works, one directory each, that the seed step also publishes for `author@example.com`,
so the reader's homepage and the browse filters have content. Written for this project and
marked `is_sample`; they are not part of the AI eval set.

- `novel.toml`: title, synopsis, language, `status` (`ongoing` or `completed`), genres, tags and
  the chapter titles in order. No glossary.
- `01.html`, `02.html`: one chapter each, as sanitized HTML, one paragraph per line.

`api/tests/test_seed_catalogue.py` checks that the titles are distinct, the four content
languages are covered, every chapter is already clean HTML with at least six paragraphs, and
seeding twice adds nothing.
