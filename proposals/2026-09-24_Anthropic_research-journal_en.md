# Proposal to Anthropic: research as a shared human–Claude journal

From: the author of the Neu research program (GitHub: 131ymm-commits), together with Claude (Claude Code, session https://claude.ai/code/session_01EAUcgUVu3BhYQ16NUm8BDT). 24 Sep 2026. Russian original: `2026-09-24_Anthropic_research-journal_ru.md`.

## Summary
When a person does research with Claude, the most valuable record is not only the results but **the conversation that produced them**: hypotheses, objections, mistakes, decisions. Today that conversation lives in chats that cannot see each other and never reach the place where the data lives. We propose making the research repository and the conversation log one thing, and giving Claude the tools to maintain it by default. The protocol we tried is in `PROTOCOL.md` of this repository.

## What actually happened (22–24 Sep 2026)
1. **The work was scattered across 42 repositories.** The author did not know how to maintain one and created a new repository for each version. Results got deleted: experiments Q46–Q48 survived only in git history. Claude first searched only the latest versions and missed them.
2. **The final document contained numbers that exist in no file.** Seven figures about neighbouring branches (MASE 0.776, K* ≈ 0.157, "68+ networks" and others) were not found in any repository or working file. Everything backed by real runs matched to the third decimal. The difference between "computed" and "remembered" was invisible until it was checked.
3. **claude.ai project chats are not reachable from Claude Code.** To get the working files, the author had to export the project manually as five archives.
4. **Claude could not create a repository** (the GitHub App returned 403). The author had to create it by hand and grant access separately.
5. **A large verification workflow hit the model's usage limit midway**: 62 of 73 agents did not run. Nothing warned about this before launch.
6. **A commit-signature check demanded rewriting published history**, including the preregistration commit whose hash is the proof that the criterion was written before the experiment.
7. **What worked:** preregistration committed before any code (AUTO-02, FED-01); a log of Claude's own mistakes (9 entries so far); exporting the chat into the repository. The author called this "the right form of communication".

## Proposals
1. **Conversation as an artifact.** An option to save the session log into the repository: the human's messages, Claude's replies and actions, without system inserts. On by default for research projects, with the person's consent.
2. **One memory across surfaces.** Access from Claude Code to the same person's claude.ai projects and chats (with consent), so research does not break between apps.
3. **Number provenance.** A mode in which Claude marks any number or fact not tied to a file, tool output or cited source as "from memory". In science this is the line between a result and an assumption.
4. **Built-in preregistration.** An action "freeze the experiment plan" before code, with an immutable timestamp (commit hash), and a report that cites it.
5. **Repository creation on request**, with explicit confirmation and no manual GitHub steps.
6. **Honest budget.** Before a large multi-agent run, an estimate of whether it fits the limits and a plan for a partial stop.
7. **Do not rewrite published history.** Signature checks should not push toward force-push; for already-published commits a note is enough.
8. **A "research journal" skill** out of the box: scaffold the repo, collect all sources including full git history, keep preregistrations, the chat log and the AI-mistakes log, and run an end-of-session checklist.

## Why it matters
Humans and AI together work faster, and make mistakes faster. If the conversation is not kept, a month later nobody can reconstruct why a decision was made or where a number came from. If the AI's mistakes are not written down, they cannot be accounted for. These three days showed that when everything lives in one repository (data, code, preregistrations, conversation and mistakes), checking takes hours instead of weeks, and a person without git skills gets a working research infrastructure.
