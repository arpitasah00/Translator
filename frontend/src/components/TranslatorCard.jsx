import { ArrowRightLeft, Copy, Volume2, Loader2 } from "lucide-react";
import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import LanguageSelector from "./LanguageSelector";
import { toast } from "sonner";

const MOCK_TRANSLATIONS = {
  en: { hello: "hello", "how are you": "how are you", "good morning": "good morning", "thank you": "thank you", world: "world" },
  es: { hello: "hola", "how are you": "¿cómo estás?", "good morning": "buenos días", "thank you": "gracias", world: "mundo" },
  fr: { hello: "bonjour", "how are you": "comment allez-vous?", "good morning": "bonjour", "thank you": "merci", world: "monde" },
  de: { hello: "hallo", "how are you": "wie geht es Ihnen?", "good morning": "guten Morgen", "thank you": "danke", world: "Welt" },
  ja: { hello: "こんにちは", "how are you": "お元気ですか？", "good morning": "おはようございます", "thank you": "ありがとう", world: "世界" },
  zh: { hello: "你好", "how are you": "你好吗？", "good morning": "早上好", "thank you": "谢谢", world: "世界" },
  ko: { hello: "안녕하세요", "how are you": "어떻게 지내세요?", "good morning": "좋은 아침", "thank you": "감사합니다", world: "세계" },
  ar: { hello: "مرحبا", "how are you": "كيف حالك؟", "good morning": "صباح الخير", "thank you": "شكرا لك", world: "عالم" },
  hi: { hello: "नमस्ते", "how are you": "आप कैसे हैं?", "good morning": "सुप्रभात", "thank you": "धन्यवाद", world: "दुनिया" },
  ru: { hello: "привет", "how are you": "как дела?", "good morning": "доброе утро", "thank you": "спасибо", world: "мир" },
};

function mockTranslate(text, targetLang) {
  const lower = text.toLowerCase().trim();
  const translations = MOCK_TRANSLATIONS[targetLang];
  if (translations && translations[lower]) return translations[lower];
  return text;
}

const TranslatorCard = () => {
  const [sourceLang, setSourceLang] = useState("auto");
  const [targetLang, setTargetLang] = useState("es");
  const [sourceText, setSourceText] = useState("");
  const [translatedText, setTranslatedText] = useState("");
  const [isTranslating, setIsTranslating] = useState(false);

const handleTranslate = useCallback(async () => {
  if (!sourceText.trim()) return;

  setIsTranslating(true);

  try {
    const res = await fetch("http://127.0.0.1:5000/translate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        message: sourceText,
        target_language: targetLang
      })
    });

    const data = await res.json();
    setTranslatedText(data.translated);
  } catch (error) {
    console.error(error);
    toast.error("Translation failed!");
  }

  setIsTranslating(false);
}, [sourceText, targetLang]);

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
      en: "en-US", es: "es-ES", fr: "fr-FR", de: "de-DE", ja: "ja-JP",
      zh: "zh-CN", ko: "ko-KR", ar: "ar-SA", hi: "hi-IN", ru: "ru-RU",
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
        <div className="flex items-center gap-2 border-b border-border/40 bg-muted/30 px-4 py-3">
          <LanguageSelector value={sourceLang} onChange={setSourceLang} showDetect />
          <Button
            variant="ghost"
            size="icon"
            onClick={handleSwap}
            disabled={sourceLang === "auto"}
            className="h-8 w-8 shrink-0 rounded-full text-muted-foreground hover:bg-accent hover:text-primary"
          >
            <ArrowRightLeft className="h-4 w-4" />
          </Button>
          <LanguageSelector value={targetLang} onChange={setTargetLang} />
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
              <Button
                onClick={handleTranslate}
                disabled={!sourceText.trim() || isTranslating}
                size="sm"
                className="gap-2 rounded-lg"
              >
                {isTranslating && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Translate
              </Button>
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
                  <p className="font-body text-lg text-foreground">{translatedText}</p>
                </motion.div>
              ) : (
                <div className="flex min-h-[180px] items-center justify-center">
                  <p className="text-sm text-muted-foreground/50">Translation will appear here</p>
                </div>
              )}
            </AnimatePresence>

            {translatedText && !isTranslating && (
              <div className="flex items-center justify-end gap-1 border-t border-border/30 pt-3">
                <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground" onClick={handleCopy}>
                  <Copy className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground" onClick={handleSpeak}>
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
