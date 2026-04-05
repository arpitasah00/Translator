import { ArrowRightLeft, Copy, Volume2, Loader2 } from "lucide-react";
import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import LanguageSelector from "./LanguageSelector";
import { toast } from "sonner";
import { api } from "@/lib/api";

// ✅ CENTRAL LANGUAGES IMPORT
import {
  LANGUAGES,
  TARGET_LANGUAGES,
  getLanguageByCode,
  detectSupportedLanguage,
} from "@/lib/languages";

const TranslatorCard = ({ onRequireAuth }) => {
  const [sourceLang, setSourceLang] = useState("auto");
  const [targetLang, setTargetLang] = useState("es");
  const [sourceText, setSourceText] = useState("");
  const [translatedText, setTranslatedText] = useState("");
  const [isTranslating, setIsTranslating] = useState(false);
  const [variants, setVariants] = useState(null);
  const [activeStyle, setActiveStyle] = useState("neutral");
  // Sentiment/Emotion Analysis State
  const [isAnalyzing, setIsAnalyzing] = useState(false);
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

  const detectedLanguage =
    sourceLang === "auto" ? detectSupportedLanguage(sourceText) : null;

  const displayedSourceLanguage =
    sourceLang === "auto" && detectedLanguage ? detectedLanguage : sourceLang;

  // Sentiment/Emotion Analysis Handler
  const handleAnalyze = useCallback(async () => {
    if (!sourceText.trim()) return;

    const isLoggedIn =
      typeof window !== "undefined" &&
      localStorage.getItem("isLoggedIn") === "true";

    if (!isLoggedIn) {
      if (onRequireAuth) {
        onRequireAuth();
      }
      toast.message("Please sign in to analyze.");
      return;
    }

    setIsAnalyzing(true);
    setAnalyzeResult(null);
    try {
      const token = localStorage.getItem("authToken");
      const res = await api.post(
        "/analyze-sentiment",
        {
          text: sourceText,
          language: sourceLang,
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      setAnalyzeResult(res.data);
    } catch (err) {
      toast.error("Sentiment analysis failed!");
      const payload = err?.response?.data;
      setAnalyzeResult(
        payload || {
          error: err?.message || "Failed to analyze",
        },
      );
    } finally {
      setIsAnalyzing(false);
    }
  }, [sourceText, sourceLang, onRequireAuth]);

  const handleTranslate = useCallback(async () => {
    if (!sourceText.trim()) return;

    const isLoggedIn =
      typeof window !== "undefined" &&
      localStorage.getItem("isLoggedIn") === "true";

    if (!isLoggedIn) {
      if (onRequireAuth) {
        onRequireAuth();
      }
      toast.message("Please sign in to translate.");
      return;
    }

    setIsTranslating(true);
    setVariants(null);
    setActiveStyle("neutral");

    try {
      const resolvedSourceLanguage =
        sourceLang === "auto"
          ? getLanguageByCode(detectedLanguage)?.name || "Auto-detect"
          : getLanguageByCode(sourceLang)?.name || sourceLang;
      const resolvedTargetLanguage =
        getLanguageByCode(targetLang)?.name || targetLang;

      const res = await api.post("/translate/variants", {
        message: sourceText,
        source_language: resolvedSourceLanguage,
        target_language: resolvedTargetLanguage,
      });
      const data = res.data;
      const v = data.variants || null;
      setVariants(v);
      if (v && (v.neutral || v.formal || v.informal)) {
        const base = v.neutral || v.formal || v.informal;
        setTranslatedText(base);
        setActiveStyle(
          v.neutral ? "neutral" : v.formal ? "formal" : "informal",
        );
      } else {
        setTranslatedText(data.translated);
      }
    } catch (error) {
      console.error(error);
      toast.error("Translation failed!");
      setTranslatedText("");
      setVariants(null);
    } finally {
      setIsTranslating(false);
    }
  }, [sourceText, sourceLang, targetLang, detectedLanguage, onRequireAuth]);

  const handleSwap = () => {
    if (sourceLang === "auto") return;
    setSourceLang(targetLang);
    setTargetLang(sourceLang);
    setSourceText(translatedText);
    setTranslatedText(sourceText);
  };

  const handleCopy = () => {
    if (translatedText) {
      navigator.clipboard.writeText(translatedText);
      toast.success("Copied to clipboard");
    }
  };

  const handleSpeak = () => {
    if (!translatedText) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(translatedText);
    const langMap = {
      en: "en-US",
      es: "es-ES",
      fr: "fr-FR",
      de: "de-DE",
      ja: "ja-JP",
      zh: "zh-CN",
      ko: "ko-KR",
      ar: "ar-SA",
      hi: "hi-IN",
      ru: "ru-RU",
      pt: "pt-BR",
      it: "it-IT",
      tr: "tr-TR",
      nl: "nl-NL",
      sv: "sv-SE",
      or: "or-IN",
      bn: "bn-BD",
      sa: "sa-IN",
      te: "te-IN",
      ta: "ta-IN",
      kn: "kn-IN",
    };
    utterance.lang = langMap[targetLang] || "en-US";
    window.speechSynthesis.speak(utterance);
  };

  return (
    <motion.div
      initial={{ y: 30, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="mx-auto w-full max-w-4xl"
    >
      <div className="overflow-hidden rounded-2xl border border-border/60 bg-card shadow-lg">
        {/* Language bar */}
        <div className="border-b border-border/40 bg-muted/30 px-4 py-3 space-y-2 md:flex md:items-center md:gap-2 md:space-y-0">
          <LanguageSelector
            value={sourceLang}
            displayValue={displayedSourceLanguage}
            onChange={setSourceLang}
            showDetect
            languages={LANGUAGES}
          />
          <Button
            variant="ghost"
            size="icon"
            onClick={handleSwap}
            disabled={sourceLang === "auto"}
            className="h-8 w-8 shrink-0 rounded-full text-muted-foreground hover:bg-accent hover:text-primary mx-auto md:mx-0"
          >
            <ArrowRightLeft className="h-4 w-4" />
          </Button>
          <LanguageSelector
            value={targetLang}
            onChange={setTargetLang}
            languages={TARGET_LANGUAGES}
          />
        </div>

        {/* Translation areas */}
        <div className="grid md:grid-cols-2 md:divide-x md:divide-border/40">
          {/* Source */}
          <div className="relative p-4">
            <textarea
              value={sourceText}
              onChange={(e) => setSourceText(e.target.value)}
              placeholder="Type or paste text here..."
              className="min-h-[180px] w-full resize-none bg-transparent font-body text-lg text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleTranslate();
                }
              }}
            />
            <div className="flex items-center justify-between border-t border-border/30 pt-3">
              <span className="text-xs text-muted-foreground">
                {sourceText.length} characters
              </span>
              <div className="flex gap-2">
                <Button
                  onClick={handleTranslate}
                  disabled={!sourceText.trim() || isTranslating}
                  size="sm"
                  className="gap-2 rounded-lg"
                >
                  {isTranslating && (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  )}
                  Translate
                </Button>
                <Button
                  onClick={handleAnalyze}
                  disabled={!sourceText.trim() || isAnalyzing}
                  size="sm"
                  className="gap-2 rounded-lg"
                >
                  {isAnalyzing && (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  )}
                  Analyze
                </Button>
              </div>
            </div>
          </div>

          {/* Output */}
          <div className="relative bg-translator-output p-4">
            <AnimatePresence mode="wait">
              {isTranslating ? (
                <motion.div
                  key="loading"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex min-h-[180px] items-center justify-center"
                >
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                </motion.div>
              ) : translatedText ? (
                <motion.div
                  key="result"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="min-h-[180px]"
                >
                  <p className="font-body text-lg text-foreground">
                    {translatedText}
                  </p>
                </motion.div>
              ) : (
                <div className="flex min-h-[180px] items-center justify-center">
                  <p className="text-sm text-muted-foreground/50">
                    Translation will appear here
                  </p>
                </div>
              )}
            </AnimatePresence>

            {/* Sentiment/Emotion Analysis Result */}
            {analyzeResult && (
              <div className="mt-4 rounded-lg border border-border/50 bg-muted p-3">
                <div className="flex items-center justify-between gap-3">
                  <h4 className="text-sm font-semibold">Emotion Analysis</h4>
                  {!analyzeResult.error && (
                    <span className="text-[11px] text-muted-foreground">
                      Hugging Face
                    </span>
                  )}
                </div>

                {analyzeResult.error ? (
                  <p className="mt-2 text-xs text-destructive">
                    {analyzeResult.error}
                  </p>
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
                        {analyzeResult.fallback_reason.provider === "huggingface"
                          ? "Hugging Face was unavailable, so Gemini fallback was used."
                          : analyzeResult.fallback_reason.provider === "huggingface+gemini"
                            ? "Hugging Face and Gemini were unavailable, so local heuristics were used."
                            : analyzeResult.fallback_reason.provider === "gemini"
                              ? "Gemini was unavailable, so local heuristics were used."
                            : "A fallback model was used."}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}

            {variants && !isTranslating && (
              <div className="mt-3 flex items-center justify-between border-t border-border/30 pt-3 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-muted-foreground">Tone:</span>
                  <Button
                    variant={activeStyle === "neutral" ? "secondary" : "ghost"}
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => {
                      if (variants.neutral) {
                        setTranslatedText(variants.neutral);
                        setActiveStyle("neutral");
                      }
                    }}
                  >
                    Neutral
                  </Button>
                  <Button
                    variant={activeStyle === "formal" ? "secondary" : "ghost"}
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => {
                      if (variants.formal) {
                        setTranslatedText(variants.formal);
                        setActiveStyle("formal");
                      }
                    }}
                  >
                    Formal
                  </Button>
                  <Button
                    variant={activeStyle === "informal" ? "secondary" : "ghost"}
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => {
                      if (variants.informal) {
                        setTranslatedText(variants.informal);
                        setActiveStyle("informal");
                      }
                    }}
                  >
                    Informal
                  </Button>
                </div>

                {variants.synonyms && variants.synonyms.length > 0 && (
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button
                        variant="link"
                        size="sm"
                        className="h-7 px-0 text-xs text-primary"
                      >
                        More ways to say this
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent
                      className="max-w-sm space-y-2 text-xs"
                      side="bottom"
                      align="end"
                    >
                      <p className="text-muted-foreground">Synonyms</p>
                      <div className="flex flex-wrap gap-2">
                        {variants.synonyms.map((syn, idx) => (
                          <Button
                            key={`${syn}-${idx}`}
                            variant="outline"
                            size="sm"
                            className="h-7 px-2 text-xs"
                            onClick={() => {
                              setSourceText(syn);
                              setTranslatedText("");
                              setVariants(null);
                              setActiveStyle("neutral");
                            }}
                          >
                            {syn}
                          </Button>
                        ))}
                      </div>
                    </PopoverContent>
                  </Popover>
                )}
              </div>
            )}

            {translatedText && !isTranslating && (
              <div className="flex items-center justify-end gap-1 border-t border-border/30 pt-3">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-muted-foreground hover:text-foreground"
                  onClick={handleCopy}
                >
                  <Copy className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-muted-foreground hover:text-foreground"
                  onClick={handleSpeak}
                >
                  <Volume2 className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default TranslatorCard;
