async function register() {
    await fetch('/register', {method: 'POST', body: new URLSearchParams({
        email: document.getElementById("reg_email").value,
        password: document.getElementById("reg_pass").value
    })});
    alert("Registered! Please login.");
}

async function login() {
    let res = await fetch('/login', {method: 'POST', body: new URLSearchParams({
        email: document.getElementById("login_email").value,
        password: document.getElementById("login_pass").value
    })});
    if(res.ok){ alert("Logged in!"); refreshActiveUsers(); }
    else{ alert("Login failed!"); }
}

async function logout() {
    await fetch('/logout', {method: 'POST', body: new URLSearchParams({
        email: document.getElementById("login_email").value
    })});
    alert("Logged out!"); refreshActiveUsers();
}

async function refreshActiveUsers(){
    let res = await fetch('/active_users');
    let users = await res.json();
    document.getElementById("activeUsers").innerHTML = 
        users.map(u => `<li>${u.email} (active: ${u.last_active})</li>`).join('');
}

window.onload = refreshActiveUsers;
