// The little the controls need that HTML cannot do alone. S30, #110.
//
// Everything here works on markup the macros in templates/_ui.html emit, by
// data attributes, so no screen writes its own script. No framework and no
// build step (decision 2). Without JavaScript the page still reads; only the
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
      if (dialog && typeof dialog.showModal === "function") {
        event.preventDefault();
        var large = opener.getAttribute("data-photo");
        if (large) fillPhotos(dialog, opener, large);
        dialog.showModal();
      }
      return;
    }

    // [data-close] inside a dialog closes it.
    var closer = event.target.closest("[data-close]");
    if (closer) {
      var parent = closer.closest("dialog");
      if (parent) parent.close();
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
