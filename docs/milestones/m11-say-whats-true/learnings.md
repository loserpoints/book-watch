# M11 · Say what's true

## Learnings

- S50 was dropped in planning. Rewriting its issue as a slice lost the issue's own note that the deploy already fails when the database can't open. [Plan slice](../../../.claude/skills/plan-slice/SKILL.md#questions)
- The first live restore failed because Fly gives a snapshot's size in bytes. The fake Fly in the tests was built from memory and never carried that field. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- Fly's documentation lives on subdomains, so allowing `fly.io` alone still blocked it. [CONTRIBUTING](../../../CONTRIBUTING.md#building)
- S51 weighed three ways to detect Fly before asking who reads the message. The app runs only on Fly, so it needed none. [CONTRIBUTING](../../../CONTRIBUTING.md#building)
- Alan twice asked for a decision again in plain words, on how to test a restore and how to detect Fly. [CLAUDE.md](../../../CLAUDE.md#working-rules)

## Carried forward

- [Track daily checks, emails and API calls somewhere I can see them](https://github.com/loserpoints/book-watch/issues/168)
