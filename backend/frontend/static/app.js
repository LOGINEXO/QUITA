(() => {
  const loginView = document.getElementById("login-view");
  const dashboard = document.getElementById("dashboard-view");
  const form = document.getElementById("login-form");
  const message = document.getElementById("login-message");
  const submit = document.getElementById("submit-button");
  const password = document.getElementById("password");
  const email = document.getElementById("email");
  const safeMessage = (text, type = "") => { message.textContent = text; message.className = "message" + (type ? " " + type : ""); };
  async function api(path, options = {}) {
    const response = await fetch(path, { credentials: "same-origin", ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
    let data = {};
    try { data = await response.json(); } catch {}
    if (!response.ok) { const detail = typeof data.detail === "string" ? data.detail : "Não foi possível concluir a solicitação."; throw Object.assign(new Error(detail), { status: response.status }); }
    return data;
  }
  function showDashboard(user) {
    loginView.classList.add("hidden");
    dashboard.classList.remove("hidden");
    document.getElementById("admin-email").textContent = user.email || "";
  }
  async function restoreSession() {
    try { const user = await api("/auth/admin/me", { method: "GET", headers: {} }); showDashboard(user); } catch {}
  }
  form.addEventListener("submit", async event => {
    event.preventDefault();
    safeMessage("");
    submit.disabled = true;
    submit.querySelector("span").textContent = "Validando acesso…";
    try {
      const user = await api("/auth/admin/login", { method: "POST", body: JSON.stringify({ email: email.value.trim(), password: password.value }) });
      password.value = "";
      showDashboard(user);
    } catch (error) {
      if (error.status === 401) safeMessage("E-mail ou senha inválidos. Confira os dados e tente novamente.");
      else if (error.status === 429) safeMessage("Muitas tentativas em sequência. Aguarde um pouco antes de tentar novamente.");
      else if (error.status === 503) safeMessage("O serviço de autenticação está indisponível ou não está configurado. Verifique o estado do servidor.");
      else safeMessage(error.message || "Falha de conexão. Tente novamente.");
    } finally {
      submit.disabled = false;
      submit.querySelector("span").textContent = "Entrar no painel";
    }
  });
  document.getElementById("toggle-password").addEventListener("click", () => {
    const reveal = password.type === "password";
    password.type = reveal ? "text" : "password";
    document.getElementById("toggle-password").setAttribute("aria-label", reveal ? "Ocultar senha" : "Mostrar senha");
  });
  document.getElementById("logout-button").addEventListener("click", async () => {
    try { await api("/auth/admin/logout", { method: "POST", body: "{}" }); } catch {}
    dashboard.classList.add("hidden");
    loginView.classList.remove("hidden");
    password.value = "";
    safeMessage("Sessão encerrada.", "success");
  });
  document.getElementById("check-api").addEventListener("click", async () => {
    const target = document.getElementById("api-status");
    target.textContent = "Verificando conexão…";
    try { await api("/health", { method: "GET", headers: {} }); target.textContent = "API acessível e respondendo normalmente."; }
    catch { target.textContent = "Não foi possível verificar a API agora. Tente novamente."; }
  });
  restoreSession();
})();