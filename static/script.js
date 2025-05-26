async function checkDuplicate() {
    const doi = document.getElementById("doi").value;
    const title = document.getElementById("title").value;
    const tags = document.getElementById("tags").value;
    const hardness = document.getElementById("hardness").checked;
    const whc = document.getElementById("whc").checked;

    let formData = new FormData();
    formData.append("doi", doi);
    formData.append("title", title);
    formData.append("tags", tags);
    formData.append("hardness", hardness);
    formData.append("whc", whc);

    const res = await fetch('/check_article', {
        method: 'POST',
        body: formData
    });

    const result = await res.json();
    const responseDiv = document.getElementById("response");
    responseDiv.innerText = result.message;
    responseDiv.style.color = (result.status === 'duplicate') ? '#e74c3c' : '#27ae60';
}

async function uploadFile() {
    const fileInput = document.getElementById("fileUpload");
    if (!fileInput.files[0]) {
        alert("Please select a file first!");
        return;
    }

    let formData = new FormData();
    formData.append("file", fileInput.files[0]);

    const res = await fetch('/upload_file', {
        method: 'POST',
        body: formData
    });

    const result = await res.json();
    const fileResponseDiv = document.getElementById("fileResponse");
    fileResponseDiv.innerText = `Added: ${result.added}, Duplicates: ${result.duplicates}`;
    fileResponseDiv.style.color = '#2980b9';
}
