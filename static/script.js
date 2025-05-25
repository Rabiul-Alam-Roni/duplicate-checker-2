async function checkDuplicate() {
    let doi = document.getElementById("doi").value.trim();
    let title = document.getElementById("title").value.trim();
    let url = document.getElementById("url").value.trim();
    let hardness = document.getElementById("hardness").checked;
    let whc = document.getElementById("whc").checked;

    if (!doi) {
        alert("DOI is required!");
        return;
    }

    let formData = new FormData();
    formData.append("doi", doi);
    formData.append("title", title);
    formData.append("url", url);
    formData.append("hardness", hardness);
    formData.append("whc", whc);

    let response = await fetch('/check_article', { method: 'POST', body: formData });
    let result = await response.json();

    let responseDiv = document.getElementById("response");
    responseDiv.innerHTML = result.message;
    responseDiv.style.color = (result.status === "duplicate") ? "#d9534f" : "#5cb85c";
}

async function uploadFile() {
    let fileInput = document.getElementById("fileUpload");
    if (!fileInput.files[0]) {
        alert("Please select a file first!");
        return;
    }

    let formData = new FormData();
    formData.append("file", fileInput.files[0]);

    let response = await fetch('/upload_file', { method: 'POST', body: formData });
    let result = await response.json();

    let responseDiv = document.getElementById("response");
    responseDiv.innerHTML = `Added: ${result.added}, Duplicates: ${result.duplicates}`;
    responseDiv.style.color = "#0275d8";
}
