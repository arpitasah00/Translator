import { Check, ChevronDown, Search } from "lucide-react";
import { useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const LANGUAGES = [
  { code: "auto", name: "Detect Language", flag: "🌐" },
  { code: "en", name: "English", flag: "🇬🇧" },
  { code: "es", name: "Spanish", flag: "🇪🇸" },
  { code: "fr", name: "French", flag: "🇫🇷" },
  { code: "de", name: "German", flag: "🇩🇪" },
  { code: "it", name: "Italian", flag: "🇮🇹" },
  { code: "pt", name: "Portuguese", flag: "🇧🇷" },
  { code: "zh", name: "Chinese", flag: "🇨🇳" },
  { code: "ja", name: "Japanese", flag: "🇯🇵" },
  { code: "ko", name: "Korean", flag: "🇰🇷" },
  { code: "ar", name: "Arabic", flag: "🇸🇦" },
  { code: "hi", name: "Hindi", flag: "🇮🇳" },
  { code: "ru", name: "Russian", flag: "🇷🇺" },
  { code: "tr", name: "Turkish", flag: "🇹🇷" },
  { code: "nl", name: "Dutch", flag: "🇳🇱" },
  { code: "sv", name: "Swedish", flag: "🇸🇪" },
];

const LanguageSelector = ({ value, onChange, showDetect = false }) => {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const languages = showDetect ? LANGUAGES : LANGUAGES.filter((l) => l.code !== "auto");
  const filtered = languages.filter((l) => l.name.toLowerCase().includes(search.toLowerCase()));
  const selected = LANGUAGES.find((l) => l.code === value);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          className="h-10 w-full justify-between gap-2 rounded-lg border border-border/50 bg-card px-3 font-body text-sm font-medium text-foreground hover:bg-accent"
        >
          <span className="text-base">{selected?.flag}</span>
          <span className="flex-1 truncate text-left">{selected?.name}</span>
          <ChevronDown className="ml-1 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-2" align="start">
        <div className="relative mb-2">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Search language..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8 pl-8 text-sm"
          />
        </div>
        <div className="max-h-56 overflow-y-auto">
          {filtered.map((lang) => (
            <button
              key={lang.code}
              onClick={() => {
                onChange(lang.code);
                setOpen(false);
                setSearch("");
              }}
              className="flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-sm text-foreground hover:bg-accent"
            >
              <span>{lang.flag}</span>
              <span className="flex-1 text-left">{lang.name}</span>
              {value === lang.code && <Check className="h-3.5 w-3.5 text-primary" />}
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
};

export { LANGUAGES };
export default LanguageSelector;
