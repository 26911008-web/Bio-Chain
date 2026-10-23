/* Pemindai QR kamera, umpan balik audio & generator QR mandiri.
 *
 * Bergantung pada global app.js: $, api, showToast, esc, STATE.
 *
 * Dipindah dari app.js (audit 23 Okt 2026, CLAUDE.md §3.1). Skrip klasik dimuat SETELAH app.js: fungsi
 * deklarasi tetap global (window.*) sehingga handler deklaratif data-onclick & pemanggil lain tidak berubah.
 */

// ==============================================================
// CAMERA QR SCANNER & AUDIO FEEDBACK
// ==============================================================
let html5QrScannerInstance = null;
let currentScannerCallback = null;
let currentCameraFacing = "environment"; // "environment" (rear) or "user" (front)

function playScanBeep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    gain.gain.setValueAtTime(0.2, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.16);
  } catch(e) {}
}

async function startCameraScanner(onSuccessCallback, title = "Pindai Kode QR Kamera") {
  currentScannerCallback = onSuccessCallback;
  $("scanner-modal-title").innerText = title;
  $("scanner-camera-error").style.display = "none";
  $("scanner-success-pill").style.display = "none";
  $("scanner-manual-input").value = "";
  $("scanner-laser").style.display = "block";
  $("scanner-modal").classList.add("open");

  if (!window.Html5Qrcode) {
    $("scanner-camera-error").style.display = "block";
    $("scanner-camera-error").innerText = "Modul kamera sedang dimuat... Harap tunggu beberapa detik atau gunakan input manual.";
    return;
  }

  try {
    if (html5QrScannerInstance) {
      try { await html5QrScannerInstance.stop(); } catch(e) {}
      html5QrScannerInstance = null;
    }

    html5QrScannerInstance = new Html5Qrcode("qr-camera-stream");
    const config = {
      fps: 12,
      qrbox: (viewfinderWidth, viewfinderHeight) => {
        const edge = Math.min(viewfinderWidth, viewfinderHeight) * 0.75;
        return { width: Math.floor(edge), height: Math.floor(edge) };
      },
      aspectRatio: 1.0
    };

    await html5QrScannerInstance.start(
      { facingMode: currentCameraFacing },
      config,
      (decodedText) => {
        onQrDetected(decodedText);
      },
      (error) => {}
    );
  } catch (err) {
    console.warn("Kamera tidak dapat dimulai:", err);
    $("scanner-laser").style.display = "none";
    $("scanner-camera-error").style.display = "block";
    $("scanner-camera-error").innerHTML = `⚠️ Kamera tidak dapat diakses (${esc(err)}).<br>Pastikan izin kamera diizinkan, atau gunakan opsi <strong>Upload Foto QR</strong> / input manual di bawah.`;
  }
}

async function toggleCameraFacing() {
  currentCameraFacing = currentCameraFacing === "environment" ? "user" : "environment";
  $("btn-switch-camera").innerText = currentCameraFacing === "environment" ? "🔄 Kamera Belakang" : "🔄 Kamera Depan";
  if (html5QrScannerInstance && html5QrScannerInstance.isScanning) {
    await startCameraScanner(currentScannerCallback, $("scanner-modal-title").innerText);
  }
}

function onQrDetected(codeText) {
  playScanBeep();
  if (navigator.vibrate) navigator.vibrate(100);

  const clean = String(codeText || "").trim();
  $("scanner-detected-code").innerText = clean;
  $("scanner-success-pill").style.display = "block";
  $("scanner-laser").style.display = "none";

  showToast(`QR Berhasil Dipindai: ${clean}`, "📷");

  setTimeout(async () => {
    await stopCameraScanner();
    if (typeof currentScannerCallback === "function") {
      currentScannerCallback(clean);
    }
  }, 600);
}

async function stopCameraScanner() {
  if (html5QrScannerInstance) {
    try {
      if (html5QrScannerInstance.isScanning) {
        await html5QrScannerInstance.stop();
      }
      html5QrScannerInstance.clear();
    } catch(e) {}
    html5QrScannerInstance = null;
  }
  $("scanner-modal").classList.remove("open");
}

function closeScannerModal() {
  stopCameraScanner();
}

function handleQrFileUpload(input) {
  if (!input.files || !input.files.length) return;
  const file = input.files[0];
  if (!window.Html5Qrcode) return showToast("Modul scan belum siap", "⚠️");

  const tempScanner = new Html5Qrcode("qr-camera-stream");
  tempScanner.scanFile(file, true)
    .then(decodedText => {
      onQrDetected(decodedText);
    })
    .catch(err => {
      showToast("Tidak dapat mendeteksi kode QR pada foto ini.", "❌");
    });
}

function submitManualScannedCode() {
  const code = ($("scanner-manual-input").value || "").trim();
  if (!code) return showToast("Masukkan kode terlebih dahulu.", "⚠️");
  onQrDetected(code);
}

function openGlobalScanner() {
  startCameraScanner((code) => {
    openModal("Hasil Pemindaian QR", code, "Kode QR berhasil dibaca dari kamera");
  }, "Pemindai QR Kamera Bio-Chain");
}

// ==============================================================
// STANDALONE QR GENERATOR TOOL
// ==============================================================
let currentGeneratedQrText = "";

function openQrGeneratorModal() {
  $("generator-modal").classList.add("open");
  generateCustomQr();
}

function closeGeneratorModal() {
  $("generator-modal").classList.remove("open");
}

function generateCustomQr() {
  const val = ($("gen-input-text")?.value || "").trim() || "BIO-MASS-2026";
  currentGeneratedQrText = val;
  const wrap = $("gen-qr-canvas-wrap");
  if (!wrap) return;
  wrap.innerHTML = "";
  if (window.QRCode) {
    new QRCode(wrap, {
      text: val,
      width: 170,
      height: 170,
      colorDark: "#111111",
      colorLight: "#ffffff",
      correctLevel: QRCode.CorrectLevel.H
    });
  } else {
    wrap.innerHTML = `<div style="font-size:40px;">📱</div>`;
  }
  $("gen-qr-text-preview").innerText = val;
}

function setPresetQr(type) {
  const input = $("gen-input-text");
  if (type === "petani") {
    input.value = `BIO-FARMER-${Date.now().toString(36).toUpperCase()}-1500KG`;
  } else if (type === "batch") {
    input.value = `BIO-BATCH-${new Date().toISOString().slice(0, 10).replace(/-/g, "")}-PABRIK`;
  } else if (type === "qc") {
    input.value = `BIO-QC-LOT-${Math.floor(Math.random() * 9000 + 1000)}-M12`;
  }
  generateCustomQr();
}

function downloadGeneratedQr() {
  const wrap = $("gen-qr-canvas-wrap");
  const canvas = wrap ? wrap.querySelector("canvas") : null;
  const img = wrap ? wrap.querySelector("img") : null;
  const src = canvas ? canvas.toDataURL("image/png") : (img ? img.src : null);
  if (!src) return showToast("QR belum digenerate.", "⚠️");
  const a = document.createElement("a");
  a.href = src;
  a.download = `QR_${currentGeneratedQrText.replace(/[^a-zA-Z0-9_-]/g, "_")}.png`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  showToast("Gambar QR berhasil diunduh!", "⬇️");
}

function copyGeneratedQrText() {
  if (!currentGeneratedQrText) return;
  navigator.clipboard.writeText(currentGeneratedQrText)
    .then(() => showToast(`Teks disalin: ${currentGeneratedQrText}`, "📋"))
    .catch(() => showToast("Gagal menyalin teks", "❌"));
}
