/* Admin > Storage: show only what belongs to the chosen provider (local: nothing; S3: the connection fields). */
(function () {
  var select = document.querySelector('select[data-provider-switch]');
  if (!select) return;
  var fields = document.getElementById(select.getAttribute('data-provider-switch'));
  var note = document.getElementById('cloud-note-LOCAL');
  var test = document.getElementById('cloud-test');

  function apply() {
    var kind = select.value, cloud = kind === 'S3';
    if (fields) fields.classList.toggle('hidden', !cloud);
    if (note) note.classList.toggle('hidden', cloud);
    if (test) test.classList.toggle('hidden', !cloud);
  }
  select.addEventListener('change', apply);
  apply();
})();
