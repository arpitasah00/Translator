import { useState } from "react";
import { motion } from "framer-motion";
import { Upload, Image as ImageIcon, Loader2, Copy } from "lucide-react";

// ✅ USE OCR_SAFE_LANGUAGES FOR IMAGE TRANSLATION
import { OCR_SAFE_LANGUAGES } from "@/lib/languages";

export default function ImageTranslator({ onRequireAuth }) {
  const [file, setFile] = useState(null);
  const [targetLanguage, setTargetLanguage] = useState("en"); // default safe language
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  // Analyze state and handler for image emotion detection
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState(null);

  const formatPercent = (value) => {
    const num = Number(value);
    if (Number.isNaN(num)) return "0%";
    return `${Math.round(num * 100)}%`;
  };

  const formatEmotionLabel = (value) => {
    if (!value) return "Unknown";
    return value.charAt(0).toUpperCase() + value.slice(1);
  };

  const handleUpload = async () => {
    if (!file) return;

    // 🔐 Login check
    const token = localStorage.getItem("authToken");
    const isLoggedIn =
      !!token && localStorage.getItem("isLoggedIn") === "true";

    if (!isLoggedIn) {
      onRequireAuth();
      return;
    }

    setLoading(true);

    const formData = new FormData();
    formData.append("image", file);
    formData.append("target_language", targetLanguage);
    formData.append("source_language", "auto");

    try {
      const res = await fetch("http://localhost:5000/translate-image", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });
      if (res.status === 401) {
        localStorage.removeItem("authToken");
        localStorage.removeItem("isLoggedIn");
        onRequireAuth();
        return;
      }
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.error || "Failed to translate image");
      }
      setResult(data);
    } catch (err) {
      console.error(err);
      alert(err?.message || "Error translating image");
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async () => {
    if (!file) return;
    setAnalyzing(true);
    setAnalyzeResult(null);
    try {
      const token = localStorage.getItem("authToken");
      const formData = new FormData();
      formData.append("image", file);
      const res = await fetch("http://localhost:5000/analyze-image-emotion", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });
      const data = await res.json();
      setAnalyzeResult(data);
    } catch (err) {
      alert("Image emotion analysis failed!");
      setAnalyzeResult({ error: err?.message || "Failed to analyze" });
    } finally {
      setAnalyzing(false);
    }
  };
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      className="grid md:grid-cols-2 gap-6 mt-12"
    >

      {/* LEFT SIDE */}
      <div className="bg-card p-6 rounded-2xl shadow-lg border space-y-4">

        <h2 className="text-xl font-semibold flex items-center gap-2">
          <ImageIcon className="w-5 h-5 text-primary" />
          Image Translator
        </h2>

        {/* Upload */}
        <label className="flex items-center justify-center border-2 border-dashed rounded-xl p-6 cursor-pointer hover:bg-muted transition">
          <Upload className="w-5 h-5 mr-2" />
          {file ? file.name : "Click to upload image"}
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => setFile(e.target.files[0])}
          />
        </label>

        {/* ✅ LANGUAGE DROPDOWN (OCR SAFE LANGUAGES) */}
        <select
          value={targetLanguage}
          onChange={(e) => setTargetLanguage(e.target.value)}
          className="w-full border rounded-lg p-2 bg-background"
        >
          {OCR_SAFE_LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.flag} {lang.name}
            </option>
          ))}
        </select>

        {/* ✅ BUTTONS (SMART ACTIVE LOGIC) */}
        <div className="flex gap-2">
          <button
            onClick={handleUpload}
            disabled={loading || !file}
            className={`w-full flex items-center justify-center gap-2 py-2 rounded-xl transition
              ${
                file
                  ? "bg-primary text-white hover:opacity-90"
                  : "bg-muted text-muted-foreground cursor-not-allowed"
              }
            `}
            style={{ flex: 1 }}
          >
            {loading ? (
              <>
                <Loader2 className="animate-spin w-4 h-4" />
                Translating...
              </>
            ) : file ? (
              "Translate Image"
            ) : (
              "Upload Image First"
            )}
          </button>
          <button
            onClick={handleAnalyze}
            disabled={analyzing || !file}
            className={`w-full flex items-center justify-center gap-2 py-2 rounded-xl transition
              ${
                file
                  ? "bg-primary text-white hover:opacity-90"
                  : "bg-muted text-muted-foreground cursor-not-allowed"
              }
            `}
            style={{ flex: 1 }}
          >
            {analyzing ? (
              <>
                <Loader2 className="animate-spin w-4 h-4" />
                Analyzing...
              </>
            ) : file ? (
              "Analyze"
            ) : (
              "Upload Image First"
            )}
          </button>
        </div>


        {/* Preview */}
        {file && (
          <img
            src={URL.createObjectURL(file)}
            alt="preview"
            className="rounded-xl mt-2"
          />
        )}
    </div>

      {/* RIGHT SIDE */}
      <div className="bg-card p-6 rounded-2xl shadow-lg border space-y-4">

        <h2 className="text-xl font-semibold">Result</h2>

        {/* Original */}
        <div>
          <div className="flex justify-between items-center mb-1">
            <p className="text-sm text-muted-foreground">Original Text</p>
            {result?.original && (
              <Copy
                className="w-4 h-4 cursor-pointer"
                onClick={() => copyText(result.original)}
              />
            )}
          </div>
          <div className="bg-muted p-3 rounded min-h-[80px]">
            {result?.original || "No text detected yet"}
          </div>
        </div>

        {/* Translated */}
        <div>
          <div className="flex justify-between items-center mb-1">
            <p className="text-sm text-muted-foreground">
              Translated Text
            </p>
            {result?.translated && (
              <Copy
                className="w-4 h-4 cursor-pointer"
                onClick={() => copyText(result.translated)}
              />
            )}
          </div>
          <div className="bg-muted p-3 rounded min-h-[80px]">
            {result?.translated || "Translation will appear here"}
          </div>
        </div>

        {analyzeResult && (
          <div className="rounded-lg border border-border/50 bg-muted p-3">
            <div className="flex items-center justify-between gap-3">
              <h4 className="text-sm font-semibold">Emotion Analysis</h4>
              {analyzeResult.provider && !analyzeResult.error && (
                <span className="text-[11px] text-muted-foreground">
                  {analyzeResult.provider === "gemini-image-fallback"
                    ? "Gemini image fallback"
                    : "Eden AI"}
                </span>
              )}
            </div>
            {analyzeResult.error ? (
              <p className="mt-2 text-xs text-destructive">{analyzeResult.error}</p>
            ) : (
              <div className="mt-3 space-y-3">
                <div className="rounded-md bg-background/70 p-3">
                  <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
                    Primary Emotion
                  </div>
                  <div className="mt-1 flex items-end justify-between gap-3">
                    <span className="text-base font-semibold text-foreground">
                      {formatEmotionLabel(analyzeResult.label)}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {formatPercent(analyzeResult.score)}
                    </span>
                  </div>
                </div>
                {Array.isArray(analyzeResult.emotions) &&
                  analyzeResult.emotions.length > 0 && (
                    <div className="space-y-2">
                      {analyzeResult.emotions.map((emotion) => (
                        <div
                          key={`${emotion.label}-${emotion.score}`}
                          className="space-y-1"
                        >
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-foreground">
                              {formatEmotionLabel(emotion.label)}
                            </span>
                            <span className="text-muted-foreground">
                              {formatPercent(emotion.score)}
                            </span>
                          </div>
                          <div className="h-2 overflow-hidden rounded-full bg-background">
                            <div
                              className="h-full rounded-full bg-primary transition-all"
                              style={{
                                width: `${Math.max(
                                  6,
                                  Math.round(Number(emotion.score || 0) * 100),
                                )}%`,
                              }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                {analyzeResult.fallback_reason && (
                  <p className="text-[11px] text-muted-foreground">
                    Eden AI timed out, so a fallback model was used.
                  </p>
                )}
              </div>
            )}
          </div>
        )}

      </div>

    </motion.div>
  );
}
