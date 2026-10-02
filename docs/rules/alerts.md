# Alerts

## Purpose

These rules decide when the app emails me about a copy, so that an email is always worth opening and a quiet morning sends nothing.

## Rules

### What goes in the email

- A copy is in the morning email when its book has a limit, it is certainly this book, its delivered price is at or under the limit (see [pricing](pricing.md)), it is new since the book was last opened (see [matching](matching.md)), and it has never been in an email.
- A copy that was over the limit when the book was last opened, and is at or under it now, is in the email too, marked as a price drop with its old price. The old price is read from the copy's price history.
- Raising a limit does not email the copies seen when it was raised, since they were seen at the new limit.
- A copy with unknown shipping is never in the email.
- Each copy shows its book, its delivered price against the limit, its condition, a link to the listing and a link to the book in the app.

### When it is sent

- One email a morning at most, sent after the daily check. Update and Check all never send.
- No copy to list means no email.
- A copy is in at most one email, ever.

### Sending

- Email goes through Resend from its shared address, which needs no domain and delivers only to the Resend account's own address.
- The key and the recipient are Fly secrets. Without either, no email is sent and the log says email is off.
- A failed send is logged, not shown in the app. Nothing is recorded as sent, so the next morning tries the same copies.
- A test email can be sent on demand, with a link to the app. It is never recorded as an alert and does not change the morning email.

## Open issues

- [See what the app does unattended, and hear when something is wrong](https://github.com/loserpoints/book-watch/issues/168)
