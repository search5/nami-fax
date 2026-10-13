/* Send Fax page: the cover page options fold away with the cover page switch (data-folds) and the chosen files are collected in a
 * list that can be added to and removed from (the original's coverpage toggle and MultiSelector). */
(function () {
  // --- cover page switch ----------------------------------------------------------------------------------------------
  document.querySelectorAll('input[data-folds]').forEach(function (box) {
    var block = document.getElementById(box.getAttribute('data-folds'));
    if (!block) return;
    function apply() { block.classList.toggle('hidden', !box.checked); }
    box.addEventListener('change', apply);
    apply();
  });

  // --- several files --------------------------------------------------------------------------------------------------
  var input = document.querySelector('input[type=file][data-list]');
  if (!input || !window.DataTransfer) return;
  var list = document.getElementById(input.getAttribute('data-list'));
  var label = document.getElementById('file-label');
  var max = parseInt(input.getAttribute('data-max-bytes') || '0', 10);
  var chosen = [];

  function size(n) { return n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(0) + ' KB' : (n / 1048576).toFixed(1) + ' MB'; }

  function sync() {
    var transfer = new DataTransfer();
    chosen.forEach(function (f) { transfer.items.add(f); });
    input.files = transfer.files;
    list.innerHTML = '';
    chosen.forEach(function (file, index) {
      var row = document.createElement('div');
      row.className = 'flex items-center justify-between gap-3 px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-sm';
      var name = document.createElement('span');
      name.textContent = file.name + ' (' + size(file.size) + ')';
      if (max && file.size > max) name.className = 'text-rose-600';
      var remove = document.createElement('button');
      remove.type = 'button';
      remove.textContent = '×';
      remove.className = 'text-slate-400 hover:text-rose-600 font-bold';
      remove.addEventListener('click', function () { chosen.splice(index, 1); sync(); });
      row.appendChild(name);
      row.appendChild(remove);
      list.appendChild(row);
    });
    if (label) {
      label.textContent = chosen.length ? chosen.length + ' file(s)' : label.getAttribute('data-empty') || label.textContent;
      label.classList.toggle('text-blue-700', chosen.length > 0);
    }
  }

  if (label) label.setAttribute('data-empty', label.textContent);
  input.addEventListener('change', function () {
    var picked = Array.prototype.slice.call(input.files);
    picked.forEach(function (f) {
      var known = chosen.some(function (c) { return c.name === f.name && c.size === f.size && c.lastModified === f.lastModified; });
      if (!known) chosen.push(f);
    });
    sync();
  });
})();
