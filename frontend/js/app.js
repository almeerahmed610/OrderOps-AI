// OrderOps AI common frontend compatibility file

function isLoggedIn() {
    return !!localStorage.getItem("access_token");
}

function requireLogin() {
    if (!isLoggedIn()) {
        window.location.href = "login.html";
    }
}

function logoutUser() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    window.location.href = "login.html";
}

function getStoredUser() {
    try {
        return JSON.parse(localStorage.getItem("user") || "null");
    } catch {
        return null;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const user = getStoredUser();

    document.querySelectorAll("[data-user-name]").forEach(el => {
        el.textContent = user?.full_name || "User";
    });

    document.querySelectorAll("[data-logout]").forEach(btn => {
        btn.addEventListener("click", logoutUser);
    });
});