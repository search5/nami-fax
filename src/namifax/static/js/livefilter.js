/* Filter a list as you type: <input data-live-filter="#id"> hides the rows (tr, li or label) of the element #id that do not contain
 * the typed text (the original's address book, archive and distribution list filters). */
(function () {
  document.querySelectorAll('input[data-live-filter]').forEach(function (box) {
    var holder = document.querySelector(box.getAttribute('data-live-filter'));
    if (!holder) return;
    box.addEventListener('input', function () {
      var q = box.value.trim().toLowerCase();
      holder.querySelectorAll('tbody tr, li, label, a[data-filter-item]').forEach(function (row) {
        row.style.display = !q || row.textContent.toLowerCase().indexOf(q) >= 0 ? '' : 'none';
      });
    });
  });
})();
