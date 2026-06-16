# Poetica STEM Demo v0.1

## Grade 5 Robotics: From Syllabus to Student Evidence

Poetica is a curriculum-aware coding language where students learn computing
through field language and visuals before they see syntax. Teachers bring
their existing syllabus. Students write in the language of their subject.
Code appears after the concept makes sense.

---

### 1. Teacher starts with a normal syllabus

```
Unit 2: Conditions and Decisions
Objectives:
- Students will understand that sensors can trigger actions in a robot.
- Students will use conditions to make decisions in code.
- Students will modify thresholds to change robot behavior.
Vocabulary: condition, threshold, comparison, if/else, decision
```

Poetica extracts units, objectives, standards (CSTA/NGSS), vocabulary,
and maps them to computing concepts with confidence scores.
The teacher reviews and approves the mapping.

---

### 2. Student writes in robotics language

```
name obstacle_stop

seed sensor.distance with 25
seed motor.speed with 100

when sensor.distance < 10:
    stop motor
    emit "obstacle detected"
else:
    emit "path clear"
```

The student writes `stop motor`, not `motor_speed = 0`.
The student writes `sensor.distance`, not `sensor_distance`.
They describe what happens in the world of their subject.

---

### 3. Visual simulation shows what the program does

```
  Step 1: [seed] Set sensor_distance = 25
  --------------------------------------------------------
  |   |   |   |   |   |
  +---+---+---+---+---+
  |   |   |   |   |   |
  +---+---+---+---+---+
  |   |   |   |   |   |
  +---+---+---+---+---+
  |   |   |   |   |   |
  +---+---+---+---+---+
  | ^ |   |   |   |   |
  +---+---+---+---+---+

  Step 3: [when] Check: sensor_distance < 10
  ...
  Step 4: [seed] Set motor_speed = 0
  ...
  Step 5: [emit] Output: "obstacle detected"
```

The student sees the robot. They see the decision gate.
They see what happens step by step.

---

### 4. Five-layer lesson maps domain to code

```
  Original:  stop motor                  <-- what the student wrote
  Canonical: seed motor_speed with 0     <-- what Poetica compiled
  Concept:   actuator_control            <-- the robotics concept
  Code:      motor_speed = 0             <-- the Python code
  Visual:    the motor stops spinning    <-- what you'd SEE
```

Every syntax token appears with its meaning. No naked syntax.
The student learns what `motor_speed = 0` means before they memorize
the pattern `variable = value`.

For lines that aren't domain-specific:

```
  Visual:  The value "obstacle detected" leaves the program and appears on screen
  Phrase:  emit "obstacle detected"
  Concept: output (Send a value to the screen)
  Code:    print("obstacle detected")
```

---

### 5. Evidence replaces a letter grade

```json
{
  "concept": "input_condition_action",
  "evidence_criteria": [
    {
      "description": "student can explain input -> condition -> action",
      "met": null
    },
    {
      "description": "student can modify the threshold",
      "met": null
    },
    {
      "description": "student can debug a wrong comparison",
      "met": null
    }
  ]
}
```

Not "B-minus in computing."

Can the student explain input → condition → action? Can they change
the threshold from 10 to 20 and predict what happens? Can they find
and fix a bug where `<` should be `>`?

Each criterion is observable, specific, and actionable.
The portfolio opens doors. It never closes doors.

---

## The pipeline

```
teacher's syllabus (plaintext)
    |
    v
poetica syllabus draft → draft curriculum YAML (teacher reviews)
    |
    v
poetica curriculum lesson → layered lesson output
    |
    v
robotics domain pack → field-specific language
    |
    v
poetica align --format lesson → 5-layer alignment
    |
    v
poetica play --world robot_grid → visual simulation
    |
    v
evidence portfolio (JSON) → what the student can actually do
```

## Try it

```bash
cd demos/grade5_robotics
bash run_demo.sh
```

274 tests passing. MIT license.

## What Poetica is not

- Not an AI tutoring chatbot
- Not a gamified coding app
- Not a replacement for teacher judgment
- Not a standards compliance engine

Poetica is a compiler. It takes human-readable phrases, maps them through
a concept graph, and produces real code in Python, JavaScript, Rust, Go,
Bash, or SQL. The education layer sits on top of the compiler, not instead of it.

## Contact

[echo313unfolding/poetica](https://github.com/echo313unfolding/poetica)
