// The little the controls need that HTML cannot do alone. S30, #110.
//
// Everything here works on markup the macros in templates/_ui.html emit, by
// data attributes, so no screen writes its own script. No framework and no
// build step. Without JavaScript the page still reads; only the
// sheets and the enlarged photo need it.

(function () {
  "use strict";

  // An open "Was $12.40" box under a price's caret closes on the next tap
  // anywhere, and that tap does nothing else (S72, #164): a tap that lands on
  // a row would otherwise open the book, or a listing, while the person only
  // meant to put the box away. A tap on its own caret closes it as usual.
  // Capturing, so it runs before the link, htmx or any other handler.
  document.addEventListener(
    "click",
    function (event) {
      var open = document.querySelectorAll("details.move[open]");
      if (!open.length) return;
      var target = event.target instanceof Element ? event.target : null;
      var own = target && target.closest("details.move[open] > summary");
      if (own) return;
      event.preventDefault();
      event.stopPropagation();
      Array.prototype.forEach.call(open, function (box) { box.open = false; });
    },
    true
  );

  // [data-open="id"] opens the <dialog id="id"> as a modal. The browser then
  // handles focus, Escape and the Android back gesture, and returns focus to
  // the opener when it closes.
  document.addEventListener("click", function (event) {
    var opener = event.target.closest("[data-open]");
    if (opener) {
      var dialog = document.getElementById(opener.getAttribute("data-open"));
      // "Don't ask me again": this device said so, so do what the sheet's
      // main button does without showing it. Per device on purpose; asking
      // again on another one is fine (S34).
      var skip = opener.getAttribute("data-skip");
      if (dialog && skip && remembered(skip)) {
        event.preventDefault();
        var main = dialog.querySelector("[data-default]");
        if (main) main.click();
        return;
      }
      if (dialog && typeof dialog.showModal === "function") {
        event.preventDefault();
        var large = opener.getAttribute("data-photo");
        if (large) fillPhotos(dialog, opener, large);
        dialog.showModal();
      }
      return;
    }

    // [data-replace] shows the same screen another way, so it takes this
    // page's place in the history instead of adding one: back still leaves
    // the screen (S45).
    var replacing = event.target.closest("a[data-replace]");
    if (replacing && !event.defaultPrevented && event.button === 0 &&
        !event.metaKey && !event.ctrlKey && !event.shiftKey) {
      event.preventDefault();
      window.location.replace(replacing.href);
      return;
    }

    // [data-close] inside a dialog closes it.
    var closer = event.target.closest("[data-close]");
    if (closer) {
      var parent = closer.closest("dialog");
      if (parent) {
        var noAsk = parent.querySelector("[data-remember]");
        if (noAsk && noAsk.checked) remember(noAsk.getAttribute("data-remember"));
        parent.close();
      }
      return;
    }

    // A tap on the backdrop, outside the sheet itself, closes it.
    if (event.target instanceof HTMLDialogElement && event.target.open) {
      var box = event.target.getBoundingClientRect();
      var inside =
        event.clientX >= box.left && event.clientX <= box.right &&
        event.clientY >= box.top && event.clientY <= box.bottom;
      if (!inside) event.target.close();
    }
  });

  // "added", sent by the server with a new book (S45): the sheet that asked
  // is done, so it closes over the list that now holds the book.
  document.addEventListener("added", function (event) {
    var sheet = event.target instanceof Element && event.target.closest("dialog");
    if (sheet && sheet.open) sheet.close();
  });

  // "sheet-ready", sent with the take-off sheet's contents (S71, #223): the
  // trash asked for this book's sheet, and it opens only once it holds it,
  // so it never shows the last book's for a moment. A refusal sent back to a
  // sheet already open leaves it open.
  // The event comes on the trash that asked, and names the sheet to open.
  document.addEventListener("sheet-ready", function (event) {
    var id = event.detail && event.detail.value;
    var sheet = id && document.getElementById(id);
    if (sheet && !sheet.open && typeof sheet.showModal === "function") sheet.showModal();
  });

  // "taken-off", sent with the list once a book is bought or removed: the
  // sheet closes over the list that no longer holds it.
  document.addEventListener("taken-off", function () {
    var sheet = document.getElementById("off-sheet");
    if (sheet && sheet.open) sheet.close();
  });

  // Opening a copy's listing tells the app which copy it was, so the bought
  // sheet can offer it (S71). Alongside the tap, never in its way: the link
  // still goes straight to the marketplace, which is what hands it to the
  // eBay app, and a note that never arrives costs only the suggestion.
  document.addEventListener("click", function (event) {
    var link = event.target instanceof Element && event.target.closest("a[data-opened]");
    if (!link || typeof navigator.sendBeacon !== "function") return;
    try { navigator.sendBeacon(link.getAttribute("data-opened")); } catch (ignored) {}
  });

  // A sheet that went to the server and came back with results or an error
  // reopens itself, so the answer appears where the question was asked.
  function openWaiting() {
    var waiting = document.querySelector("dialog[data-autoopen]");
    if (waiting && !waiting.open && typeof waiting.showModal === "function") {
      waiting.showModal();
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", openWaiting);
  } else {
    openWaiting();
  }

  // Browser storage can be missing or refuse (a private window); the only
  // cost is being asked again.
  function remembered(key) {
    try { return window.localStorage.getItem(key) === "1"; } catch (e) { return false; }
  }
  function remember(key) {
    try { window.localStorage.setItem(key, "1"); } catch (e) {}
  }

  // Every photo of one copy, built only now it has been tapped, so nothing
  // loads from eBay before somebody asks (S33). The first falls back to the
  // small photo already on the page if its large version does not exist.
  function fillPhotos(dialog, opener, large) {
    var strip = dialog.querySelector(".photo-strip");
    if (!strip) return;
    var urls = [large];
    try {
      var listed = JSON.parse(opener.getAttribute("data-photos") || "[]");
      if (Array.isArray(listed) && listed.length) urls = listed;
    } catch (ignored) {}
    strip.replaceChildren();
    urls.forEach(function (url, index) {
      var img = document.createElement("img");
      img.alt = "The seller's photo, " + (index + 1) + " of " + urls.length;
      if (index === 0) img.dataset.fallback = opener.getAttribute("data-photo-small") || url;
      img.src = url;
      strip.appendChild(img);
    });
    strip.scrollLeft = 0;

    // One dot per photo, the one in view filled: the only sign on screen that
    // there is more to swipe to. Nothing to show for a single photo.
    var dots = dialog.querySelector(".photo-dots");
    if (!dots) return;
    dots.replaceChildren();
    if (urls.length < 2) return;
    urls.forEach(function () {
      dots.appendChild(document.createElement("i"));
    });
    showDot(strip, dots);
  }

  function showDot(strip, dots) {
    var width = strip.clientWidth || 1;
    var current = Math.round(strip.scrollLeft / width);
    Array.prototype.forEach.call(dots.children, function (dot, index) {
      dot.classList.toggle("on", index === current);
    });
  }

  document.addEventListener(
    "scroll",
    function (event) {
      var strip = event.target;
      if (!(strip instanceof Element) || !strip.classList.contains("photo-strip")) return;
      var dots = strip.parentElement.querySelector(".photo-dots");
      if (dots && dots.children.length) showDot(strip, dots);
    },
    true
  );

  // If the large photo does not exist, fall back to the one already shown.
  document.addEventListener(
    "error",
    function (event) {
      var img = event.target;
      if (img.tagName === "IMG" && img.dataset.fallback && img.src !== img.dataset.fallback) {
        img.src = img.dataset.fallback;
      }
    },
    true
  );

  // The want list draws itself again when it comes back into view, since its
  // books may have gone out of date unseen: the phone slept, another app was
  // in front, or back restored the page from the browser's memory (S67,
  // #244). The whole list, not only the header, so rows and the morning
  // check's pill are current too. Not while a check runs, which replacing
  // the list would stop and whose own steps keep the header current, and not
  // while the Check all sheet is open in it.
  var AWAY_MS = 60 * 1000;
  var hiddenAt = null;
  var redrawnAt = 0;

  function redrawList() {
    var list = document.getElementById("want-list");
    if (!list || !window.htmx) return;
    if (document.querySelector("#sweep-runner.sweeping")) return;
    if (list.querySelector("dialog[open]")) return;
    // Back from the browser's memory fires both events below; one redraw.
    if (Date.now() - redrawnAt < 2000) return;
    redrawnAt = Date.now();
    htmx.ajax("GET", "/books/list", { target: "#want-list", swap: "outerHTML" });
  }

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") {
      hiddenAt = Date.now();
      return;
    }
    if (hiddenAt !== null && Date.now() - hiddenAt >= AWAY_MS) redrawList();
    hiddenAt = null;
  });

  window.addEventListener("pageshow", function (event) {
    if (event.persisted) redrawList();
  });

  // With "Under limit" on, a check can change which books belong in the
  // list, and redrawing one row at a time can't add or remove one. So the
  // list draws itself again when the list changes, once no check is running
  // (S68, #240).
  document.body.addEventListener("list-changed", function () {
    if (new URLSearchParams(window.location.search).get("show") === "under") {
      redrawList();
    }
  });
})();
