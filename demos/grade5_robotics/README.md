# Grade 5 Robotics — Full Curriculum Demo

A complete vertical slice showing the Poetica education pipeline from
teacher syllabus to student lesson to evidence portfolio.

## What the teacher starts with

A plaintext syllabus (`syllabus.txt`) describing a Grade 5 robotics course:
5 units, learning objectives, vocabulary, and standards references (CSTA, NGSS).

This is what a real teacher has. Not YAML. Not JSON. A document they already wrote.

## What Poetica extracts

```
poetica syllabus inspect demos/grade5_robotics/syllabus.txt
```

The extractor finds:
- Course title and grade band
- Standards references (CSTA-1B-AP-10, NGSS 3-5-ETS1-1, etc.)
- Unit titles
- Learning objectives per unit
- Vocabulary
- Concept matches with confidence scores

Then generates a draft curriculum YAML:

```
poetica syllabus draft demos/grade5_robotics/syllabus.txt \
    --subject "Robotics" --grade-band "5" --domain robotics \
    --output demos/grade5_robotics/generated_curriculum.yaml
```

The draft is marked `needs_teacher_review: true`. Inferred mappings are labeled
with confidence scores. The teacher reviews and edits before classroom use.

## What the student sees

For the lesson "sensors trigger robot actions," the student gets five layers:

```
Original:  stop motor                  <-- what the student wrote
Canonical: seed motor_speed with 0     <-- what Poetica compiled
Concept:   actuator_control            <-- the robotics concept
Code:      motor_speed = 0             <-- the Python code
Visual:    the motor stops spinning    <-- what you'd SEE
```

No naked syntax. Every code token appears with its meaning, its plain-language
phrase, its formal concept name, and its physical/visual description.

Lines that weren't domain-rewritten get four layers:

```
Visual:  The value "obstacle detected" leaves the program and appears on screen
Phrase:  emit "obstacle detected"
Concept: output (Send a value to the screen)
Code:    print("obstacle detected")
```

## How domain language maps to code

The robotics domain pack (`examples/domains/robotics.yaml`) defines:

| Domain phrase | Canonical Poetica | Python |
|---------------|------------------|--------|
| `sensor.distance` | `sensor_distance` | `sensor_distance` |
| `motor.speed` | `motor_speed` | `motor_speed` |
| `stop motor` | `seed motor_speed with 0` | `motor_speed = 0` |

The student writes in robotics language. Poetica shows both the robot concept
and the code concept side by side. The student learns what `motor_speed = 0`
means before they memorize the syntax `variable = value`.

## How evidence replaces a letter grade

Instead of "B-minus in computing," the evidence portfolio records:

```json
{
  "concept": "input_condition_action",
  "evidence_criteria": [
    {"description": "student can explain input -> condition -> action", "met": null},
    {"description": "student can modify the threshold", "met": null},
    {"description": "student can debug a wrong comparison", "met": null}
  ]
}
```

Each criterion is observable and specific. A student who can modify the threshold
but can't debug the comparison has a clear, actionable next step — not a vague
grade. The portfolio opens doors. It never closes doors.

## Why teacher review is required

Poetica drafts curriculum mappings using keyword matching. It does NOT:
- Claim official standards alignment
- Silently invent compliance
- Replace teacher judgment about what students need

Every draft is marked with confidence scores and source objectives.
The teacher verifies the mapping before it reaches students.

## Running the demo

```bash
bash demos/grade5_robotics/run_demo.sh
```

This runs all 7 pipeline steps and checks that each produces output.

## Files in this demo

| File | Description |
|------|-------------|
| `syllabus.txt` | Teacher's plaintext syllabus (input) |
| `obstacle_stop.poem` | Example robotics poem |
| `generated_curriculum.yaml` | Draft curriculum YAML (generated) |
| `lesson_input_condition_action.txt` | Alignment lesson with domain provenance |
| `visual_robot_grid.txt` | Playground step-by-step in robot_grid world |
| `evidence_input_condition_action.json` | Evidence portfolio schema |
| `demo_transcript.txt` | Full pipeline transcript (all 7 steps) |
| `run_demo.sh` | Executable demo script |
| `README.md` | This file |

## The pipeline

```
teacher's syllabus (plaintext)
  |
  v
poetica syllabus inspect    --> extract units, objectives, standards
  |
  v
poetica syllabus draft      --> generate draft curriculum YAML
  |
  v
teacher reviews YAML        --> human-in-the-loop verification
  |
  v
poetica curriculum inspect  --> validate the mapping
  |
  v
poetica curriculum lesson   --> generate layered lesson output
  |
  v
domain pack (robotics)      --> field-specific language
  |
  v
poetica align --format lesson --> 5-layer alignment (Original/Canonical/Concept/Code/Visual)
  |
  v
poetica play --world robot_grid --> step-by-step visual simulation
  |
  v
evidence portfolio (JSON)   --> what the student can actually do
```
