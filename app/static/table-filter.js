// Filter a table's rows as you type: a <table data-filterable id="x"> and controls with
// data-filter="x". A text box matches anywhere in the row (ignoring accents and case); a
// <select data-filter-key="role"> matches the row's data-role. data-filter-count="x"
// shows how many rows are left. No server round trip: the whole list is on the page.
(function () {
  function norm(text) {
    return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
  }
  document.querySelectorAll("table[data-filterable]").forEach(function (table) {
    var controls = document.querySelectorAll('[data-filter="' + table.id + '"]');
    var count = document.querySelector('[data-filter-count="' + table.id + '"]');
    function apply() {
      var shown = 0;
      table.querySelectorAll("tbody tr").forEach(function (row) {
        var ok = true;
        controls.forEach(function (control) {
          var wanted = norm(control.value);
          if (!wanted) return;
          var key = control.dataset.filterKey;
          ok = ok && (key ? norm(row.dataset[key] || "") === wanted
                          : norm(row.textContent).indexOf(wanted) !== -1);
        });
        row.hidden = !ok;
        if (ok) shown += 1;
      });
      if (count) count.textContent = shown;
    }
    controls.forEach(function (control) {
      control.addEventListener("input", apply);
      control.addEventListener("change", apply);
    });
    apply();
  });
})();
