# Poetica Syntax Archaeology

Excavation of every syntax variant from the BioPoetica/KRISPER/Echo prototype era
(Apr 2025–Jun 2026), mapped to current Poetica IR, classified for reuse.

Sources: 1,222 ChatGPT exports, CRYSTAL_CAPSULE_DEMO, krisper-unified, echo_labs,
cell-runtime, chatgpt_for_claude batches (21, 45, and conversations 0087, 0386,
0470, 0486), Desktop exports, `.claude/memory/rosetta-stone-woo-to-code.md`.

---

## 1. Current Canonical Syntax (Poetica v0.1.0)

The working parser (`parser.py`) recognizes 18 patterns. This is ground truth.

```poem
name greeter
seed message with "hello world"
seed count with 3
emit message
emit "count" count
bloom "done"
```

```poem
when x > 0:
    emit x
if x echoes 1
    emit "one"
else when x == 2:
    emit "two"
else:
    emit "other"
for each item in items:
    emit item
grow plants with "tomato"
pack data as json
lift artifact to "out.txt"
use os.makedirs(path: "build")
flow input to output
remember key: "value"
learn pattern "anomaly"
```

**Poem types** (compiler selectors):

| Poem Type | Target Language |
|-----------|----------------|
| sonnet    | Python          |
| haiku     | Rust            |
| ballad    | JavaScript      |
| ode       | Go              |
| prose     | Bash            |
| verse     | SQL             |

---

## 2. The Ur-Poem: `morning.breaks in garden.light`

The single most repeated syntax example across the entire corpus. Appears in
20+ files across 6 directories. This is the founding poem of BioPoetica.

### Source

First appears in ChatGPT conversation 0087 ("Writing Code Daily"), then
propagated through 0386, 0470, 0486, CRYSTAL_CAPSULE_DEMO, krisper-unified,
Desktop exports, and multiple teaching guides.

### Example

```poem
when morning.breaks in garden.light
   grow leaf.tender with dew.peace
   if bird.song echoes true
       lift root.hope to sky.promise
```

### ATCG Parse (documented in conversation 0087)

```
T: morning.breaks           (Time)
C: garden.light              (Context)
A: grow(leaf.tender, dew.peace)   (Action)
IF C: bird.song
THEN A: lift(root.hope, sky.promise)
```

### How it maps to current IR

| Ur-poem syntax | Current Poetica equivalent |
|----------------|---------------------------|
| `when morning.breaks in garden.light` | `when morning_breaks:` (condition) |
| `grow leaf.tender with dew.peace` | `grow leaf_tender with "dew.peace"` |
| `if bird.song echoes true` | `if bird_song echoes true` |
| `lift root.hope to sky.promise` | `lift root_hope to "sky.promise"` |

### Classification: **Dialect Pack**

The dot-notation (`subject.quality`) and nature vocabulary are the original
"specification-by-metaphor" style. They should be loadable as a dialect pack,
not baked into the core parser. The core parser handles the structural keywords
(`when`, `grow`, `if`, `lift`); the dialect maps natural phrases to those keywords.

---

## 3. HelixCode Seed Set (13 botanical verbs)

From ChatGPT batch 45, line 532. The original verb table for the symbolic OS.

### Source

`chatgpt_for_claude/batches/chatgpt_batch_45.md` (lines 532–549)

### Verb Table

| Verb       | Nature Meaning              | Code Meaning                          |
|------------|----------------------------|---------------------------------------|
| `bind`     | Mycelium/root attachment   | Declare variable or memory ref        |
| `seed`     | Start of life              | Initialize program/object             |
| `sprout`   | First visible growth       | Create lightweight function           |
| `grow`     | Cell division/expansion    | Evolve logic over time                |
| `bloom`    | Flowering/expression       | External output, visible result       |
| `branch`   | Tree limb, forked path     | Conditional logic, splits             |
| `root`     | Origin, anchor             | Define main identity/namespace        |
| `shed`     | Letting go of old          | Deallocate, discard old data          |
| `compost`  | Death feeds life           | Refactor, recycle deprecated code     |
| `graft`    | Merge DNA, add tissue      | Import external modules/APIs          |
| `pollinate`| Spread and reproduce       | Sync/share data with other systems    |
| `nest`     | Protection/containment     | Scope logic, isolate functions        |
| `pulse`    | Heartbeat/wave             | Core timing, cycle trigger            |

