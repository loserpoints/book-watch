-- The most I will pay for this book, delivered.
--
-- On the entry rather than the work, and that is not filing. A work is shared
-- between entries, and *Two kinds of hunt* is where two entries for one book
-- start existing — a reader who will take any copy and a collector who wants
-- one printing will not pay the same, so a ceiling on the work would make one
-- of them wrong.
--
-- It is a delivered price. Shipping is the difference between a good copy and
-- a bad deal, and `Copy.landed_cost` already computes it.

-- Stored as a string, like every other amount here. Decision 1: "8.99" parsed
-- into a float and written back is a different number, and this one gets
-- compared against prices eBay sent as strings.
--
-- Null is the ordinary state. Most books will never have a ceiling, and a book
-- without one is not a book with a ceiling of infinity — nothing is marked
-- either way.
ALTER TABLE entry ADD COLUMN ceiling TEXT;

-- The currency it is in, so the comparison can refuse rather than guess.
--
-- Assuming the marketplace's currency would be simpler and would be silently
-- wrong the first time a copy is priced in something else — which already
-- happens, because a search may return an overseas seller pricing in GBP. A
-- comparison across currencies is not a hard comparison, it is an unsupported
-- one, and the page says so instead.
ALTER TABLE entry ADD COLUMN ceiling_currency TEXT;

-- Both or neither. A number with no currency is not a price, and a currency
-- with no number is not a ceiling.
CREATE TRIGGER entry_ceiling_is_whole_or_absent
BEFORE UPDATE OF ceiling, ceiling_currency ON entry
FOR EACH ROW
WHEN (NEW.ceiling IS NULL) != (NEW.ceiling_currency IS NULL)
BEGIN
    SELECT RAISE(ABORT, 'a ceiling needs both an amount and a currency');
END;
