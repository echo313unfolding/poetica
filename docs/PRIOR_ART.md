# Prior Art and Related Work

Poetica does not claim to invent readable programming. It claims to connect
readable programming to curriculum, domain language, visual simulation, and
evidence-based STEM learning — in a single pipeline that a teacher can drive
without becoming a software engineer.

This document maps the landscape honestly: what Poetica borrows, what it
extends, and where it differs.

---

## 1. Human-Readable Programming Languages

### Quorum (Andreas Stefik, University of Nevada Las Vegas)

Quorum is the most important precedent. Stefik's empirical work (2011–present)
demonstrated that programming language syntax is not "neutral" — some keyword
choices are measurably harder for novices than others. Quorum was redesigned
from the ground up using controlled experiments on syntax learnability.

**What Poetica borrows:** The conviction that syntax should be evidence-based,
not tradition-based. Poetica's verb set (`seed`, `grow`, `emit`, `bloom`) was
chosen for semantic clarity, not for resemblance to C.

**Where Poetica differs:** Quorum is a full programming language with its own
runtime, type system, and IDE. Poetica is a DSL that compiles to *other*
languages. Quorum teaches students *Quorum*. Poetica teaches students Python,
Rust, JavaScript, Go, Bash, or SQL — through a readable intermediate form.
Quorum does not have a curriculum mapper, domain packs, or evidence portfolios.

### Inform 7 (Graham Nelson)

Inform 7 compiles near-English prose into interactive fiction. A statement
like `The red ball is in the living room` is valid Inform 7. The language
proves that natural-language-like syntax can drive a real compiler for a
specific domain (world modeling).

**What Poetica borrows:** The idea that a compiler can accept phrases that
read like descriptions of intent rather than instructions to a machine.

**Where Poetica differs:** Inform 7 targets a single domain (interactive
fiction) and a single output (Z-machine / Glulx). Poetica is domain-agnostic
(robotics, microbiology, finance — via domain packs) and multi-target (six
languages). Inform 7 has no education layer.

### AppleScript

AppleScript attempted English-like syntax for system automation: `tell
application "Finder" to open folder "Documents"`. It is widely considered
a cautionary tale — the English surface made the language *harder* to learn,
because users expected English semantics and got programming semantics.

**What Poetica learns:** Readability is necessary but not sufficient.
AppleScript had readable syntax without concept scaffolding. Users could
read the code but couldn't predict what it would do. Poetica addresses this
with the alignment map (every token has a visual, concept, and code layer)
and the capability gate (operations are unlocked progressively, not all
available at once).

---

## 2. Visual-First / Block-Based Learning

### Scratch / Blockly (MIT Media Lab / Google)

Scratch eliminates syntax errors entirely by using drag-and-drop blocks.
It is the most successful introductory programming environment ever built
(100M+ users). Blockly is the open-source block editor that powers many
derivatives (Code.org, MakeCode, App Inventor).

**What Poetica borrows:** The principle that beginners should see what a
program *does* before they worry about how it's *spelled*. Poetica's visual
worlds (robot_grid, garden, filesystem) serve the same role as Scratch's
stage — showing the effect of each operation.

**Where Poetica differs:** Scratch and Blockly are environments, not
compilers. They produce Scratch projects, not Python or Rust. The transition
from blocks to text is a cliff — students must start over in a new paradigm.
Poetica is text from day one, but the text is readable and every line has a
visual layer. The transition to production code is a compiler flag
(`--type sonnet`), not a paradigm shift.

Scratch also has no curriculum integration. Teachers use Scratch *inside*
their curriculum, but Scratch doesn't know what the curriculum says. Poetica
imports the syllabus and maps objectives to concepts.

### Logo (Seymour Papert, MIT)

Logo introduced "body-syntonic" learning — the turtle is an object students
can reason about by imagining themselves as the turtle. `FORWARD 100` means
something because you can *be* the turtle.

**What Poetica borrows:** Domain language as cognitive scaffolding. When a
student writes `stop motor` in Poetica's robotics domain, they are reasoning
about the robot, not about variable assignment. The domain pack is the modern
version of the turtle.

**Where Poetica differs:** Logo is a language. Poetica is a compiler that
accepts domain-specific phrases and maps them through a concept graph to
multiple target languages. Logo taught geometry through programming. Poetica
teaches computing through the student's own subject.

---

## 3. Gradual Syntax / Beginner Languages

