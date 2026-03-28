/* base.js — Image Traditional */

document.addEventListener('DOMContentLoaded', function () {

  // Contact dropdown
  const contactToggle = document.getElementById('contactToggle');
  const contactMenu = document.getElementById('contactMenu');

  if (contactToggle && contactMenu) {
    contactToggle.addEventListener('click', function (e) {
      e.stopPropagation();
      const isOpen = contactMenu.classList.toggle('open');
      contactToggle.setAttribute('aria-expanded', isOpen);
    });

    document.addEventListener('click', function (e) {
      if (!contactToggle.contains(e.target) && !contactMenu.contains(e.target)) {
        contactMenu.classList.remove('open');
        contactToggle.setAttribute('aria-expanded', 'false');
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        contactMenu.classList.remove('open');
        contactToggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // Auto-dismiss alerts after 5s
  document.querySelectorAll('.alert').forEach(function (alert) {
    setTimeout(function () { alert.remove(); }, 5000);
  });

});