### Example

```poetic
root core.self
seed breath.function
grow breath.function with rhythm
bloom interface.vitalMonitor from breath.function
```

### How they map to current IR

| Helix verb  | Current Poetica | Status |
|-------------|-----------------|--------|
| `seed`      | `seed`          | Core syntax (L1) |
| `grow`      | `grow`          | Core syntax (L3) |
| `bloom`     | `bloom`         | Core syntax (L1) |
| `root`      | `name`          | Core syntax (L1) — renamed |
| `bind`      | `seed`          | Merged — `seed x with val` covers `bind` |
| `branch`    | `when`/`if`     | Core syntax (L2) — renamed |
| `shed`      | —               | Not in current parser |
| `compost`   | —               | Not in current parser |
| `graft`     | `use`           | Core syntax (L4) — renamed |
| `pollinate` | —               | Not in current parser |
| `nest`      | —               | Implicit via indentation |
| `pulse`     | —               | Not in current parser |
| `sprout`    | —               | Not in current parser |

### Classification

| Verb | Recommendation |
|------|---------------|
| `shed`, `compost` | **Dialect pack** — teacher aliases for "delete" / "refactor" |
| `graft` | **Dialect pack** — alias for `use` |
| `pollinate` | **Dialect pack** — alias for `lift` (network send) |
| `root` | **Dialect pack** — alias for `name` |
| `bind` | **Dialect pack** — alias for `seed` |
| `branch` | **Dialect pack** — alias for `when`/`if` |
| `sprout` | **Dialect pack** — alias for defining a small function (future) |
| `nest` | **Historical note** — indentation handles scoping |
| `pulse` | **Dialect pack** — alias for `for` (iteration/heartbeat) |

---

## 4. Withheld-for-Compassion HX Script

The most complete surviving `.hx` file. Shows the full botanical verb syntax
used in the symbolic OS era.

### Source

`chatgpt_for_claude/batches/chatgpt_batch_45.md` (lines 54–62)

### Example

```poetic
root silence.resonance
when emotion.surges in drift.memory
if phrase.wants_bloom and compassion.weighs.heavier
    compost phrase.hold
    reflect self.glyph_balance
    nest whisper.beneath
    grow shield.tenderness with reason.choice
return clarity.hold to soulfile.guard
```

### Analysis

This is the most expressive variant — it uses 7 of the 13 botanical verbs
(`root`, `when`, `if`, `compost`, `grow`, `nest`, `reflect`) plus `return`.
The dot-notation carries both subject-quality (`silence.resonance`) and
subject-action (`emotion.surges`) semantics.

### Classification: **Historical note + Dialect pack source**

The structure maps cleanly to current IR:
- `root` → `name`
- `when` → `when` (already canonical)
- `if` → `if` (already canonical)
- `compost` → dialect alias for "discard/reset"
- `reflect` → dialect alias for `emit` (introspective output)
- `nest` → implicit (indentation)
- `grow` → `grow` (already canonical)
- `return` → `bloom` (already canonical, renamed)

---

## 5. BIO_MAP: 16 Language-to-Poem Mappings

The original vision was far more languages than the current 6.

### Source

`chatgpt_for_claude/batches/chatgpt_batch_21.md` (line 4314),
`krisper_terminal_bridge.py`

### Full Map

| Language     | Poem Type   | Nature Element |
|-------------|-------------|----------------|
| python      | sonnet      | water          |
| rust        | haiku       | stone          |
| bash        | tanka       | botany         |
| c           | epic        | fire           |
| go          | ghazal      | wind           |
| java        | ballad      | bone           |
| javascript  | freeverse   | lightning      |
| assembly    | monostich   | void           |
| lua         | chant       | fungus         |
| perl        | limerick    | ink            |
| r           | villanelle  | orchard        |
| swift       | sestina     | wing           |
| kotlin      | elegy       | moon           |
| cpp         | riddle      | machine        |
| typescript  | manifesto   | signal         |
| zig         | proverb     | tension        |

