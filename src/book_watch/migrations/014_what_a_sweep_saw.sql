-- A sweep records how much it was able to see.
--
-- We ask eBay for 50 results and send no sort, so it ranks by relevance — a
-- ranking that shifts as listings are added, edited and re-scored. A copy at
-- rank 48 today can be at rank 53 tomorrow, untouched and still for sale.
--
-- So a copy missing from a sweep means one of two things: it ended, or we did
-- not look far enough. Until now nothing could tell those apart, which barely
-- mattered while a book was searched once and never again. It matters now that
-- opening a book searches, because the copies at the edge of the window churn
-- in and out on every visit — and `copies._worth_recording` treats a copy that
-- was missing last time as having *come back*, which would fill the price
-- history with reappearances that only ever meant "fell out of our window".
--
-- Same discipline as the capture version: the observation carries the
-- conditions it was made under.

-- What we asked eBay for. Null on rows that predate this, where it was 50 and
-- is not worth pretending we recorded it.
ALTER TABLE sweep ADD COLUMN asked_for INTEGER;

-- What eBay said matched in total, which it does not always say. Null means it
-- did not, not that nothing matched — and a sweep that does not know reads as
-- a window rather than as complete.
ALTER TABLE sweep ADD COLUMN total_matching INTEGER;
