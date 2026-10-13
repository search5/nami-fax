/* Scheduled Tasks page: the start/stop box refreshes by itself and a click on Start/Stop changes it at once, without reloading. */
(function () {
  var box = document.getElementById('scheduler-state');
  if (!box || !window.fetch) return;
  var url = box.getAttribute('data-state-url');
  var busy = false;

  function show(html) { box.innerHTML = html; }

  function refresh() {
    if (busy) return;
    fetch(url, { credentials: 'same-origin' }).then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) { if (html && !busy) show(html); }).catch(function () {});
  }

  box.addEventListener('submit', function (event) {
    var form = event.target.closest('form[data-scheduler-action]');
    if (!form) return;
    event.preventDefault();
    busy = true;
    // (form.action would be the <input name="action">, so the attribute is read)
    fetch(form.getAttribute('action'), { method: 'POST', body: new URLSearchParams(new FormData(form)), credentials: 'same-origin',
                         headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.text(); }).then(show).catch(function () { HTMLFormElement.prototype.submit.call(form); })
      .finally(function () { busy = false; });
  });

  setInterval(refresh, 3000);
})();

/* The per-job blocks (last result, Run now / Stop): a click acts without reloading and a running job is watched until it ends. */
(function () {
  var cards = document.querySelectorAll('[data-job-status]');
  if (!cards.length || !window.fetch) return;

  function swap(html) {
    var doc = new DOMParser().parseFromString(html, 'text/html');
    doc.querySelectorAll('[data-job-status]').forEach(function (fresh) {
      var old = document.querySelector('[data-job-status="' + fresh.getAttribute('data-job-status') + '"]');
      if (old) old.replaceWith(fresh);
    });
  }

  function refresh() {
    fetch('/admin/scheduler/jobs', { credentials: 'same-origin' }).then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) { if (html) swap(html); }).catch(function () {});
  }

  document.addEventListener('submit', function (event) {
    var form = event.target.closest('form[data-job-action]');
    if (!form) return;
    event.preventDefault();
    fetch(form.getAttribute('action'), { method: 'POST', body: new URLSearchParams(new FormData(form)), credentials: 'same-origin',
                                          headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function () { refresh(); })
      .catch(function () { HTMLFormElement.prototype.submit.call(form); });
  });

  setInterval(refresh, 2000);
})();
