# Where this pack came from

Copied from `github.com/mffcampos-cmyk/ODF-Validator` at commit
`e0a71e4f6c0d0f6e504fcd004a3acacbc4a4f520`, taking exactly the files git tracks under `Rules/`.
`pyproject.toml` pins the same commit for the engine; if you change one,
change the other.

The pack's own files have not changed since `c9a5b8db`, the commit they were
first taken from. The pin moved because the engine's Data Dictionary parser
was fixed: a message section that never states its DocumentType no longer
inherits the previous message, which is what made ARC's teams table read as
"DT_PARTIC requires Competition/Team (1,N)" and made every conforming
DT_PARTIC message fail.

## What is here

- `pack.yaml` — pack version, root XSD, the upstream index URL, and the
  `length_exempt` list.
- `rules/`, `Disciplines/<CODE>/rules/` — the authored validation rules.
- `xsd/` — the SYOG2026 schema.

## The schema is not byte-identical to the IOC's published copy

It carries two deliberate changes, both inherited from the validator and
recorded here so a reader of this repository does not have to find the other
one to learn about them:

1. **`RecordBrokenType` → `pictureType`.** The published `odf2-structure.xsd`
   does not compile as downloaded: element `ImageData` in
   `officialCommunicationType` references a type the schema never defines.
   `pictureType` is what the schema's other `ImageData` element uses.
2. **Header `@Time` typed as `odfTimeType`** (`[0-9]{9}`), where the published
   schema leaves it unconstrained. Stricter than the official schema, not a
   correction to it.

The IOC will publish no further schema for the Sport Youth Olympic Games 2026,
so this copy is final.

## Why the pin matters

"This generator's output validates clean" is a claim about one revision of the
engine and its rules, not about the validator in general. Two changes on the
way to this one moved what clean means, and both are worth knowing before
trusting an older result:

- Discipline-RSC scoping was wrong at dispatch until 2026-08-28, and while it
  was, **none of the 52 discipline-scoped rules fired** on a conforming
  message. Output validated against an engine from before that fix was checked
  by far fewer rules than it appeared to be.
- After it, the pipeline also runs `missing_mandatory_attrs()` on every
  message, reporting `CORE_DD_MANDATORY_ATTR` for the (element, attribute)
  pairs the Data Dictionaries mark mandatory where the XSD is silent, plus the
  per-`@Code` conditional obligations. That check did not exist when earlier
  clean results were recorded. This project's output passes it — but passing
  it was never what those earlier results claimed.

The commit named at the top of this file is the revision the current claim is
measured against. That is the whole reason it is pinned rather than tracked.

## What is NOT here

The Common Codes workbook and the 25 Data Dictionaries. They are published by
the IOC, they change, and they are not ours to redistribute. Fetch them:

    python -m generator.sources

Until you do, the pack has no code tables and the application will not start —
by design, with an error that says so, rather than an empty discipline
dropdown.

## Refreshing against a newer validator

From a checkout of the validator, extract the pack from a **commit**, never
from the working tree:

    git archive <new-commit> Rules | tar -x -C <this-repository>

The distinction is not pedantry. A validator checkout in normal use carries
uncommitted work — when this pack was vendored, four files under `Rules/`
were modified in the source checkout and belonged to something unfinished.
Copying what `git ls-files` lists reads those modified files off disk and
vendors them, while the provenance line below still names a commit that does
not contain them. The record would be wrong in a way nothing would catch.

Then update the commit named above and the `odf-validator` pin in
`pyproject.toml` — they must name the same commit — and run the test suite. A
pack and an engine from different revisions is exactly the situation the pin
exists to make visible.