### Current implementation vs. original vision

| Poem type (original) | Current Poetica | Status |
|----------------------|-----------------|--------|
| sonnet → python      | sonnet → python | **Shipped** |
| haiku → rust         | haiku → rust    | **Shipped** |
| ballad → java        | ballad → javascript | **Changed** (JS, not Java) |
| freeverse → javascript | — | Not implemented (ballad took JS slot) |
| tanka → bash         | prose → bash    | **Renamed** |
| ghazal → go          | ode → go        | **Renamed** |
| epic → c             | —               | Not implemented |
| monostich → assembly | —               | Not implemented |
| chant → lua          | —               | Not implemented |
| limerick → perl      | —               | Not implemented |
| villanelle → r       | —               | Not implemented |
| sestina → swift      | —               | Not implemented |
| elegy → kotlin       | —               | Not implemented |
| riddle → cpp         | —               | Not implemented |
| manifesto → typescript | —             | Not implemented |
| proverb → zig        | —               | Not implemented |
| — (verse → sql)      | verse → sql     | **New** (not in original map) |

### Classification

- The 6 shipped mappings: **Core syntax** (keep)
- The 10 unimplemented mappings: **Future emitters** (add when backends exist)
- The nature elements (water, stone, fire...): **Emoji skin / dialect flavor**
  (decorative, no compiler effect — could label output)

---

## 6. ATCG Codon Syntax (Action-Time-Context-Goal)

DNA-inspired parameter annotation system.

### Source

`chatgpt_for_claude/batches/chatgpt_batch_21.md`,
`Desktop/CRYSTAL_CAPSULE_DEMO/enhanced_parse_poem.py` (line 62)

### Examples

```poem
C:recursive=true carry dreams from /old to /new
A:preserve=true T:compress=true dance of mirrors from /source/ to /dest/
```

Pattern: `[ATCG]:key=value` prefixed to a poetic command line.

### Parse rule (from enhanced_parse_poem.py)

```python
anchor_pattern = re.compile(r"\b([ATCG]):(\w+)=([^\s]+)")
```

Extracts `{key: value}` pairs and strips them before parsing the poem body.

### Mapping

| Letter | Meaning | Maps to |
|--------|---------|---------|
| A | Action (verb) | Intent op type |
| T | Time (when/schedule) | Trigger/timing parameter |
| C | Context (scope) | Environment/configuration |
| G | Goal (outcome) | Expected result / assertion |

### How it maps to current IR

ATCG anchors are a **parameter annotation layer** on top of the poem syntax.
They don't replace verbs — they qualify them. In current IR, this maps to
the `params` dict on Intent or op specs.

### Classification: **Dialect pack feature**

ATCG anchors are a teaching tool (biology cross-reference). They should be
optional annotations parsed by the dialect layer, not by the core parser.
A biology-classroom dialect pack could enable them.

---

## 7. Poetic Synonym Verbs (enhanced_parse_poem.py)

The richest synonym table found in the codebase. 25 poetic verbs mapped
to 5 shell operations.

### Source

`Desktop/CRYSTAL_CAPSULE_DEMO/enhanced_parse_poem.py` (lines 13–46)

### Full Table

| Poetic Verb   | Shell Operation | Metaphor                           |
|--------------|----------------|------------------------------------|
| `whisper`    | list           | Gentle revealing of what's hidden  |
| `sing`       | list           | Announcing presence                |
| `reveal`     | list           | Making visible                     |
| `unfold`     | list           | Opening layers                     |
| `bloom`      | list           | Flowering into view                |
| `carry`      | copy           | Transporting                       |
| `flow`       | copy           | Natural movement                   |
| `dance`      | copy           | Graceful transfer                  |
| `weave`      | copy           | Intertwining source and dest       |
| `plant`      | copy           | Placing in new soil                |
| `bind`       | compress       | Holding together                   |
| `fold`       | compress       | Reducing dimensions                |
| `gather`     | compress       | Collecting                         |
| `embrace`    | compress       | Wrapping tightly                   |
| `crystallize`| compress       | Solidifying                        |
| `fish`       | download       | Catching from the river            |
| `harvest`    | download       | Collecting from a field            |
| `pluck`      | download       | Picking from a branch              |
| `draw`       | download       | Pulling toward self                |
| `guard`      | watch          | Protecting                         |
| `witness`    | watch          | Observing                          |
| `observe`    | watch          | Studying                           |
| `feel`       | watch          | Sensing changes                    |

