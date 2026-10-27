/**
 * Bio-Chain Voice-to-Text (id-ID) & Rural Ergonomics Assistant
 * 
 * Features:
 * 1. Single-Instance Speech Recognition (Anti-collision with auto-abort)
 * 2. Indonesian Spoken Number & Text Normalizer (thousands dots, commas, words to digits, unit stripping)
 * 3. Fuzzy matching for dropdown <select> elements
 * 4. High-visibility Gaptek feedback: Listening pulse, green success badge, friendly Indonesian error messages
 * 5. Quick numerical steppers (- / +) for mobile thumb ergonomics
 */
(() => {
  "use strict";

  // Check Web Speech API availability
  const SpeechRecognition = typeof window !== "undefined"
    ? (window.SpeechRecognition || window.webkitSpeechRecognition || null)
    : null;

  // Single active recognition tracker to avoid InvalidStateError
  let activeRecognition = null;
  let activeButton = null;
  let activeTarget = null;
  let activeBadge = null;

  // ------------------------------------------------------------------
  // 1. Indonesian Number Parser & Normalizer
  // ------------------------------------------------------------------
  const INDO_DIGITS = {
    'nol': 0, 'kosong': 0,
    'satu': 1, 'se': 1,
    'dua': 2,
    'tiga': 3,
    'empat': 4,
    'lima': 5,
    'enam': 6,
    'tujuh': 7,
    'delapan': 8,
    'sembilan': 9
  };

  function parseIndonesianNumberGroup(phrase) {
    const tokens = phrase.trim().split(/\s+/).filter(Boolean);
    if (!tokens.length) return 0;

    let val = 0;
    for (let i = 0; i < tokens.length; i++) {
      const t = tokens[i];
      if (t === 'seratus') {
        val += 100;
      } else if (t === 'ratus') {
        const prevDigit = INDO_DIGITS[tokens[i - 1]] || 1;
        val += (prevDigit * 100) - prevDigit;
      } else if (t === 'sepuluh') {
        val += 10;
      } else if (t === 'sebelas') {
        val += 11;
      } else if (t === 'belas') {
        val += 10;
      } else if (t === 'puluh') {
        const prevDigit = INDO_DIGITS[tokens[i - 1]] || 1;
        val += (prevDigit * 10) - prevDigit;
      } else if (t === 'setengah') {
        val += 0.5;
      } else if (INDO_DIGITS[t] !== undefined) {
        val += INDO_DIGITS[t];
      } else if (!isNaN(Number(t))) {
        val += Number(t);
      }
    }
    return val;
  }

  function parseIndonesianWords(phrase) {
    const s = phrase.trim().toLowerCase();
    if (!s) return NaN;

    if (s === 'setengah') return 0.5;

    let str = s
      .replace(/\bsebelas\b/g, 'sebelas')
      .replace(/\bsepuluh\b/g, 'sepuluh')
      .replace(/\bseratus\b/g, 'seratus')
      .replace(/\bseribu\b/g, '1 ribu')
      .replace(/\bsejuta\b/g, '1 juta');

    // Check if purely digit-by-digit spoken: e.g. "dua lima nol nol" -> 2500, "satu satu" -> 11
    const rawTokens = str.split(/\s+/).filter(Boolean);
    const isPureDigits = rawTokens.every(t => INDO_DIGITS[t] !== undefined || !isNaN(Number(t)));
    const hasScaleWords = rawTokens.some(t => ['belas', 'puluh', 'ratus', 'ribu', 'juta'].includes(t));
    if (isPureDigits && !hasScaleWords && rawTokens.length > 1) {
      let digitStr = '';
      for (const t of rawTokens) {
        if (INDO_DIGITS[t] !== undefined) digitStr += INDO_DIGITS[t];
        else if (!isNaN(Number(t))) digitStr += t;
      }
      const res = Number(digitStr);
      if (!isNaN(res)) return res;
    }

    let total = 0;

    // Millions (juta)
    if (str.includes('juta')) {
      const parts = str.split('juta');
      const milPart = parts[0].trim();
      const milVal = milPart ? parseIndonesianNumberGroup(milPart) : 1;
      total += milVal * 1000000;
      str = parts.slice(1).join(' ').trim();
    }

    // Thousands (ribu)
    if (str.includes('ribu')) {
      const parts = str.split('ribu');
      const ribPart = parts[0].trim();
      const ribVal = ribPart ? parseIndonesianNumberGroup(ribPart) : 1;
      total += ribVal * 1000;
      str = parts.slice(1).join(' ').trim();
    }

    // Remainder (< 1000)
    if (str) {
      total += parseIndonesianNumberGroup(str);
    }

    return total;
  }

  function detectFieldType(el, requestedType = null) {
    if (requestedType && requestedType !== "auto" && requestedType !== "number" && requestedType !== "text") {
      return requestedType;
    }
    if (!el) return requestedType || "text";

    if (el.tagName === "SELECT") return "select";
    if (el.tagName === "TEXTAREA") return "text";

    const voiceType = el.getAttribute ? el.getAttribute("data-voice-type") : el["data-voice-type"];
    if (voiceType) return voiceType.toLowerCase();

    const id = (el.id || el.name || "").toLowerCase();
    const textKeywords = ["loc", "lokasi", "alamat", "nama", "name", "note", "catatan", "alasan", "reason", "provinsi", "kabupaten", "kecamatan", "desa"];
    if (textKeywords.some(k => id.includes(k))) return "text";

    const type = (el.type || "").toLowerCase();
    if (type === "number" || type === "range" || type === "tel") return "number";

    const mode = (el.getAttribute ? el.getAttribute("inputmode") : el.inputmode || "").toLowerCase();
    if (mode === "numeric" || mode === "decimal") return "number";

    const numKeywords = ["qty", "weight", "berat", "jumlah", "moist", "kadar", "suhu", "temp", "price", "harga", "ash", "abu", "vm", "fc", "contam", "ha", "luas", "kg", "ton", "nominal", "saldo", "req"];
    if (numKeywords.some(k => id.includes(k))) return "number";

    return requestedType === "number" ? "number" : "text";
  }

  function processIndonesianVoiceInput(rawTranscript, inputType = 'text', optionsList = []) {
    if (!rawTranscript || typeof rawTranscript !== 'string') return '';
    const trimmed = rawTranscript.trim();
    if (!trimmed) return '';

    // 1. TEXT INPUT TYPE: Clean words and capitalize first letter
    if (inputType === 'text') {
      const cleaned = trimmed.replace(/\s+/g, ' ');
      return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
    }

    // 2. NUMBER INPUT TYPE: STRICTLY return pure Number, NEVER text words!
    if (inputType === 'number') {
      let s = trimmed.toLowerCase();

      // a. Strip units and spoken suffixes
      const units = [
        'kilogram', 'kilo gram', 'kilo', 'kg',
        'ton', 'karung', 'sak',
        'rupiah', 'rp',
        'kilometer', 'kilo meter', 'km',
        'persen', '%',
        'derajat', 'celcius', 'celsius',
        'hektar', 'ha', 'meter', 'm'
      ];
      for (const u of units) {
        s = s.replace(new RegExp(`\\b${u}\\b`, 'gi'), ' ');
      }

      // b. Strip spoken filler words
      const fillers = ['kurang lebih', 'kira kira', 'kira-kira', 'sekitar', 'sebanyak', 'sebesar', 'tolong isi', 'angka', 'nilai'];
      for (const f of fillers) {
        s = s.replace(new RegExp(`\\b${f}\\b`, 'gi'), ' ');
      }

      s = s.trim();

      // c. Handle Indonesian thousands with dots: e.g. "15.000", "1.500", "1.250.000"
      s = s.replace(/(\d+)\.(\d{3})(?=\D|$)/g, '$1$2');
      s = s.replace(/(\d+)\.(\d{3})(?=\D|$)/g, '$1$2');

      // d. Handle "koma" or comma as decimal point
      if (s.includes('koma')) {
        const parts = s.split('koma');
        const wholePart = parts[0].trim();
        const decPart = parts.slice(1).join(' ').trim();

        const wholeNum = isNaN(Number(wholePart)) ? parseIndonesianWords(wholePart) : Number(wholePart);
        let decDigits = '';
        const decTokens = decPart.split(/\s+/).filter(Boolean);
        const singleDigits = {
          'nol': '0', 'kosong': '0', 'satu': '1', 'dua': '2', 'tiga': '3',
          'empat': '4', 'lima': '5', 'enam': '6', 'tujuh': '7', 'delapan': '8', 'sembilan': '9'
        };
        for (const tok of decTokens) {
          if (!isNaN(Number(tok))) decDigits += tok;
          else if (singleDigits[tok] !== undefined) decDigits += singleDigits[tok];
          else {
            const n = parseIndonesianWords(tok);
            if (!isNaN(n)) decDigits += String(n);
          }
        }
        return decDigits ? Number(`${wholeNum}.${decDigits}`) : wholeNum;
      }

      // Comma as decimal: "1,5" -> "1.5"
      s = s.replace(/(\d+),(\d+)/g, '$1.$2');

      // If pure number already
      if (!isNaN(Number(s))) {
        return Number(s);
      }

      // e. If string has an embedded multi-digit number (e.g. "Satu satu 2500" -> 2500, "stok 1500" -> 1500)
      const matchMulti = s.match(/\b\d{2,}(?:\.\d+)?\b/);
      if (matchMulti) {
        return Number(matchMulti[0]);
      }

      // f. Try parsing full Indonesian words phrase (e.g. "dua ribu lima ratus", "setengah", "seratus", etc.)
      const parsed = parseIndonesianWords(s);
      if (!isNaN(parsed) && parsed !== 0) return parsed;
      if (parsed === 0 && (s.includes('nol') || s.includes('kosong') || s === '0')) return 0;
      if (s === 'setengah' || s.includes('setengah')) return 0.5;

      // g. Digit-by-digit spoken: "satu satu" -> 11, "dua lima nol nol" -> 2500
      const digitsMap = {
        'nol': '0', 'kosong': '0', 'satu': '1', 'se': '1', 'dua': '2',
        'tiga': '3', 'empat': '4', 'lima': '5', 'enam': '6', 'tujuh': '7',
        'delapan': '8', 'sembilan': '9'
      };
      const tokens = s.split(/\s+/).filter(Boolean);
      let digitStr = '';
      for (const t of tokens) {
        if (digitsMap[t] !== undefined) digitStr += digitsMap[t];
        else if (!isNaN(Number(t))) digitStr += t;
      }
      if (digitStr) return Number(digitStr);

      // Fallback: extract first numeric match
      const match = s.match(/[-+]?\d*\.?\d+/);
      if (match) return Number(match[0]);

      return NaN;
    }

    // 3. SELECT DROPDOWN TYPE: Fuzzy match
    if (inputType === 'select') {
      const s = trimmed.toLowerCase();
      // 1. Exact value match or option text match
      for (const opt of optionsList) {
        const text = (opt.text || opt.label || '').toLowerCase();
        const val = (opt.value || '').toLowerCase();
        if (val && s === val) return opt.value;
        if (text && s === text) return opt.value;
      }
      // 2. Word boundary match
      for (const opt of optionsList) {
        const text = (opt.text || opt.label || '').toLowerCase();
        const val = (opt.value || '').toLowerCase();
        if (val && new RegExp(`\\b${val}\\b`, 'i').test(s)) return opt.value;
        if (s.includes(text) || text.includes(s)) return opt.value;
      }
      // 3. Keyword token match
      const sWords = s.split(/\s+/).filter(w => w.length > 1);
      for (const opt of optionsList) {
        const text = (opt.text || opt.label || '').toLowerCase();
        for (const w of sWords) {
          if (new RegExp(`\\b${w}\\b`, 'i').test(text)) return opt.value;
        }
      }
      return optionsList[0] ? optionsList[0].value : '';
    }

    return trimmed;
  }

  // ------------------------------------------------------------------
  // 2. Speech Recognition Controller (Anti-Collision Single Instance)
  // ------------------------------------------------------------------
  function stopActiveRecognition() {
    if (activeRecognition) {
      try {
        activeRecognition.abort();
      } catch (err) {
        console.warn("Speech abort:", err);
      }
      activeRecognition = null;
    }
    if (activeButton) {
      resetButtonUi(activeButton);
      activeButton = null;
    }
    if (activeTarget) {
      activeTarget.classList.remove("voice-active-target");
      activeTarget = null;
    }
  }

  function resetButtonUi(btn) {
    if (!btn) return;
    btn.classList.remove("is-listening");
    const origHtml = btn.getAttribute("data-idle-html");
    if (origHtml) {
      btn.innerHTML = origHtml;
    } else {
      btn.innerHTML = `<span class="voice-mic-icon">🎤</span> <span class="voice-mic-lbl">Bicara</span>`;
    }
    btn.setAttribute("aria-pressed", "false");
  }

  function showSuccessBadge(targetEl, text) {
    // Remove any previous active badge
    if (activeBadge && activeBadge.parentNode) {
      activeBadge.parentNode.removeChild(activeBadge);
      activeBadge = null;
    }

    const badge = document.createElement("div");
    badge.className = "voice-feedback-badge";
    badge.innerHTML = `✅ Terisi: <b>${escapeHtml(String(text))}</b>`;
    badge.setAttribute("role", "status");

    // Position near the input field
    const parent = targetEl.parentNode;
    if (parent) {
      if (parent.classList.contains("input-wrap") || parent.classList.contains("field-voice-group")) {
        parent.parentNode.insertBefore(badge, parent.nextSibling);
      } else {
        parent.insertBefore(badge, targetEl.nextSibling);
      }
    } else {
      document.body.appendChild(badge);
    }
    activeBadge = badge;

    // Flash green ring on target element
    targetEl.classList.add("voice-success-flash");
    setTimeout(() => {
      targetEl.classList.remove("voice-success-flash");
    }, 2500);

    // Auto remove badge after 2.5 seconds
    setTimeout(() => {
      if (badge && badge.parentNode) {
        badge.classList.add("fade-out");
        setTimeout(() => {
          if (badge.parentNode) badge.parentNode.removeChild(badge);
          if (activeBadge === badge) activeBadge = null;
        }, 300);
      }
    }, 2500);
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function toggleVoiceInput(targetId, inputType = null) {
    const targetEl = document.getElementById(targetId);
    if (!targetEl) {
      console.warn("Target input not found:", targetId);
      return;
    }

    // Auto-detect whether this field is a number, text, or select
    const resolvedType = detectFieldType(targetEl, inputType);

    // Find trigger button
    const btn = document.querySelector(`[data-voice-for="${targetId}"]`)
      || document.querySelector(`button[data-onclick*="'${targetId}'"]`)
      || (event && event.currentTarget);

    // If clicking on already listening button -> stop it
    if (activeButton === btn && activeRecognition) {
      stopActiveRecognition();
      return;
    }

    // Stop any ongoing speech recognition on other fields
    stopActiveRecognition();

    if (!SpeechRecognition) {
      if (typeof window.showToast === "function") {
        window.showToast("Browser Anda belum mendukung Web Speech API bawaan. Gunakan Google Chrome atau Edge untuk fitur suara.", "⚠️");
      } else {
        alert("Browser Anda belum mendukung Web Speech API bawaan. Gunakan Google Chrome atau Edge.");
      }
      return;
    }

    // Save button idle state
    if (btn) {
      if (!btn.getAttribute("data-idle-html")) {
        btn.setAttribute("data-idle-html", btn.innerHTML);
      }
      btn.classList.add("is-listening");
      btn.innerHTML = `<span class="voice-anim-dot">🔴</span> <span class="voice-mic-lbl">Bicara Sekarang...</span>`;
      btn.setAttribute("aria-pressed", "true");
      activeButton = btn;
    }

    targetEl.classList.add("voice-active-target");
    activeTarget = targetEl;

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = "id-ID";
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        // Listening started
      };

      recognition.onresult = (e) => {
        if (!e.results || !e.results[0] || !e.results[0][0]) return;
        const transcript = e.results[0][0].transcript;
        console.log(`[Voice id-ID] Raw transcript: "${transcript}" on field: "${targetId}" as [${resolvedType}]`);

        let optionsList = [];
        let finalType = resolvedType;
        if (targetEl.tagName === "SELECT") {
          optionsList = Array.from(targetEl.options).map(o => ({ value: o.value, text: o.text }));
          finalType = "select";
        }

        const processed = processIndonesianVoiceInput(transcript, finalType, optionsList);
        console.log(`[Voice id-ID] Processed result:`, processed);

        if (processed !== "" && processed !== null && !Number.isNaN(processed)) {
          if (finalType === "number") {
            // STRICT GUARANTEE: numeric fields ALWAYS receive pure number
            const numVal = Number(processed);
            targetEl.value = isNaN(numVal) ? processed : numVal;
            targetEl.setAttribute("inputmode", "numeric");
          } else {
            // Text or select field
            targetEl.value = processed;
          }

          // Dispatch input and change events so formulas and state setters update immediately
          targetEl.dispatchEvent(new Event("input", { bubbles: true }));
          targetEl.dispatchEvent(new Event("change", { bubbles: true }));

          // Show prominent gaptek visual confirmation
          showSuccessBadge(targetEl, processed);
          if (typeof window.showToast === "function") {
            window.showToast(`✅ Suara terdeteksi: "${processed}"`, "🎤");
          }
        } else {
          if (typeof window.showToast === "function") {
            window.showToast(`Suara "${transcript}" belum dikenali sebagai ${finalType === 'number' ? 'angka' : 'input'} valid. Coba ucapkan lagi.`, "⚠️");
          }
        }
      };

      recognition.onerror = (e) => {
        console.warn("Speech error:", e.error);
        let msg = "Suara belum terdengar, silakan tekan mikrofon dan bicara lagi.";
        if (e.error === "not-allowed" || e.error === "permission-denied") {
          msg = "Akses mikrofon ditolak. Izinkan izin mikrofon pada browser Anda.";
        } else if (e.error === "no-speech") {
          msg = "Suara belum terdengar, silakan tekan mikrofon dan bicara lagi.";
        } else if (e.error === "network") {
          msg = "Koneksi jaringan terputus untuk layanan suara.";
        }
        if (typeof window.showToast === "function") {
          window.showToast(msg, "⚠️");
        }
        stopActiveRecognition();
      };

      recognition.onend = () => {
        stopActiveRecognition();
      };

      activeRecognition = recognition;
      recognition.start();
    } catch (err) {
      console.error("SpeechRecognition start exception:", err);
      stopActiveRecognition();
      if (typeof window.showToast === "function") {
        window.showToast("Gagal memulai mikrofon: " + err.message, "❌");
      }
    }
  }

  // ------------------------------------------------------------------
  // 3. Quick Numerical Stepper Companion Helper
  // ------------------------------------------------------------------
  function stepNumberInput(targetId, delta) {
    const el = document.getElementById(targetId);
    if (!el) return;

    const cur = Number(el.value) || 0;
    const step = Number(delta);
    let next = cur + step;

    // Minimum check
    const min = el.min !== "" ? Number(el.min) : 0;
    if (next < min) next = min;

    // Maximum check
    const max = el.max !== "" ? Number(el.max) : Infinity;
    if (next > max) next = max;

    // Handle decimal precision
    if (String(delta).includes(".") || (el.step && String(el.step).includes("."))) {
      next = Math.round(next * 10) / 10;
    } else {
      next = Math.round(next);
    }

    el.value = next;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));

    // Visual micro-feedback
    el.classList.add("stepper-bump");
    setTimeout(() => el.classList.remove("stepper-bump"), 250);
  }

  // ------------------------------------------------------------------
  // 4. Live Keyboard / Gboard Voice Typing Auto-Normalizer
  //    Handles cases where mobile users tap the field and speak into
  //    Android Gboard / Google Voice Typing (which inputs words directly).
  //    Automatically converts words to pure numbers if the field requires numbers!
  // ------------------------------------------------------------------
  function initKeyboardVoiceNormalizer() {
    function tryNormalizeField(el) {
      if (!el || el.tagName !== "INPUT") return;
      const fType = detectFieldType(el);
      if (fType !== "number") return;

      const raw = String(el.value || "").trim();
      // If the field has letters (e.g. Gboard voice typing entered "Satu satu 2500" or "dua ribu lima ratus")
      if (raw && /[a-zA-Z]/.test(raw)) {
        const cleaned = processIndonesianVoiceInput(raw, "number");
        if (!isNaN(cleaned) && cleaned !== null && cleaned !== "") {
          el.value = String(cleaned);
          el.dispatchEvent(new Event("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));
          showSuccessBadge(el, cleaned);
        }
      }
    }

    // On blur or change (when user closes keyboard or moves to next field)
    document.addEventListener("change", (e) => tryNormalizeField(e.target), true);
    document.addEventListener("blur", (e) => tryNormalizeField(e.target), true);

    // Debounced input listener (while typing or dictating via Gboard)
    let debounceTimer = null;
    document.addEventListener("input", (e) => {
      const el = e.target;
      if (!el || el.tagName !== "INPUT") return;
      if (detectFieldType(el) !== "number") return;
      if (el.value && /[a-zA-Z]/.test(el.value)) {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => tryNormalizeField(el), 600);
      }
    }, true);
  }

  // Initialize normalizer on load
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", initKeyboardVoiceNormalizer);
    } else {
      initKeyboardVoiceNormalizer();
    }
  }

  // ------------------------------------------------------------------
  // 5. Global Registration & Auto-Augmentation
  // ------------------------------------------------------------------
  window.detectFieldType = detectFieldType;
  window.processIndonesianVoiceInput = processIndonesianVoiceInput;
  window.toggleVoiceInput = toggleVoiceInput;
  window.stepNumberInput = stepNumberInput;

  // Delegate click handlers for steppers with data-step
  document.addEventListener("click", (e) => {
    const stepBtn = e.target.closest && e.target.closest(".btn-step-quick");
    if (stepBtn) {
      const targetId = stepBtn.dataset.target;
      const stepVal = stepBtn.dataset.step;
      if (targetId && stepVal) {
        stepNumberInput(targetId, stepVal);
      }
    }
  });

  console.log("✅ Bio-Chain Voice-to-Text & Ergonomics Module Loaded");
})();
