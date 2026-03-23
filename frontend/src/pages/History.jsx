import { motion } from "framer-motion";
import { Clock, ArrowRight, Trash2 } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";

const MOCK_HISTORY = [
  { id: 1, source: "Hello", target: "Hola", from: "English", to: "Spanish", time: "2 min ago" },
  { id: 2, source: "Good morning", target: "Bonjour", from: "English", to: "French", time: "15 min ago" },
  { id: 3, source: "Thank you", target: "ありがとう", from: "English", to: "Japanese", time: "1 hour ago" },
  { id: 4, source: "How are you?", target: "Wie geht es Ihnen?", from: "English", to: "German", time: "3 hours ago" },
];

const History = () => {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Navbar />
      <main className="container mx-auto max-w-3xl px-4 py-12">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <div className="mb-8 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent">
              <Clock className="h-5 w-5 text-accent-foreground" />
            </div>
            <div>
              <h1 className="font-display text-2xl font-bold text-foreground">Translation History</h1>
              <p className="text-sm text-muted-foreground">Your recent translations</p>
            </div>
          </div>

          <div className="space-y-3">
            {MOCK_HISTORY.map((item, i) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08 }}
                className="group flex items-center justify-between rounded-xl border border-border/50 bg-card p-4 shadow-sm transition-shadow hover:shadow-md"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{item.from}</span>
                    <ArrowRight className="h-3 w-3" />
                    <span>{item.to}</span>
                    <span className="ml-2">{item.time}</span>
                  </div>
                  <div className="mt-1.5 flex items-baseline gap-3">
                    <p className="text-foreground">{item.source}</p>
                    <span className="text-muted-foreground">→</span>
                    <p className="font-medium text-primary">{item.target}</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </motion.div>
            ))}
          </div>

          <p className="mt-8 text-center text-sm text-muted-foreground">
            Sign in to save and sync your translation history across devices.
          </p>
        </motion.div>
      </main>
      <Footer />
    </div>
  );
};

export default History;
