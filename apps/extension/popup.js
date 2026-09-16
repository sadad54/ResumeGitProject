document.getElementById("capture").addEventListener("click", async () => {
  const button = document.getElementById("capture"); button.disabled = true;
  try {
    const result = await chrome.runtime.sendMessage({ type: "capture-active" });
    document.getElementById("status").textContent = result?.ok ? "Opened ProofHire. Paste the description to continue." : "Could not open ProofHire. Try again.";
  } catch { document.getElementById("status").textContent = "Capture failed. Try reopening the extension."; }
  finally { button.disabled = false; }
});
