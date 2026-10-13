/* Two-factor pages: [data-copy] copies its value to the clipboard, [data-download] saves its value as a text file
 * (named by data-filename). Both work from what the page already shows; nothing is sent to the server. */
(function () {
  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    return new Promise(function (resolve, reject) {                       // plain http (not localhost): the old way
      var area = document.createElement('textarea');
      area.value = text; area.style.position = 'fixed'; area.style.opacity = '0';
      document.body.appendChild(area); area.select();
      try { document.execCommand('copy') ? resolve() : reject(); } catch (e) { reject(e); } finally { document.body.removeChild(area); }
    });
  }
  document.querySelectorAll('[data-copy]').forEach(function (button) {
    var label = button.textContent;
    button.addEventListener('click', function () {
      copy(button.getAttribute('data-copy')).then(function () {
        button.textContent = button.getAttribute('data-done') || '✓';
        setTimeout(function () { button.textContent = label; }, 1500);
      }).catch(function () {});
    });
  });
  document.querySelectorAll('[data-download]').forEach(function (button) {
    button.addEventListener('click', function () {
      var blob = new Blob([button.getAttribute('data-download')], { type: 'text/plain;charset=utf-8' });
      var link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = button.getAttribute('data-filename') || 'namifax-2fa.txt';
      document.body.appendChild(link); link.click(); document.body.removeChild(link);
      setTimeout(function () { URL.revokeObjectURL(link.href); }, 1000);
    });
  });
})();
