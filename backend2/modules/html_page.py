HTML_PAGE = """
<!doctype html>
<html lang=\"vi\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Car Rental Demo</title>
  <style>
    body { font-family: Arial, sans-serif; background:#f5f6f8; margin:0; padding:24px; }
    .wrap { max-width: 1100px; margin: 0 auto; }
    .card { background:white; border-radius:14px; padding:18px; box-shadow:0 1px 3px rgba(0,0,0,.08); margin-bottom:16px; }
    .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap:16px; }
    a.button, button { display:inline-block; width:100%; box-sizing:border-box; padding:12px 14px; margin-top:8px; border-radius:10px; text-align:center; text-decoration:none; border:none; cursor:pointer; background:#111827; color:white; }
    button.alt, a.button.alt { background:#2563eb; }
    pre { background:#0f172a; color:#e2e8f0; padding:12px; border-radius:10px; overflow:auto; }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"card\">
      <h1>CarRentalAutoPayment</h1>
      <p>Route <code>/</code> van duoc giu de tuong thich. Ban test day du nhanh nhat tai cac trang trong <code>/frontend</code>.</p>
    </div>
    <div class=\"grid\">
      <div class=\"card\">
        <h3>Full Console</h3>
        <a class=\"button alt\" href=\"/frontend/index.html\">Mo full console</a>
      </div>
      <div class=\"card\">
        <h3>Owner</h3>
        <a class=\"button\" href=\"/frontend/owner.html\">Mo owner page</a>
      </div>
      <div class=\"card\">
        <h3>Renter</h3>
        <a class=\"button\" href=\"/frontend/renter.html\">Mo renter page</a>
      </div>
      <div class=\"card\">
        <h3>Auth</h3>
        <a class=\"button\" href=\"/frontend/auth.html\">Mo auth page</a>
      </div>
    </div>
    <div class=\"card\">
      <h3>Quick API Buttons</h3>
      <button onclick=\"runApi('/api/overview')\">Load Overview</button>
      <button class=\"alt\" onclick=\"runApi('/api/node/chain')\">Load Chain</button>
      <button onclick=\"runApi('/api/node/reconcile', 'POST')\">Run Reconcile</button>
    </div>
    <div class=\"card\">
      <h3>Ket qua</h3>
      <pre id=\"result\">Chua co du lieu</pre>
    </div>
  </div>
<script>
async function runApi(url, method='GET') {
  try {
    const res = await fetch(url, { method });
    const data = await res.json();
    document.getElementById('result').textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    document.getElementById('result').textContent = error.message;
  }
}
</script>
</body>
</html>
"""
