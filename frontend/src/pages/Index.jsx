import { motion } from "framer-motion";
import { useState } from "react";
import { Sparkles } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import TranslatorCard from "@/components/TranslatorCard";
import ImageTranslator from "@/components/ImageTranslator";
import AuthDialog from "@/components/AuthDialog";
import { TARGET_LANGUAGES } from "@/lib/languages";

const Index = () => {
  const [authOpen, setAuthOpen] = useState(false);
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Navbar onAuthClick={() => setAuthOpen(true)} />

      <main className="container mx-auto px-4 py-12">
        {/* Hero */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-12 text-center"
        >
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/25 bg-accent/35 px-4 py-1.5 text-sm font-medium text-foreground">
            <Sparkles className="h-3.5 w-3.5 text-primary animate-pulse-glow" />
            Translate into 21+ languages
          </div>
          <h1 className="mb-3 font-display text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            Break language barriers
            <br />
            <span className="bg-[linear-gradient(135deg,_hsl(220_85%_55%),_hsl(280_80%_60%))] bg-clip-text text-transparent">
              instantly
            </span>
          </h1>
          <p className="mx-auto max-w-md text-muted-foreground">
            Fast and accurate translations across multiple languages. Type or
            paste - Get results in seconds.
          </p>
        </motion.div>

        {/* Translator */}
        <TranslatorCard onRequireAuth={() => setAuthOpen(true)} />

        {/* Image Translator */}
        <div className="mt-12">
          <ImageTranslator onRequireAuth={() => setAuthOpen(true)} />
        </div>

        {/* Supported languages preview */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="mt-16 text-center"
        >
          <p className="mb-4 text-sm font-medium text-muted-foreground">
            Supported Languages
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            {TARGET_LANGUAGES.map((lang) => (
              <span
                key={lang.code}
                className="rounded-full border border-border/50 bg-card px-3 py-1.5 text-sm text-foreground shadow-sm"
              >
                {lang.flag} {lang.name}
              </span>
            ))}
          </div>
        </motion.div>
      </main>
      <Footer />
      <AuthDialog open={authOpen} onOpenChange={setAuthOpen} />
    </div>
  );
};

export default Index;
