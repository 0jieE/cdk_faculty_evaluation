// Small enhancements; every page works without this file.
(function () {
  "use strict";

  function setMenu(sidebar, open) {
    sidebar.setAttribute("data-open", String(open));
    document.querySelectorAll("button[data-menu-toggle]").forEach(function (b) {
      b.setAttribute("aria-expanded", String(open));
    });
  }

  function closeSearch(except) {
    document.querySelectorAll("[data-search].is-open").forEach(function (f) {
      if (f !== except) f.classList.remove("is-open");
    });
  }

  document.addEventListener("click", function (event) {
    // Mobile menu toggle (staff sidebar); the scrim behind the drawer closes it too
    var toggle = event.target.closest("[data-menu-toggle]");
    if (toggle) {
      var sidebar = document.getElementById(toggle.getAttribute("aria-controls"));
      setMenu(sidebar, sidebar.getAttribute("data-open") !== "true");
      return;
    }
    var dismiss = event.target.closest("[data-dismiss]");
    if (dismiss) {
      dismiss.closest(".message").remove();
    }
    // Clicking elsewhere closes the search dropdown and the account menu
    closeSearch(event.target.closest("[data-search]"));
    document.querySelectorAll("[data-usermenu][open]").forEach(function (menu) {
      if (!menu.contains(event.target)) menu.removeAttribute("open");
    });
  });

  // Topbar search: show the dropdown while the field is in use
  document.addEventListener("focusin", function (event) {
    var form = event.target.closest("[data-search]");
    closeSearch(form);
    if (form) form.classList.add("is-open");
  });
  document.addEventListener("htmx:afterSwap", function (event) {
    var form = event.detail.target.closest && event.detail.target.closest("[data-search]");
    if (form && form.contains(document.activeElement)) form.classList.add("is-open");
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeSearch(null);
      document.querySelectorAll("[data-usermenu][open]").forEach(function (m) {
        m.removeAttribute("open");
        m.querySelector("summary").focus();
      });
      var sidebar = document.querySelector(".sidebar[data-open='true']");
      if (sidebar) setMenu(sidebar, false);
      return;
    }
    // Up/down arrows move between the search field and its results
    var form = event.target.closest("[data-search]");
    if (!form || (event.key !== "ArrowDown" && event.key !== "ArrowUp")) return;
    var items = [form.querySelector("input")].concat(Array.prototype.slice.call(form.querySelectorAll(".search-hit")));
    if (items.length < 2) return;
    var i = items.indexOf(document.activeElement);
    var next = items[Math.min(Math.max(i + (event.key === "ArrowDown" ? 1 : -1), 0), items.length - 1)];
    event.preventDefault();
    next.focus();
  });

  // Ask before destructive actions: <button data-confirm="Remove Juan from IT101?">
  document.addEventListener("submit", function (event) {
    var button = event.submitter;
    var text = (button && button.getAttribute("data-confirm")) || event.target.getAttribute("data-confirm");
    if (text && !window.confirm(text)) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);

  // Evaluation form: live "answered" counter and jump to the first unanswered question
  function initEvaluation(root) {
    var form = root.querySelector("[data-evaluation]");
    if (!form || form.dataset.ready) return;
    form.dataset.ready = "1";
    var questions = Array.prototype.slice.call(form.querySelectorAll(".question[data-question]"));
    var countEl = document.querySelector("[data-answered]");
    var meter = document.querySelector("[data-answered-meter]");

    function update() {
      var answered = questions.filter(function (q) {
        var done = !!q.querySelector("input[type=radio]:checked");
        if (done) q.classList.remove("unanswered");
        return done;
      }).length;
      if (countEl) countEl.textContent = answered;
      if (meter) meter.style.width = (100 * answered / Math.max(questions.length, 1)) + "%";
    }
    form.addEventListener("change", update);
    update();
  }

  // Evaluation submit: point at missing answers, otherwise ask before saving. Capture phase so
  // nothing (htmx included) sees the submit until the student presses "Yes, submit".
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form.matches("[data-evaluation]")) return;
    var button = event.submitter;
    var dialog = form.querySelector("[data-confirm-dialog]");
    var stop = function () { event.preventDefault(); event.stopImmediatePropagation(); };

    var questions = Array.prototype.slice.call(form.querySelectorAll(".question[data-question]"));
    var missing = questions.filter(function (q) { return !q.querySelector("input[type=radio]:checked"); });
    if (missing.length) {
      stop();
      if (dialog && dialog.open) dialog.close();
      missing.forEach(function (q) { q.classList.add("unanswered"); });
      missing[0].scrollIntoView({ behavior: "smooth", block: "center" });
      var first = missing[0].querySelector("input[type=radio]");
      if (first) first.focus({ preventScroll: true });
      return;
    }

    if (!dialog || typeof dialog.showModal !== "function") return; // the server asks instead
    if (dialog.open && button && button.closest("[data-confirm-dialog]")) {
      // Confirmed in the dialog: block a second click while the request is in flight
      setTimeout(function () { button.disabled = true; }, 0);
      return;
    }
    stop();
    var overall = form.querySelector("[name^='ras_']:checked");
    var slot = dialog.querySelector("[data-confirm-overall]");
    if (slot) slot.textContent = overall ? ", with an overall appraisal of " + overall.value : "";
    dialog.showModal();
  }, true);

  document.addEventListener("click", function (event) {
    var close = event.target.closest("[data-dialog-close]");
    if (close) close.closest("dialog").close();
  });

  document.addEventListener("DOMContentLoaded", function () { initEvaluation(document); });
  document.addEventListener("htmx:load", function (event) { initEvaluation(event.detail.elt); });
})();
