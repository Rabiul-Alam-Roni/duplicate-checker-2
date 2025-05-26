async function checkDuplicate() {
    let formData = new FormData();
    formData.append("doi", document.getElementById("doi").value.trim());
    formData.append("title", document.getElementById("title").value.trim());
    formData.append("url", document.getElementById("url").value.trim());
    formData.append("hardness", document.getElementById("hardness").checked);
    formData.append("whc", document.getElementById("whc").checked);

    let res = await fetch('/check_article', {method: 'POST', body: formData});
    let result = await res.json();
    document.getElementById("response").innerText = result.message;
}

async function uploadFile() {
    let fileInput = document.getElementById("fileUpload");
    if (!fileInput.files[0]) {
        alert("Choose file first!");
        return;
    }
    let formData = new FormData();
    formData.append("file", fileInput.files[0]);

    let res = await fetch('/upload_file', {method: 'POST', body: formData});
    let result = await res.json();
    document.getElementById("response").innerText =
        `Added: ${result.added}, Duplicates: ${result.duplicates}`;
    refreshFileList();
}
