# M9 · Tell me

## Learnings

- Nothing proved the email setup worked until the first real alert, so S42 was added to send a test email on demand. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- Fly's deploy token opens `flyctl ssh console`, so the test email runs inside the live machine and the Resend key never enters GitHub. [CONTRIBUTING](../../../CONTRIBUTING.md#building)
- Actions logs are public, so the test email's output is scrubbed of the address and the key. [CONTRIBUTING](../../../CONTRIBUTING.md#building)
- S42 was added after M9's work started, and the governance had no rule for it. Refining before work starts is not a scope change. [Governance](../../governance.md#workflow)

## Carried forward

- [Show when a copy's price has dropped](https://github.com/loserpoints/book-watch/issues/164)
- [Track daily checks, emails and API calls somewhere I can see them](https://github.com/loserpoints/book-watch/issues/168)
