/* Archive: a row shows the preview of its fax beside it while the mouse is over it (the original's previewImage in avantfax.js).
 * The row is marked with data-preview (the image address) and highlighted; the box #faxpreview follows the row. */
(function (root) {
  var HIGHLIGHT = '#FFF0B6';
  var BOX_HEIGHT = 140;                                   // room the box needs under its top edge (the original's 130/140)

  /* Where the box goes: left of the row (110 px), at the row's top, lifted when the page ends too soon below it. */
  function place(rowLeft, rowTop, pageHeight) {
    var left = Math.max(rowLeft - 110, 0);
    var top = rowTop;
    if (pageHeight - top < 130) top = Math.max(pageHeight - BOX_HEIGHT, 0);
    return { left: left, top: top };
  }

  function init(doc, win) {
    var box = doc.getElementById('faxpreview');
    if (!box) return;
    var image = box.querySelector('img');

    function offset(el) {
      var rect = el.getBoundingClientRect();
      return { left: rect.left + (win.pageXOffset || 0), top: rect.top + (win.pageYOffset || 0) };
    }

    function show(row) {
      image.setAttribute('src', row.getAttribute('data-preview'));
      box.classList.remove('hidden');
      row.style.background = HIGHLIGHT;
    }

    function hide(row) {
      box.classList.add('hidden');
      row.style.background = '';
    }

    function follow(row) {
      var at = offset(row);
      var spot = place(at.left, at.top, doc.documentElement.scrollHeight);
      box.style.left = spot.left + 'px';
      box.style.top = spot.top + 'px';
    }

    doc.querySelectorAll('tr[data-preview]').forEach(function (row) {
      row.addEventListener('mouseover', function () { show(row); follow(row); });
      row.addEventListener('mousemove', function () { follow(row); });
      row.addEventListener('mouseout', function () { hide(row); });
    });
  }

  root.NamiPreview = { place: place, init: init };
  if (typeof document !== 'undefined' && root === (typeof window !== 'undefined' ? window : null)) {
    init(document, window);
  }
})(typeof window !== 'undefined' ? window : globalThis);