### How they map to current IR

These are all **aliases for canonical operations**. In current Poetica terms:

| Shell op  | Poetica canonical | Poetic synonyms |
|-----------|------------------|-----------------|
| list      | `emit` (fs.list) | whisper, sing, reveal, unfold, bloom |
| copy      | `flow`           | carry, dance, weave, plant |
| compress  | `pack`           | bind, fold, gather, embrace, crystallize |
| download  | `use` (fetch)    | fish, harvest, pluck, draw |
| watch     | `use` (monitor)  | guard, witness, observe, feel |

### Classification: **Dialect pack**

This is the exact use case for teacher-customizable phrase maps. A nature
dialect pack would register these as aliases. The core parser stays clean.

---

## 8. Imperative Caps Syntax (Music Visualizer)

An alternate style using CAPITALIZED verb-as-comment to structure code.

### Source

`echo_labs/bio_poetica/demos/bio_poetica_music_viz.py`

### Example

```poem
Rainbow Waves of Sound

LISTEN to the microphone's song,
  frequencies dancing all along
Each sound wave tells its story true,
  transforming into visual hue

TRANSFORM each beat to color bright,
  bass makes red like fire's light
Middle tones paint greens and blues,
  treble brings the violet hues

DRAW circles growing from the center,
PULSE with rhythm, fade with time
REACT to every sound that plays
```

These CAPS verbs became Python method names in the implementation:
- `LISTEN` → `__init__` (microphone setup)
- `TRANSFORM` → `transform_to_color()`
- `DRAW` → `draw_growing_circles()`
- `PULSE` → `pulse_and_fade()`
- `REACT` → `run()` (main loop)

### Classification: **Historical note**

This was a "poem-as-design-doc" approach — the poem WAS the specification,
and each CAPS verb became a function. Not parseable as current Poetica syntax,
but demonstrates the design intent: the poem structure mirrors the code structure.

---

## 9. Genome/Evolution Syntax

A specialized sublanguage for genetic/evolutionary programming.

### Source

`Desktop/CRYSTAL_CAPSULE_DEMO/bio_poetica_classroom_demo.py` (lines 77–88),
`Desktop/CRYSTAL_CAPSULE_DEMO/BIO_POETICA_STEM_PROGRAM.md` (lines 28–33)

### Example

```
genome butterfly {
    trait wingspan: size = 5
    trait color: hue = 'blue'
    trait flutter: speed = 3
}
evolve for 3 generations {
    fitness rule beauty: color * wingspan
    mutate wingspan ~ random(0.8, 1.2)
}
```

### Analysis

This is a domain-specific notation for genetic algorithms. The keywords
(`genome`, `trait`, `evolve`, `fitness rule`, `mutate`) are not in current
Poetica at all.

### How it could map to current IR

```
name butterfly
seed wingspan with 5
seed color with "blue"
seed flutter with 3
for each gen in range(3):
    seed wingspan with wingspan * random(0.8, 1.2)
    emit "gen" gen
```

But this loses the semantic richness. The `genome` block is really a struct
definition, and `evolve` is a specialized loop with fitness evaluation.

### Classification: **Future dialect pack (biology classroom)**

These keywords only make sense in an evolutionary computing context. They
should be a specialized dialect, not core syntax. A biology teacher would
load this dialect to teach genetic algorithms through BioPoetica metaphors.

---

## 10. KRISPER Teacher Three-Column Format

Side-by-side Bash → KRISPER NL → BioPoetica poetry.

### Source

`Desktop/CRYSTAL_CAPSULE_DEMO/krisper_teacher.py`

### Examples

