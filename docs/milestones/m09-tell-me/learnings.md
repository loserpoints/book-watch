# M9 · Tell me

## Learnings

- Nothing proved the email setup worked until the first real alert, so S42 was added to send a test email on demand. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- Fly's deploy token opens `flyctl ssh console`, so the test email runs inside the live machine and the Resend key never enters GitHub. [CONTRIBUTING](../../../CONTRIBUTING.md#building)
- Actions logs are public, so the test email's output is scrubbed of the address and the key. [CONTRIBUTING](../../../CONTRIBUTING.md#building)
- S42 was added after M9 started, and a slice rewritten in place can't be compared across two scope files. Each milestone now keeps one scope, kept current. [Governance](../../governance.md#artifacts)

## Carried forward

- [Show when a copy's price has dropped](https://github.com/loserpoints/book-watch/issues/164)
- [Track daily checks, emails and API calls somewhere I can see them](https://github.com/loserpoints/book-watch/issues/168)
