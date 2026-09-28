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
        if (large) {
          var img = dialog.querySelector("img");
          if (img) {
            img.dataset.fallback = opener.getAttribute("data-photo-small") || large;
            img.src = large;
          }
        }
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
