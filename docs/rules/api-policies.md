# API policies

## Purpose

This document records what each marketplace's own terms say about using its listings, with links to the pages that say it, so a decision about a marketplace starts from its terms.

## Rules

### Reading these pages

- Each entry quotes or paraphrases the marketplace's own document, names the section, and links it. The link is the source; the summary is only a way back to it.
- Each entry gives the version or date of the document as it was read. Terms change, so check the link before relying on a summary.
- eBay's license page and Biblio's and Alibris's sites refuse requests from a Claude Code session. Alan reads those pages in a browser and pastes the text.
- A marketplace page is read from Fly, with Read a marketplace page once, before anything is built on its shape. AbeBooks served a Claude Code session a different version of the same page: sorted another way, with grouped rows and copies without an ISBN.

### eBay

Read 2026-10-05 from the [API License Agreement](https://developer.ebay.com/join/api-license-agreement), dated September 3, 2025.

- **Purpose.** The license covers "facilitating your own or Your Users' use of eBay Services" (3.1).
- **Copies.** "Limited intermediate copies of eBay Content only as necessary", deleted "when they are no longer required" (3.1(b)).
- **Arrangement.** "Rearranging or reorganizing eBay Content within your Application" is permitted (3.1(c)).
- **Ended listings.** "When the eBay Content is no longer publicly available, you must delete it from your Application" (8.1(b)(1)).
- **Other marketplaces.** eBay content "may not be co-mingled or combined with non-eBay Content" and "must be visually isolated from third-party listings or other non-eBay information" (8.1(b)(2)).
- **Freshness.** Listing information shown "may not be more than six (6) hours older than information displayed on the eBay Site", or the app discloses how much older it is (8.1(c)).
- **User IDs.** "You will not under any circumstances collect, store or share any eBay User' User IDs or passwords" (8.2).
- **Messages.** "You may only communicate with Your Users ... to promote and facilitate access to and use of eBay Services" (8.3).
- **Prices.** No using eBay content "either alone or in combination with third-party information, to suggest or model prices for items listed on eBay Site" (9.5).
- **Competition.** No using eBay content "to compete with eBay Services" (9.3).
- **Ownership.** eBay owns "any content created or derived" from eBay content (5).
- **Other users.** Sublicensing display to an app's users requires a binding agreement with each user that carries these terms (4.2).
- **Publicity.** No public statement "concerning any aspect of the eBay Developers Program" without eBay's written approval (18).
- **Audit.** eBay may monitor or audit the app and its records of eBay data (12.1).
- **Personal data.** Storing personal data brings in the [Data Processing Addendum](https://developer.ebay.com/join/api-license-agreement) and its security measures (Exhibit A).
- **Access.** Production use of most Buy APIs is for partners who apply through the eBay Partner Network ([Buy APIs requirements](https://developer.ebay.com/api-docs/buy/static/buy-requirements.html)). The [Browse API guide](https://developer.ebay.com/api-docs/buy/static/api-browse.html) describes the search and item methods the app uses.
- **Call limits.** [API call limits](https://developer.ebay.com/develop/api-call-limits).

### AbeBooks

Read 2026-10-05.

- **Access.** The [Search Web Services overview](https://www.abebooks.com/developer/search-web-services/overview) requires joining the [affiliate program](https://www.abebooks.com/books/affiliateprogram/) through [Impact](http://member.impactradius.com/campaign-mediapartner-signup/AbeBooks-Inc.brand?type=dm), then emailing affiliate@abebooks.com with the requesting IP address, the site's URL, an email address, a technical contact and the affiliate ID. AbeBooks reviews the request and sends instructions for a client key.
- **Data.** The [parameters page](https://www.abebooks.com/developer/search-web-services/parameters) lists ISBN, price, total with shipping by destination country, listing and item condition, seller description, seller photos, listing URL, seller rating, first edition and dust jacket. It gives no listing date, though results can be sorted newest first. Up to 200 results a search, at 4 to 5 searches a second.
- **License.** The [Search Web Services License Agreement](https://www.abebooks.com/docs/affiliateprogram/webservices/terms-printable.shtml) governs the API, and the [affiliate operating agreement](https://www.abebooks.com/docs/AffiliateProgram/operating-agreement.pdf), updated July 2024, governs the program. The operating agreement redirects to a file on `assets.brightspot.abebooks.a2z.com`.
- **Permitted purposes.** Letting users of the site submit searches and showing the results "for viewing by the individual user that submitted the search query", and "such other purposes as may be agreed to in writing by AbeBooks" (license 2.1).
- **Searches.** Only "as necessary to facilitate lawful, legitimate and good faith inquiries by third party users" (license 2.3(b)(i)), and only through the API, not "robots, spiders, crawlers, scraping or other similar technology" (2.3(b)(ii)).
- **Storage.** Results deleted once no longer needed, and "in any event no later than 24 hours after the Search Results were first downloaded" (license 2.3(c)(i)).
- **Freshness.** Results shown only if fetched "no more than 5 minutes before" they are shown (license 2.3(c)(iv)).
- **Who sees results.** Only "the person that submitted the query", and only on the applicant's site (license 2.3(c)(ii), (iii)). Every page showing results links each item to its AbeBooks page (2.3(c)).
- **Changes.** Only minor changes needed for display that do not change the meaning (license 2.3(c)(v)).
- **Review.** AbeBooks may require the search program for approval and may inspect its use (license 2.6). The license ends if the site's nature or URL changes materially (5.2).
- **Publicity.** No materials referencing AbeBooks without its written consent, beyond showing results (license 3.5).
- **Email.** No promotion "in any offline manner (e.g., in any printed material, mailing, SMS, MMS, email or attachment to email" (operating agreement, participation requirement 6).
- **Own purchases.** No buying through one's own affiliate links "for use by you" (participation requirement 28).
- **Comparison.** A site that shows AbeBooks prices beside other sites' prices shows AbeBooks' lowest new price and, if provided, its lowest used price (operating agreement, linking requirements).
- **Disclosure.** The site states that it participates in the AbeBooks affiliate program (operating agreement, section 10).
- **Fixed IP.** On Fly, an outbound address that doesn't change costs $3.60 a month ([egress IPs](https://fly.io/docs/networking/egress-ips/)).
- **Website terms.** The [Terms and Conditions](https://www.abebooks.com/docs/legal/termsAndConditions.shtml) grant "a limited license to access and make personal use of the Web Site", which "does not include ... any collection and use of any product listings, descriptions, or prices; ... or any use of data mining, robots, or similar data gathering and extraction tools", and bar use "for any commercial purpose without express written consent of AbeBooks" (License and site access). Read 2026-10-06.
- **robots.txt.** [robots.txt](https://www.abebooks.com/robots.txt) disallows `/servlet/`, `/search/`, `/abe/`, `/abep/`, `/cgi/`, `/collections/`, `/checkout/` and `/discovery/` for every robot, and allows `/search/` and `/servlet/` pages only to named search engines. It states no crawl delay. It is a request to crawlers, separate from the website terms. Read 2026-10-06.

#### AbeBooks' pages

Read 2026-10-06, from 18 requests sent from a Claude Code session and 7 sent from the Fly machine with Actions → Read a marketplace page once.

- **Title search.** `/book-search/title/<title>/author/<author>/` lists 30 rows a page. It comes in two versions, below. Each row gives title, ISBN when the seller entered one, publisher and year, binding, seller, condition, price, shipping to the US, and whether it is a first edition, signed or in a dust jacket. A row for an edition with several copies says "Used offers from US$ X", the delivered price of its cheapest copy. Later pages are under `/servlet/SearchResults`. [Example](https://www.abebooks.com/book-search/title/geronimo-rex/author/barry-hannah/).
- **ISBN page.** `/book-search/isbn/<ISBN>/used/` lists one ISBN's used copies, 30 a page, sorted by delivered price, cheapest first, with the same fields per copy and a count of results. Later pages are under `/servlet/SearchResults`. [Example with 9 copies](https://www.abebooks.com/book-search/isbn/9780670337286/used/), [example with 207](https://www.abebooks.com/book-search/isbn/9780590353427/used/).
- **Edition page.** `/<ISBN>/<title>/plp` shows about 10 copies of one edition, not sorted by price. Its summary of lowest and highest price excludes shipping. [Example](https://www.abebooks.com/9780140449136/Crime-Punishment-Penguin-Classics-Dostoyevsky-0140449132/plp).
- **The version served to Fly.** Every row is one copy, sorted by delivered price, cheapest first, and every row has an ISBN. Page 1 is the book's 30 cheapest copies across its editions. An edition whose copies all cost more than the 30th does not appear, nor do copies without an ISBN. Seen on three searches, every time, on 2026-10-06. The order is rough rather than exact: the same day, page 1 of *Geronimo Rex* had two neighbors 2 cents out of order and its one copy of a French edition last, $7 cheaper than the rows above it.
- **The version served to the Claude Code session.** Rows are sorted by relevance, and an edition with several copies gets one grouped row. Copies without an ISBN are included.
- **Writing the search.** The title and author in the path are search words, not the address of one book. Small words make no difference: `crime-punishment` and `crime-and-punishment` gave the same results. Punctuation must be dropped: `jesus-son` found *Jesus' Son*, and `jesuss-son` found nothing. A subtitle narrows the search: `already-dead` gave 66 results, `already-dead-california-gothic` 44.
- **No results.** A search that matches nothing returns an ordinary page with no rows and no count, the same for a misspelled title as for a book with no copies.
- **The count** reads "(71 results)", or "(Over 1,500 results)" for large ones.
- **Copies without an ISBN** appear only in the title search. In the *Geronimo Rex* example, 21 of the first page's 30 rows had none, most of them first editions.
- **Shipping** is priced to a country, not a ZIP code, from the visitor's shopping preferences or location.

### Biblio

Read 2026-10-05 from search results, because Biblio's pages refuse scripted requests.

- **Access.** The API is for affiliates and booksellers. The [API documentation](https://www.biblio.com/blog/2013/01/biblio-inventory-api-documentation/) says to register an account on biblio.com, then email Biblio's marketing team from that account's address to request a key.
- **Program.** The [affiliate program](https://www.biblio.com/affiliate-program) runs through [Awin](https://ui.awin.com/merchant-profile/88369). Joining it gives no API access on its own.
- **License.** Not read. The API's terms are not public.
- **robots.txt.** [robots.txt](https://www.biblio.com/robots.txt) disallows `/search.php`, `/b/`, `/app/` and others for every robot. Read 2026-10-06.
- **Pages.** Biblio's pages answered with a Cloudflare challenge instead of the page, from a Claude Code session and from the Fly machine (status 403).

### Alibris

Read 2026-10-05 from search results, because Alibris's pages refuse scripted requests.

- **API.** Alibris [launched an API in 2010](https://www.prnewswire.com/news-releases/alibris-launches-api-developer-portal-with-mashery-111775394.html). No current documentation was found.
- **Program.** The [affiliate program](https://www.alibris.com/affiliates/home) runs through Rakuten.

### Amazon

Read 2026-10-05.

- **Access.** The Product Advertising API comes through Amazon Associates. It needs three qualifying sales within 180 days of joining, and ten qualifying sales in the trailing 30 days to keep access ([requirements](https://affiliate-program.amazon.com/help/node/topic/GVJ2BJP35457CLML), [the ten-sale rule](https://www.keywordrush.com/blog/amazon-pa-api-associatenoteligible-error-is-there-a-new-10-sales-rule/)).
- **Versions.** The Product Advertising API 5.0 retired on May 15, 2026, in favor of the Creators API, which keeps the sales requirement ([summary](https://dev.to/agenthustler/amazon-product-api-pa-api-in-2026-restrictions-alternatives-and-web-scraping-4l35)).
- **Data.** Whether the API returns individual used copies with condition notes was not confirmed.

## Open issues

- [S66 · AbeBooks copies appear on a book's page, in the daily check and in the morning email](https://github.com/loserpoints/book-watch/issues/229)
- [Search Biblio as a second marketplace](https://github.com/loserpoints/book-watch/issues/145)
- [Others can try book-watch in a public demo, or run their own copy](https://github.com/loserpoints/book-watch/issues/225)
