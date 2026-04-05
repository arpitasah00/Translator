// ALL LANGUAGES (Text Translation)
export const LANGUAGES = [
  { code: "auto", name: "Detect Language", flag: "🌐" },

  { code: "en", name: "English", flag: "🇬🇧" },
  { code: "es", name: "Spanish", flag: "🇪🇸" },
  { code: "fr", name: "French", flag: "🇫🇷" },
  { code: "de", name: "German", flag: "🇩🇪" },
  { code: "it", name: "Italian", flag: "🇮🇹" },
  { code: "pt", name: "Portuguese", flag: "🇵🇹" },

  { code: "zh", name: "Chinese", flag: "🇨🇳" },
  { code: "ja", name: "Japanese", flag: "🇯🇵" },
  { code: "ko", name: "Korean", flag: "🇰🇷" },

  { code: "ar", name: "Arabic", flag: "🇸🇦" },
  { code: "hi", name: "Hindi", flag: "🇮🇳" },
  { code: "or", name: "Odia", flag: "🇮🇳" },
  { code: "bn", name: "Bengali", flag: "🇧🇩" },
  { code: "sa", name: "Sanskrit", flag: "🇮🇳" },
  { code: "te", name: "Telugu", flag: "🇮🇳" },
  { code: "ta", name: "Tamil", flag: "🇮🇳" },
  { code: "kn", name: "Kannada", flag: "🇮🇳" },

  { code: "ru", name: "Russian", flag: "🇷🇺" },
  { code: "tr", name: "Turkish", flag: "🇹🇷" },
  { code: "nl", name: "Dutch", flag: "🇳🇱" },
  { code: "sv", name: "Swedish", flag: "🇸🇪" },
];

export const TARGET_LANGUAGES = LANGUAGES.filter(
  (lang) => lang.code !== "auto"
);

export const LANGUAGE_CODE_SET = new Set(
  LANGUAGES.map((lang) => lang.code).filter((code) => code !== "auto")
);

export const getLanguageByCode = (code) =>
  LANGUAGES.find((lang) => lang.code === code);

export const detectSupportedLanguage = (text) => {
  const sample = (text || "").trim();
  if (!sample) return null;

  const scriptChecks = [
    ["ar", (ch) => ch >= "\u0600" && ch <= "\u06FF"],
    ["ru", (ch) => ch >= "\u0400" && ch <= "\u04FF"],
    ["bn", (ch) => ch >= "\u0980" && ch <= "\u09FF"],
    ["hi", (ch) => ch >= "\u0900" && ch <= "\u097F"],
    ["or", (ch) => ch >= "\u0B00" && ch <= "\u0B7F"],
    ["ta", (ch) => ch >= "\u0B80" && ch <= "\u0BFF"],
    ["te", (ch) => ch >= "\u0C00" && ch <= "\u0C7F"],
    ["kn", (ch) => ch >= "\u0C80" && ch <= "\u0CFF"],
    ["zh", (ch) => ch >= "\u4E00" && ch <= "\u9FFF"],
    ["ja", (ch) =>
      (ch >= "\u3040" && ch <= "\u309F") ||
      (ch >= "\u30A0" && ch <= "\u30FF")],
    ["ko", (ch) => ch >= "\uAC00" && ch <= "\uD7AF"],
  ];

  let dominantScript = null;
  let dominantScore = 0;
  for (const [code, matcher] of scriptChecks) {
    const score = [...sample].reduce(
      (total, ch) => total + (matcher(ch) ? 1 : 0),
      0,
    );
    if (score > dominantScore) {
      dominantScript = code;
      dominantScore = score;
    }
  }

  if (dominantScript && dominantScore > 0) {
    return dominantScript;
  }

  const lowered = ` ${sample.toLowerCase()} `;
  const keywordMap = {
    sv: [" och ", " det ", " att ", " inte ", " jag "],
    nl: [" de ", " het ", " een ", " niet ", " ik "],
    tr: [" ve ", " bir ", " bu ", " için ", " değil "],
    pt: [" não ", " você ", " para ", " uma ", " com "],
    es: [" que ", " los ", " las ", " una ", " estoy ", " hola "],
    fr: [" je ", " pas ", " une ", " est ", " les ", " bonjour "],
    de: [" und ", " ist ", " nicht ", " ich ", " das ", " bitte "],
    it: [" che ", " non ", " una ", " per ", " sono ", " ciao "],
    en: [" the ", " and ", " are ", " you ", " this ", " please "],
  };

  let bestCode = null;
  let bestScore = 0;
  for (const [code, keywords] of Object.entries(keywordMap)) {
    const score = keywords.reduce(
      (total, keyword) => total + (lowered.includes(keyword) ? 1 : 0),
      0,
    );
    if (score > bestScore) {
      bestCode = code;
      bestScore = score;
    }
  }

  if (bestScore > 0) {
    return bestCode;
  }

  if (/^[\p{Script=Latin}\p{P}\p{Z}\p{N}]+$/u.test(sample)) {
    return "en";
  }

  return null;
};

export const OCR_SAFE_LANGUAGES = [
  { code: "en", name: "English", flag: "🇬🇧" },
  { code: "es", name: "Spanish", flag: "🇪🇸" },
  { code: "ar", name: "Arabic", flag: "🇸🇦" },
  { code: "hi", name: "Hindi", flag: "🇮🇳" },
  { code: "or", name: "Odia", flag: "🇮🇳" },
  { code: "bn", name: "Bengali", flag: "🇧🇩" },
  { code: "fr", name: "French", flag: "🇫🇷" },
  { code: "de", name: "German", flag: "🇩🇪" },
  { code: "it", name: "Italian", flag: "🇮🇹" },
  { code: "pt", name: "Portuguese", flag: "🇵🇹" },
  { code: "zh", name: "Chinese", flag: "🇨🇳" },
  { code: "ja", name: "Japanese", flag: "🇯🇵" },
  { code: "ko", name: "Korean", flag: "🇰🇷" },
  { code: "ru", name: "Russian", flag: "🇷🇺" },
  { code: "tr", name: "Turkish", flag: "🇹🇷" },
  { code: "nl", name: "Dutch", flag: "🇳🇱" },
  { code: "ta", name: "Tamil", flag: "🇮🇳" },
  { code: "te", name: "Telugu", flag: "🇮🇳" },
  { code: "kn", name: "Kannada", flag: "🇮🇳" },
];