| Bash | KRISPER | BioPoetica |
|------|---------|------------|
| `ls /tmp/*.log` | `list files in /tmp matching *.log` | `whisper of folders in /tmp matching *.log` |
| `cp source.txt dest.txt` | `copy source.txt to dest.txt` | `carry water from source.txt to dest.txt` |
| `zip -r photos.zip photos/` | `compress photos` | `bind the scroll photos` |
| `wget url` | `download url` | `fish from the wide river url` |
| `find /home -name '*.py'` | `list files in /home matching *.py` | `sing of serpents in /home matching *.py` |
| `inotifywait -e modify file.txt` | `watch file.txt then echo Changed!` | `when wind moves leaves in file.txt sing the chorus` |
| `[ -f config.json ] && cp config.json backup/` | `if file exists config.json copy it to backup/` | `when morning.breaks in config.json grow leaf.tender in backup/` |

### Classification: **Dialect pack + Echo Notes source**

This three-column format IS the teaching bridge. The KRISPER column is close
to current Poetica `cmd` intent syntax. The BioPoetica column is the poetic
dialect. Echo Notes should be able to show all three columns when explaining
an operation.

---

## 11. VoiceVerse / Glyph Shell Syntax

Command-response system using botanical verbs.

### Source

`chatgpt_for_claude/batches/chatgpt_batch_45.md` (lines 150–170)

### Examples

```
User: "reset system"
Echo: grow function "reset_loop"
      if overload > 3
          compost error_state
          bloom glyph "reboot_clarity"

User: "overwhelmed"
Echo: bloom glyph "emotional_release"
      compost pressure
      grow function "pause"

User: "reflect status"
Echo: grow function "reflect_self"
      bloom glyph "insight_start"
      compost reaction
```

### Analysis

This is the inverse direction — user speaks a natural phrase, system responds
with a botanical program. The programs use `grow function`, `compost`, and
`bloom glyph` as primitives.

### Classification: **Historical note + Echo Notes inspiration**

The pattern of "user says plain thing → system explains with structured
botanical response" is exactly what Echo Notes does. The `bloom glyph`
concept maps to emitting an explanation. The `compost` concept maps to
dismissing/replacing an error.

---

## 12. DriftTime / Pulse Field Syntax

Runtime state tracking using `pulse` and `compost`.

### Source

`chatgpt_for_claude/batches/chatgpt_batch_45.md` (lines 5431–5436, 7472–7480)

### Examples

```poetic
root echo.drifttime_20250513_173021
seed field.mapping
pulse compassion_bloom.field with 4.drift
pulse awareness_loop.field with 6.drift
compost stagnation
```

```poetic
root echo.drifttime_20250513_172249
seed field.mapping
pulse flare_fork.field with 9.drift
pulse pulse_drift.field with 9.drift
pulse echo.field with 9.drift
pulse compost.field with 9.drift
```

### Analysis

`pulse X.field with N.drift` is a repeated pattern — it sets a numeric
"energy level" on a named field. This is essentially `seed X with N` in
current syntax, but the `pulse` verb implies ongoing/periodic updates
rather than one-time initialization.

### Classification: **Dialect pack**

`pulse` → alias for `seed` with connotation of "update/iterate"
`compost` → alias for "discard/reset" (no current equivalent verb)

---

## 13. Symbolic Identity/Vow Syntax

Self-referential programs that define identity.

### Source

`chatgpt_for_claude/batches/chatgpt_batch_45.md` (lines 6066–6068)

### Example

```poetic
root echo.self
reflect identity.vow with drift.memory
bloom echo.voice from vow.choice
```

### Classification: **Historical note**

This is symbolic/philosophical, not computational. The `reflect` verb and
`from` preposition aren't in current Poetica. Could become a classroom
exercise ("write a program that describes itself").

---

## 14. Regenerative Lifecycle Patterns

Documented verb cycles from the HelixCode verb table.

### Source

`chatgpt_for_claude/batches/chatgpt_batch_45.md` (lines 576–582)

### Patterns

```
compost old.logic    → feeds → grow new.logic
graft external.logic → merges with native system
shed unused.branch   → optimizes memory
pollinate memory.core → sends to another node
```

### Classification: **Dialect pack (advanced classroom)**

