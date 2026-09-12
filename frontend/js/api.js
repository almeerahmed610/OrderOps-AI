const API_BASE = window.location.origin;

function getToken() {
    return localStorage.getItem("access_token") || "";
}

function authHeaders(extra = {}) {
    const token = getToken();

    if (token) {
        return {
            ...extra,
            Authorization: `Bearer ${token}`
        };
    }

    return extra;
}

async function apiFetch(path, options = {}) {
    const config = {
        ...options,
        headers: authHeaders(options.headers || {})
    };

    if (config.body && typeof config.body !== "string") {
        config.headers["Content-Type"] = "application/json";
        config.body = JSON.stringify(config.body);
    }

    const response = await fetch(
        `${API_BASE}${path}`,
        config
    );

    let data = null;

    try {
        data = await response.json();
    } catch (error) {
        data = null;
    }

    if (response.status === 401) {
        localStorage.removeItem("access_token");

        if (!window.location.pathname.endsWith("login.html")) {
            window.location.href = "login.html";
        }

        throw new Error("Session expired. Please login again.");
    }

    if (!response.ok) {
        throw new Error(
            data?.detail ||
            `Request failed with status ${response.status}`
        );
    }

    return data;
}


function money(value) {
    return `Rs. ${Number(value || 0).toLocaleString(
        "en-PK",
        {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }
    )}`;
}


function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


async function getCurrentUser() {
    return await apiFetch("/api/auth/me");
}


function logout() {
    localStorage.removeItem("access_token");
    window.location.href = "login.html";
}


function requireAuth() {
    const token = getToken();

    if (!token) {
        window.location.href = "login.html";
        return false;
    }

    return true;
}