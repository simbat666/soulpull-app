// Compatibility loader for older cached HTML that referenced /static/app.js
(() => {
  const s = document.createElement('script');
  s.src = '/static/js/app.js?v=20251228-6';
  s.defer = true;
  document.head.appendChild(s);
})();