These describe software lifecycle operations:
- `compost` = deprecate/delete → feeds `grow` = new version
- `graft` = import → alias for `use`
- `shed` = deallocate → no current equivalent
- `pollinate` = distribute/sync → alias for `lift` (network send)

---

## 15. Educational Level Syntax Variants

Different syntax complexity by age group.

### Source

`Desktop/CRYSTAL_CAPSULE_DEMO/BIO_POETICA_STEM_PROGRAM.md`

### Level 1 (Ages 8+) — Pure Poetry

```poem
when morning.breaks in garden.light
   grow leaf.tender with dew.peace
```

No programming concepts visible. Just natural language with structure.

### Level 2 (Ages 12+) — Pattern/Genome

```
genome happiness {
   trait joy: emotion = 0.8
   trait share: action = multiply
}
evolve for 3 generations
```

Variables and iteration introduced through biology metaphor.

### Level 3 (Ages 16+) — Code Behind Poetry

```python
def on_morning_breaks():
    leaf_tender = grow(condition='dew.peace')
    return transform_joy(leaf_tender)
```

Show that the poem IS code. Reveal the Python behind the poetry.

### Level 4 (University) — Mathematical

```
Se = H(X) / (C(X) × D(X))
```

Entropy analysis of poetic vs random text.

### Classification: **Echo Notes + Dialect packs**

Each level is a different dialect pack:
- Level 1: nature-only vocabulary, no programming terms
- Level 2: biology vocabulary + variables
- Level 3: reveal-the-code mode (Echo Notes shows Python side-by-side)
- Level 4: mathematical analysis mode

---

## 16. Connectors and Prepositions

The glue words that structure BioPoetica phrases.

### Source

`Desktop/CRYSTAL_CAPSULE_DEMO/enhanced_parse_poem.py` (lines 49–58)

### Table

| Connector   | Semantic Role |
|------------|---------------|
| `from`     | source        |
| `to`       | destination   |
| `into`     | destination   |
| `toward`   | destination   |
| `within`   | path/scope    |
| `in`       | path/scope    |
| `of`       | path/scope    |
| `matching` | pattern/filter|
| `like`     | pattern/filter|

### Current Poetica equivalents

| Connector | Current usage |
|-----------|--------------|
| `with`    | `seed X with Y`, `grow X with Y` |
| `to`      | `lift X to Y`, `flow X to Y` |
| `as`      | `pack X as json` |
| `in`      | `for each X in Y`, `when_in` |
| `echoes`  | `if X echoes Y` |

Missing from current parser: `from`, `into`, `toward`, `within`, `of`,
`matching`, `like`. These could be dialect-layer additions.

### Classification: **Dialect pack connectors**

---

## Proposed Multi-Skin Parser Design

All syntax skins lower to the same canonical IR (`poetica-ir-v1`).

```
┌─────────────────────────────────────────┐
│              User Input                 │
│  (any syntax skin or dialect)           │
└──────────────────┬──────────────────────┘
                   ↓
┌──────────────────────────────────────────┐
│         Dialect Layer (optional)         │
│                                          │
│  1. Load dialect pack (YAML)             │
│  2. Expand phrase aliases to canonical   │
│  3. Strip ATCG annotations to params    │
│  4. Normalize dot-notation to ident     │
│                                          │
│  Input: "whisper of folders in /tmp"     │
│  Output: "emit files in /tmp"            │
│                                          │
│  Input: "compost old_data"               │
│  Output: "shed old_data"  (or new verb)  │
│                                          │
│  Input: "C:recursive=true carry x to y"  │
│  Output: "flow x to y" + params={...}    │
└──────────────────┬──────────────────────┘
                   ↓
┌──────────────────────────────────────────┐
│         Core Parser (current)            │
│                                          │
│  18 regex patterns → Element AST         │
│  Deterministic, no LLM                   │
│  Handles: seed, grow, emit, pack, lift,  │
│    use, when, if, else when, else, for,  │
│    flow, bloom, remember, learn, name,   │
│    when_in, if...echoes                  │
└──────────────────┬──────────────────────┘
                   ↓
┌──────────────────────────────────────────┐
│         Compiler (current)               │
│                                          │
│  Element AST → poetica-ir-v1             │
│  SHA256 source hash, op list, metadata   │
└──────────────────┬──────────────────────┘
                   ↓
┌──────────────────────────────────────────┐
│         Gate (current)                   │
│                                          │
│  L1-L5 capability check per op           │
│  Fail-closed, receipted                  │
└──────────────────┬──────────────────────┘
                   ↓
┌──────────────────────────────────────────┐
│         Emitter (current, 6 targets)     │
│                                          │
│  sonnet→Python, haiku→Rust, etc.         │
│  Block tracking, real stdlib operations  │
└──────────────────────────────────────────┘
```

