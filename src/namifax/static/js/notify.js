/* New-fax notification and modem status, like the original's avantfax.js / ajaxmodemstatus.js:
 * the unread count is fetched every 30 seconds (data-inbox-poll), the modem status every 20 seconds (data-modem-poll).
 * A new fax updates the badge and the title. With FOCUS_ON_NEW_FAX (data-focus-new-fax on the body) the window is brought
 * forward; with FOCUS_ON_NEW_FAX_POPUP (data-popup-new-fax) the fax is announced by a browser notification, if it was
 * allowed, and the user's sound file is played. Both are off by default, as in the original. There is no modal alert. */
(function () {
  var body = document.body;
  if (!body || !window.fetch) return;

  var inboxEvery = parseInt(body.getAttribute('data-inbox-poll') || '30', 10) * 1000;
  var modemEvery = parseInt(body.getAttribute('data-modem-poll') || '20', 10) * 1000;
  var baseTitle = document.title.replace(/^\(\d+\)\s*/, '');
  var current = null;

  function setBadges(count) {
    document.querySelectorAll('[data-inbox-count]').forEach(function (el) { el.textContent = count; });
    document.title = (count > 0 ? '(' + count + ') ' : '') + baseTitle;
  }

  /* Announce a new fax as configured and say when it is done (a playing sound is waited for, so that a reload does not cut it). */
  function announce(count, sound, done) {
    if (body.getAttribute('data-focus-new-fax')) {
      try { window.focus(); } catch (e) {}
    }
    if (!body.getAttribute('data-popup-new-fax')) return done();
    if (window.Notification && Notification.permission === 'granted') {
      try { new Notification('NamiFAX', { body: count + ' ' + (body.getAttribute('data-new-fax') || 'new fax') }); } catch (e) {}
    }
    if (!sound) return done();
    try {
      var beep = new Audio('/audio/' + encodeURIComponent(sound));
      beep.addEventListener('ended', done);
      beep.addEventListener('error', done);
      var started = beep.play();
      if (started && started.catch) started.catch(done);
      setTimeout(done, 15000);                               // (never wait for ever)
    } catch (e) { done(); }
  }

  /* On the Inbox page the list follows the count, as the original's performInboxCheck reloads it; other pages only count. */
  function reloadInbox() {
    if (body.getAttribute('data-page') === 'inbox') window.location.reload();
  }

  function checkInbox() {
    fetch('/ajax/inbox?randid=' + Math.random(), { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.text() : ''; })
      .then(function (text) {
        var parts = text.trim().split('|');
        var count = parseInt(parts[0], 10);
        if (isNaN(count)) return;
        var before = current;
        current = count;
        setBadges(count);
        if (before === null || count === before) return;
        var once = false;
        function done() { if (!once) { once = true; reloadInbox(); } }
        if (count > before) announce(count, parts[1], done); else done();
      })
      .catch(function () {});
  }

  function checkModems() {
    var holder = document.querySelector('[data-modems]');
    if (!holder) return;
    var devices = (holder.getAttribute('data-modems') || '').split(',').filter(Boolean);
    if (!devices.length) return;
    fetch('/ajax/modemstatus?randid=' + Math.random() + '&modems=' + encodeURIComponent(devices.join(',')), { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.text() : ''; })
      .then(function (text) {
        var rows = new DOMParser().parseFromString(text, 'text/xml').getElementsByTagName('row');
        var summary = [];
        for (var i = 0; i < rows.length; i++) {
          var device = rows[i].getElementsByTagName('modem')[0].textContent;
          var status = rows[i].getElementsByTagName('status')[0].textContent;
          var css = rows[i].getElementsByTagName('class')[0].textContent;
          document.querySelectorAll('[data-modem="' + device + '"]').forEach(function (el) {
            el.textContent = status;
            el.className = el.className.replace(/\bmodem-\w+\b/g, '') + ' ' + css;
          });
          summary.push(status);
        }
        var line = holder.querySelector('[data-modem-summary]');
        if (line && summary.length) line.textContent = summary.length === 1 ? summary[0] : summary.length + ' ' + (holder.getAttribute('data-lines') || 'lines');
      })
      .catch(function () {});
  }

  var badge = document.querySelector('[data-inbox-count]');
  current = badge ? parseInt(badge.textContent, 10) || 0 : 0;
  setBadges(current);
  setInterval(checkInbox, inboxEvery);
  setInterval(checkModems, modemEvery);
  if (window.Notification && Notification.permission === 'default') {
    document.addEventListener('click', function ask() {
      document.removeEventListener('click', ask);
      try { Notification.requestPermission(); } catch (e) {}
    });
  }
})();
