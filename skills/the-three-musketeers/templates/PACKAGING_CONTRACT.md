# Packaging contract

Owner: <user> | Effective: <date> | Scope: every project in `PROJECTS.md`

## 1. Purpose

A fixed team of agent profiles works across a changing set of projects. This
contract keeps a project from existing only in an agent's memory, and makes every
claim checkable.

## 2. The wipe test

A project is packaged when an agent with zero memory can answer, from the
project root alone:

1. What is this, and what is it for?
2. Where do the code and data live?
3. What phase is it in, and what is blocked?
4. What were the last few decisions, and why?
5. What artifacts exist, and how do I verify each one?
6. Which decisions belong to <user>, and which to the agent?

The contract fixes what must be findable, not file names. Existing spines stay.

## 3. What lives where

- PM memory and `PROJECTS.md`: a catalogue. Root, spine pointer, phase, locks.
- Project disk: the record itself.

## 4. Cards

Every card carries Root, Acceptance, Artifact, Fence, Locks, and ends with "If the
premise looks wrong, say so before building." A card missing a field is
rewritten, not dispatched.

## 5. Acceptance

All four must hold:

1. A real file exists at the stated path.
2. Its content is checkable against the acceptance criterion.
3. The verification command's exit code was captured directly, not through a pipe.
4. The model route that produced it is recorded from the log.

Claimed work without a path is not work.

## 6. The checker gate

The checker runs on a different model family from the producer. It sees the
artifact and the acceptance criterion, not the producer's rationale. It may block,
citing evidence. The PM gets two rounds to fix or rebut; a surviving block goes to
<user> with both positions and the artifact.

## 7. Project locks

| Project | Lock |
|---|---|
| all | No push, tag, release, or publish without a task-specific decision from <user>. |
| <project> | <lock> |

## 8. What this contract does not do

No mandated layout, no new frameworks, no automatic loosening of thresholds, no
self-modifying acceptance criteria.