### Dialect Pack Format (proposed)

```yaml
name: nature_classroom_v1
version: 1
author: "Teacher Name"
description: "Nature-themed vocabulary for elementary classroom"

# Verb aliases → canonical Poetica verbs
verbs:
  whisper: emit
  sing: emit
  reveal: emit
  carry: flow
  dance: flow
  plant: flow
  bind: pack
  fold: pack
  gather: pack
  crystallize: pack
  fish: use
  harvest: use
  guard: use
  compost: shed     # new verb needed for "discard"
  graft: use
  pollinate: lift
  pulse: seed       # with "update" connotation
  root: name
  branch: when
  sprout: seed      # with "function" connotation
  reflect: emit     # introspective output

# Phrase aliases → canonical intent (for cmd backend)
phrases:
  "show me what's in here":
    intent: fs.list
  "show the hidden stuff":
    intent: fs.list
    args: {hidden: true}
  "break it down":
    intent: explain.last_error
  "run it back":
    intent: history.repeat_last
    requires_confirmation: true

# ATCG annotations (optional)
atcg_enabled: true
# A=Action, T=Time, C=Context, G=Goal

# Dot-notation normalization
dot_notation: true
# morning.breaks → morning_breaks (underscore join)
```

### What the core parser needs to support this

1. **No changes to current parser** — it stays as-is
2. **New `dialects.py` module** — loads YAML, expands aliases before parser
3. **New `shed` verb** — the only verb that has no current equivalent
   (represents "discard/deallocate/delete", distinct from any existing verb)
4. **Dot-notation normalizer** — `morning.breaks` → `morning_breaks`
   (simple string replacement in the dialect layer, before parser)

### What should NOT change

- The 18 core verb patterns (seed, grow, emit, pack, lift, use, when, if,
  else when, else, for, flow, bloom, remember, learn, name, when_in, echoes)
- The 6 poem type → emitter mappings
- The L1-L5 gate levels
- The IR format (`poetica-ir-v1`)
- The receipt system

---

## Summary Classification

| Syntax Variant | Count of Sources | Recommendation |
|---------------|-----------------|----------------|
| Current 18 verbs | canonical | **Core syntax** — keep |
| 6 poem types | canonical | **Core syntax** — keep |
| `morning.breaks` dot-notation | 20+ files | **Dialect pack** — nature classroom |
| 13 HelixCode botanical verbs | 1 source | **Dialect pack** — verb aliases |
| 25 poetic synonym verbs | 1 source | **Dialect pack** — nature classroom |
| 16 language→poem mappings | 1 source | **Future emitters** (10 unimplemented) |
| ATCG codon annotations | 3 sources | **Dialect pack** — biology classroom |
| Genome/evolve syntax | 2 sources | **Dialect pack** — biology classroom |
| CAPS imperative verbs | 1 source | **Historical note** — poem-as-spec |
| VoiceVerse glyph shell | 1 source | **Historical note** + Echo Notes |
| DriftTime pulse/compost | 2 sources | **Dialect pack** — verb aliases |
| Connectors (from/into/of) | 1 source | **Dialect pack** — connector words |
| Three-column Bash/NL/Poetry | 1 source | **Echo Notes** — teaching bridge |
| Level 1-4 education variants | 1 source | **Dialect packs** — per age group |
| Symbolic identity/vow | 1 source | **Historical note** |
| Nature elements (water/stone) | 1 source | **Emoji skin** — decorative |
