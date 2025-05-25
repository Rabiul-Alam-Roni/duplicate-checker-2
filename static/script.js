async function checkDuplicate() {
    let doi = document.getElementById("doi").value.trim();
    let title = document.getElementById("title").value.trim();
    let url = document.getElementById("url").value.trim();

    if (!doi) {
        document.getElementById("response").innerText = "DOI is required.";
        return;
    }

    let formData = new FormData();
    formData.append("doi", doi);
    formData.append("title", title);
    formData.append("url", url);

    let response = await fetch('/check_article', {
        method: 'POST',
        body: formData
    });

    let result = await response.json();

    if (result.status === "duplicate") {
        document.getElementById("response").innerText = "❌ " + result.message;
        document.getElementById("response").style.color = "red";
    } else {
        document.getElementById("response").innerText = "✅ " + result.message;
        document.getElementById("response").style.color = "green";
    }
}
