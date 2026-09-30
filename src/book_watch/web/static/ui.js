// The little the controls need that HTML cannot do alone. S30, #110.
//
// Everything here works on markup the macros in templates/_ui.html emit, by
// data attributes, so no screen writes its own script. No framework and no
// build step. Without JavaScript the page still reads; only the
// sheets and the enlarged photo need it.

(function () {
  "use strict";

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
})();