### Hedy (Felienne Hermans, Vrije Universiteit Amsterdam)

Hedy introduces Python syntax gradually across numbered levels. Level 1 has
`print hello` (no quotes, no parentheses). Level 6 adds `if/else`. Level 18
is full Python. Hermans' research shows that gradual syntax introduction
reduces frustration and dropout.

**What Poetica borrows:** The leveled approach. Poetica's capability gate
(L1–L5) is structurally similar — L1 programs can only `seed`, `emit`,
`flow`, `bloom`, and `remember`. Higher operations unlock at higher levels.

**Where Poetica differs:** Hedy teaches *Python syntax* gradually. Poetica
teaches *computing concepts* through domain language, then shows the syntax
as one layer of the alignment map. Hedy's levels are about which *syntax
features* are available. Poetica's levels are about which *operations* are
safe — a security/capability boundary, not just a pedagogical scaffold.

Hedy also does not have domain packs, curriculum import, visual simulation,
or evidence portfolios. It is a single-language tool (Python). Poetica
compiles to six languages.

---

## 4. AI Coding Assistants

### GitHub Copilot / ChatGPT / Claude

AI assistants generate code from natural language descriptions. They can
produce working programs from prompts like "write a function that stops a
motor when the sensor reads less than 10."

**What Poetica borrows:** Nothing, architecturally. Poetica is a
deterministic compiler, not a language model.

**Where Poetica differs fundamentally:**

- **Determinism.** `seed x with 42` always compiles to the same code for a
  given target. There is no temperature, no sampling, no hallucination.
- **Auditability.** Every compilation produces a receipt: what ops were used,
  what the gate allowed, what code was generated, with hashes. An AI assistant
  cannot produce a receipt because its output is stochastic.
- **Curriculum alignment.** An AI assistant does not know what the teacher's
  syllabus says. It generates code that may or may not match the learning
  objectives. Poetica maps every operation to a curriculum concept.
- **Capability control.** An AI assistant will happily generate `import os;
  os.system("rm -rf /")` if prompted cleverly. Poetica's gate makes this
  structurally impossible at L1–L3.

AI assistants are tools for professional developers. Poetica is infrastructure
for educators.

---

## Differentiation Summary

| System | Readable syntax | Multi-target | Curriculum integration | Domain packs | Visual simulation | Evidence portfolio | Deterministic |
|--------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Quorum | Y | - | - | - | - | - | Y |
| Inform 7 | Y | - | - | single domain | Y (IF world) | - | Y |
| Scratch/Blockly | blocks | - | - | - | Y (stage) | - | Y |
| Logo | Y | - | - | single (geometry) | Y (turtle) | - | Y |
| Hedy | gradual | - | - | - | - | - | Y |
| AppleScript | Y | - | - | single (macOS) | - | - | Y |
| Copilot/ChatGPT | NL input | multi | - | - | - | - | - |
| **Poetica** | **Y** | **6 targets** | **syllabus import** | **pluggable** | **3 worlds** | **per-concept** | **Y** |

---

## The Gap Poetica Fills

The prior art falls into two clusters:

1. **Readable languages** (Quorum, Inform 7, Hedy, Logo) — teach programming
   through better syntax, but are single-target and have no curriculum layer.
2. **Visual environments** (Scratch, Blockly) — eliminate syntax friction, but
   create a cliff when students move to text and have no curriculum layer.

Neither cluster connects to the teacher's existing syllabus. Neither produces
evidence portfolios. Neither lets a domain expert (robotics teacher, biology
teacher, finance instructor) bring their own vocabulary and have it compile
to real code.

Poetica's contribution is the *pipeline*: syllabus in, domain language
active, visual simulation running, alignment map showing every layer, evidence
criteria attached to curriculum concepts, and real code out the other end.
The compiler is the means. The curriculum connection is the point.

---

## References

- Stefik, A. & Siebert, S. (2013). "An Empirical Investigation into Programming Language Syntax." *ACM TOCE*, 13(4).
- Nelson, G. (2006). "Natural Language, Semantic Analysis and Interactive Fiction." *IF Theory Reader*.
- Papert, S. (1980). *Mindstorms: Children, Computers, and Powerful Ideas.* Basic Books.
- Hermans, F. (2020). "Hedy: A Gradual Language for Programming Education." *ACM ICER*.
- Resnick, M. et al. (2009). "Scratch: Programming for All." *Communications of the ACM*, 52(11).
