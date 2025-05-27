async function checkDuplicate() {
    const formData = new FormData();
    formData.append("doi", document.getElementById("doi").value);
    formData.append("title", document.getElementById("title").value);
    formData.append("tags", document.getElementById("tags").value);
    formData.append("hardness", document.getElementById("hardness").checked);
    formData.append("whc", document.getElementById("whc").checked);

    const res = await fetch('/check_article', {method: 'POST', body: formData});
    const result = await res.json();

    const responseDiv = document.getElementById("response");
    responseDiv.textContent = result.message;
    responseDiv.style.color = result.status === 'duplicate' ? '#e74c3c' : '#27ae60';
}

async function uploadFile() {
    const fileInput = document.getElementById("fileUpload");
    if (!fileInput.files[0]) {
        alert("Please select a file first!");
        return;
    }
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    const res = await fetch('/upload_file', {method: 'POST', body: formData});
    const result = await res.json();

    const fileResponseDiv = document.getElementById("fileResponse");
    fileResponseDiv.textContent = `Added: ${result.added}, Duplicates: ${result.duplicates}`;
    fileResponseDiv.style.color = '#2980b9';
}
