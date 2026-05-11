# Send-lists

Each JSON file in this folder is a complete chat-completions payload captured from the production system at the moment it was about to call the LLM. Run any of them with the replay harness:

```bash
python ../harness/replay.py case1_first_turn.json --batch 20
```

---

## `case1_first_turn.json`

**The first turn of a multi-party scene.** Three participants — Tom (the active NPC), Sam (the player), and Liam — at the Quiet Mourning Bookshop. Liam has just spoken to Sam; Tom is now the active speaker and is about to address Sam.

Demonstrates:
- A clean **PairHistory** prompt: only the `(Tom, Sam)` pair is visible. Liam doesn't appear as a transcript participant.
- The **narrative envelope** for cross-pair context (`A moment ago, Liam said to Sam: "..."` delivered as a system message, not as a transcript turn).
- The **anchor parenthetical** glued to the player's message (`(Sam is waiting for your response.)`).
- The **pronouns fix** in the current scene state.

In the post: corresponds to Case 1 in the empirical results — the variant that tested at 88–92% target correctness after applying the narrative envelope (up from 60% in the transcript form).

---

## `case2_accumulated.json`

**A second turn in the same scene, from a different speaker's perspective.** Liam is now the active speaker, having previously responded to Sam. The `(Liam, Sam)` pair history shows their exchange so far; a cross-event from Tom is delivered as system context.

Demonstrates:
- An **accumulated pair history** with one prior user turn and one prior assistant turn, properly rotated.
- A cross-pair event injected as **`Recent events in the scene:`** narrative block, not woven into the transcript.
- The **current scene state** describing the active addressee's relationship to the speaker, using pronouns after the first anchor.

In the post: corresponds to Case 2 in the empirical results — accumulated pair history with a cross-event injection.

---

## `case3_adversarial_before.json` and `case3_adversarial_after.json`

**The adversarial scene from Section 4c of the post.** Maya is being asked to address Liam directly. The current scene state communicates strong negative feelings toward Liam (Maya is romantically repulsed by him, the prior scene featured a physical threat). Under those conditions, the model is structurally biased to talk *about* Liam in third person.

Two variants of the same scene:

### `case3_adversarial_before.json`

Current scene state uses **the addressee's name repeatedly** — four mentions of "Liam" as a third-person object:

```
Liam is also part of this conversation. Liam is your Partner.
You strongly resent Liam. You are romantically repulsed by Liam.
You are speaking directly to Liam.
```

Five mentions total. The closing anchor competes with four prior object-position mentions, and tends to lose.

In the post: tested at **~70%** target correctness.

### `case3_adversarial_after.json`

Same scene, **pronouns applied after the first mention**:

```
Liam is also part of this conversation. He is your Partner.
You strongly resent him. You are romantically repulsed by him.
You are speaking directly to Liam.
```

The first mention anchors who the addressee is. Subsequent references are pronouns, removing the object-position competition.

In the post: tested at **~92%** target correctness.

### Running both

```bash
python ../harness/replay.py case3_adversarial_before.json --batch 20
python ../harness/replay.py case3_adversarial_after.json --batch 20
```

Read both batches. The difference is four words in the current scene state.

The point of including both versions isn't to claim that you'll see exactly 70% and 92% on your machine — sampling variance is real, your hardware and exact model build matter. The point is that, qualitatively, the "before" responses are noticeably more likely to do the failure mode the patterns were designed to prevent: talking *about* Liam in third person while ostensibly addressing him.

---

## Notes on what's NOT in these send-lists

- **No fine-tuning data.** Same off-the-shelf `mn-12b-mag-mell-r1` model for all four send-lists. The differences in behaviour come from the prompt structure alone.
- **No retry logic.** Each request is single-shot. Production systems may want to add a validation pass; the patterns shouldn't depend on it.
- **No streaming.** The harness uses the non-streaming endpoint. Streaming behaviour is identical for prompt parsing.
- **No tool calls / function calling.** These are dialogue-only prompts. The production system uses tool calls for NPC actions, but that's orthogonal to the conversation patterns documented here.
