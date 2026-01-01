// Compatibility loader for older cached HTML that referenced /static/app.js
(() => {
  const s = document.createElement('script');
  s.src = '/static/js/app.js?v=app-20260101-2';
  s.defer = true;
  document.head.appendChild(s);
})();


