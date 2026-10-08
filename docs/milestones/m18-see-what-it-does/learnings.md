# M18 · See what it does

## Learnings

- The priority rules would have framed M18 with an enhancement under rule 4. Alan chose observability instead, deferred since M13 and dropped twice before (S50, S53). A choice the rules don't make is now named in the draft, with the rule that applied and what it would have chosen. [Set milestone](../../../.claude/skills/set-milestone/SKILL.md#priority)
- Planning started from slices and went back to what to measure. Settling the vocabulary first, then logs for why and counts for how often, made the three slices that followed easy to write. The split is the rules doc's first section. [Monitoring](../../rules/monitoring.md#logs-and-counts)
- S78's test passed here and failed in CI: a router built without a stub fell back to the real client and found this environment's eBay keys. Checks now run once without the keys before a push. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- S77's scrubbing hid only the first character of an eBay token, which holds `^` and `#`, and its test passed by looking for the whole token. A test that a secret stays out now checks for any piece of a fake shaped like the real one. [CONTRIBUTING](../../../CONTRIBUTING.md#testing)
- S77 replaced the app's log lines and left the runbook quoting two of the old ones until S79 found them. A change that rewords a message now searches the docs for its old wording. [CONTRIBUTING](../../../CONTRIBUTING.md#reviewing)
- Fly's docs name `fly_volume_` series, and Fly's Grafana held none, so the app reads its own disk. Checking against the thing itself, already a building rule, found it before the dashboard depended on it. [Monitoring](../../rules/monitoring.md#counts)
- S79's review stopped after one round, with a few hours of counts to look at, and alerts (S80) were dropped for the same reason: what to alert on is chosen from data. A view of data is now reviewed once it holds some. [CONTRIBUTING](../../../CONTRIBUTING.md#building)

## Carried forward

- [Hear from Grafana when something goes wrong, and restyle the dashboard once it holds data](https://github.com/loserpoints/book-watch/issues/282)
