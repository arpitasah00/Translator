import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Clock, ArrowRight, Copy, Star, StarOff, Trash2 } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/use-toast";
import { api } from "@/lib/api";

const History = () => {
  const { toast } = useToast();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const res = await api.get("/history");
        if (!isMounted) return;
        setItems(res.data.items || []);
      } catch (err) {
        if (!isMounted) return;
        if (err?.response?.status === 401) {
          setError("Please sign in to view your history.");
        } else {
          setError("Failed to load history. Please try again.");
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    load();
    return () => {
      isMounted = false;
    };
  }, []);

  const filteredItems = useMemo(() => {
    const q = search.toLowerCase().trim();
    return items.filter((item) => {
      const matchesSearch =
        !q ||
        (item.original || "").toLowerCase().includes(q) ||
        (item.translated || "").toLowerCase().includes(q);
      const matchesFavorite = !showFavoritesOnly || item.is_favorite;
      return matchesSearch && matchesFavorite;
    });
  }, [items, search, showFavoritesOnly]);

  const formatTimeAgo = (isoString) => {
    if (!isoString) return "";
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return "";
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHours = Math.floor(diffMin / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin} min ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
    if (diffDays === 1) return "yesterday";
    if (diffDays < 7) return `${diffDays} days ago`;
    return date.toLocaleDateString();
  };

  const handleToggleFavorite = async (item) => {
    const next = !item.is_favorite;
    setItems((prev) => prev.map((x) => (x.id === item.id ? { ...x, is_favorite: next } : x)));
    try {
      await api.post(`/history/${item.id}/favorite`, { is_favorite: next });
    } catch (err) {
      setItems((prev) =>
        prev.map((x) => (x.id === item.id ? { ...x, is_favorite: item.is_favorite } : x))
      );
      toast({
        title: "Could not update favorite",
        variant: "destructive",
      });
    }
  };

  const handleCopy = async (text) => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      toast({ title: "Copied to clipboard" });
    } catch {
      toast({ title: "Copy failed", variant: "destructive" });
    }
  };

  const handleDelete = async (item) => {
    const id = item.id;
    const previous = items;
    setItems((prev) => prev.filter((x) => x.id !== id));
    try {
      await api.delete(`/history/${id}`);
      toast({ title: "Deleted from history" });
    } catch (err) {
      setItems(previous);
      toast({ title: "Could not delete history", variant: "destructive" });
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Navbar />
      <main className="container mx-auto max-w-3xl px-4 py-12">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <div className="mb-8 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent">
              <Clock className="h-5 w-5 text-accent-foreground" />
            </div>
            <div className="flex flex-1 items-center justify-between gap-3">
              <div>
                <h1 className="font-display text-2xl font-bold text-foreground">
                  Translation History
                </h1>
                <p className="text-sm text-muted-foreground">Your recent translations</p>
              </div>
              <div className="flex items-center gap-3">
                <Input
                  placeholder="Search in history..."
                  className="h-9 max-w-xs text-sm"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Switch
                    id="favorites-only"
                    checked={showFavoritesOnly}
                    onCheckedChange={setShowFavoritesOnly}
                  />
                  <label htmlFor="favorites-only" className="cursor-pointer">
                    Favorites only
                  </label>
                </div>
              </div>
            </div>
          </div>

          {loading && (
            <p className="text-sm text-muted-foreground">Loading history...</p>
          )}

          {!loading && error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <div className="mt-2 max-h-[420px] space-y-3 overflow-y-auto pr-1">
            {!loading && !error && filteredItems.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No translations yet. Start translating to see history here.
              </p>
            )}

            {filteredItems.map((item, i) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="group flex items-center justify-between rounded-xl border border-border/50 bg-card p-4 shadow-sm transition-shadow hover:shadow-md"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>Auto-detect</span>
                    <ArrowRight className="h-3 w-3" />
                    <span>{item.target_language}</span>
                    {item.created_at && (
                      <span className="ml-2">{formatTimeAgo(item.created_at)}</span>
                    )}
                  </div>
                  <div className="mt-1.5 flex items-baseline gap-3">
                    <p className="text-foreground">{item.original}</p>
                    <span className="text-muted-foreground">→</span>
                    <p className="font-medium text-primary">{item.translated}</p>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
                    onClick={() => handleCopy(item.translated)}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-yellow-500 opacity-0 transition-opacity group-hover:opacity-100"
                    onClick={() => handleToggleFavorite(item)}
                  >
                    {item.is_favorite ? (
                      <Star className="h-4 w-4" />
                    ) : (
                      <StarOff className="h-4 w-4" />
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive opacity-0 transition-opacity group-hover:opacity-100"
                    onClick={() => handleDelete(item)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </motion.div>
            ))}
          </div>

          {!error && (
            <p className="mt-8 text-center text-sm text-muted-foreground">
              Your translations are saved to your account so you can quickly find, copy, and favorite them later.
            </p>
          )}
        </motion.div>
      </main>
      <Footer />
    </div>
  );
};

export default History;
