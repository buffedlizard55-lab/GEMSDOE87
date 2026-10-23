(() => {
  const statusNode = document.querySelector("[data-submission-status]");
  const reasonNode = document.querySelector("[data-submission-reason]");
  const downloadNode = document.querySelector("[data-submission-download]");
  const feedNode = document.querySelector("[data-source-feed]");
  const feedCheckedNode = document.querySelector("[data-feed-checked]");

  const safeRelativeTif = (value) => {
    if (typeof value !== "string" || !/^[A-Za-z0-9._/-]+\.tif$/i.test(value)) return false;
    if (value.startsWith("/") || value.includes("..") || value.includes("//")) return false;
    return true;
  };

  const gatesPassed = (status) =>
    Array.isArray(status.gates) &&
    status.gates.length > 0 &&
    status.gates.every((gate) => gate && gate.status === "passed");

  async function loadSubmissionStatus() {
    if (!statusNode) return;
    try {
      const response = await fetch("data/submission-status.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`status HTTP ${response.status}`);
      const status = await response.json();
      const artifact = status.artifact;
      const download = status.download;
      const holdout = status.holdout_dti;
      const ci = holdout && holdout.ci_95;
      const holdoutReady = holdout &&
        holdout.evidence_class === "HOLDOUT-DTI" &&
        typeof holdout.evaluator_version === "string" && holdout.evaluator_version.length > 0 &&
        Number.isInteger(holdout.withheld_positive_count) && holdout.withheld_positive_count > 0 &&
        Number.isFinite(holdout.score) &&
        Array.isArray(ci) && ci.length === 2 && ci.every(Number.isFinite) &&
        holdout.beats_current_best === true;
      const novelty = status.novelty;
      const noveltyReady = novelty &&
        novelty.status === "passed" &&
        Number.isFinite(novelty.rank_correlation_max) && novelty.rank_correlation_max <= 0.90 &&
        Number.isFinite(novelty.fraction_within_3px_max) && novelty.fraction_within_3px_max <= 0.70 &&
        Number.isInteger(novelty.registry_rasters_checked) && novelty.registry_rasters_checked > 0;
      const validation = status.validation;
      const validationReady = validation &&
        validation.status === "passed" &&
        validation.no_nan_inside_footprint === true &&
        validation.finite_values_in_0_1 === true &&
        validation.crs_shape_transform_match === true &&
        /^[a-f0-9]{64}$/i.test(validation.receipt_sha256 || "");
      const ready = status.submission_ready === true &&
        status.status === "ready" &&
        gatesPassed(status) &&
        holdoutReady && noveltyReady && validationReady &&
        artifact && safeRelativeTif(artifact.filename) &&
        /^[a-f0-9]{64}$/i.test(artifact.sha256 || "") &&
        artifact.sha256.toLowerCase() === validation.receipt_sha256.toLowerCase() &&
        safeRelativeTif(download && download.path) &&
        download.path === `downloads/${artifact.filename}` &&
        typeof status.submission_name === "string" && status.submission_name.trim().length > 0 &&
        typeof status.submission_note === "string" && status.submission_note.trim().length > 0 && status.submission_note.length <= 140;

      statusNode.textContent = ready ? "READY — VALIDATED FILE AVAILABLE" : "NOT READY TO SUBMIT";
      const statusCard = statusNode.closest(".status-card");
      if (statusCard) {
        statusCard.classList.toggle("is-ready", ready);
        statusCard.classList.toggle("is-blocked", !ready);
      }
      if (reasonNode) {
        reasonNode.textContent = ready
          ? `Unique name: ${status.submission_name} · note: ${status.submission_note}`
          : (status.reason || "No validation receipt is available. Do not upload a placeholder.");
      }
      if (downloadNode) {
        downloadNode.classList.toggle("hidden", !ready);
        if (ready) {
          downloadNode.href = download.path;
          downloadNode.download = artifact.filename || "gemsdoe-submission.tif";
          downloadNode.textContent = `Download ${artifact.filename || "validated submission.tif"}`;
        } else {
          downloadNode.removeAttribute("href");
          downloadNode.removeAttribute("download");
        }
      }
    } catch (error) {
      statusNode.textContent = "NOT READY TO SUBMIT";
      const statusCard = statusNode.closest(".status-card");
      if (statusCard) {
        statusCard.classList.add("is-blocked");
        statusCard.classList.remove("is-ready");
      }
      if (reasonNode) reasonNode.textContent = "Submission status could not be verified. No file is offered.";
      if (downloadNode) {
        downloadNode.classList.add("hidden");
        downloadNode.removeAttribute("href");
      }
      console.error("Could not load submission status", error);
    }
  }

  async function loadFeed() {
    if (!feedNode) return;
    try {
      const response = await fetch("data/feed.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`feed HTTP ${response.status}`);
      const feed = await response.json();
      if (feedCheckedNode) feedCheckedNode.textContent = feed.checked_at || "Timestamp not available";
      const entries = Array.isArray(feed.entries) ? feed.entries : [];
      feedNode.replaceChildren();
      for (const entry of entries) {
        if (!entry || typeof entry.label !== "string" || typeof entry.url !== "string") continue;
        let parsed;
        try { parsed = new URL(entry.url); } catch { continue; }
        if (parsed.protocol !== "https:") continue;
        const item = document.createElement("li");
        item.className = "feed-item";
        const link = document.createElement("a");
        link.href = parsed.href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = entry.label;
        const note = document.createElement("p");
        note.textContent = entry.note || "Open the source to review the latest information.";
        const state = document.createElement("span");
        state.className = "feed-state";
        state.textContent = String(entry.status || "not checked").replaceAll("_", " ");
        item.append(link, note, state);
        feedNode.append(item);
      }
    } catch (error) {
      feedNode.innerHTML = "<li class=\"feed-item\"><p>Source feed unavailable; use the official source links below.</p></li>";
      console.error("Could not load source feed", error);
    }
  }

  for (const btn of document.querySelectorAll("[data-copy-text]")) {
    btn.addEventListener("click", async () => {
      const value = btn.getAttribute("data-copy-text") || "";
      try {
        await navigator.clipboard.writeText(value);
        const prev = btn.textContent;
        btn.textContent = "Copied!";
        setTimeout(() => { btn.textContent = prev; }, 1600);
      } catch {
        btn.textContent = "Select code";
      }
    });
  }

  loadSubmissionStatus();
  loadFeed();
})();
