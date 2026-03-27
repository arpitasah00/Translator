import { Languages, LogIn, History } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import ThemeToggle from "./ThemeToggle";

const Navbar = () => {
  const location = useLocation();

  return (
    <motion.nav
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="sticky top-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-xl"
    >
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        <Link to="/" className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary">
            <Languages className="h-5 w-5 text-primary-foreground" />
          </div>
          <span className="font-display text-xl font-bold tracking-tight text-foreground">
            LinguaFlow
          </span>
        </Link>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          {location.pathname !== "/history" && (
            <Button variant="ghost" size="sm" asChild>
              <Link to="/history" className="gap-2">
                <History className="h-4 w-4" />
                <span className="hidden sm:inline">History</span>
              </Link>
            </Button>
          )}
          <Button variant="default" size="sm" asChild>
            <Link to="/login" className="gap-2">
              <LogIn className="h-4 w-4" />
              <span>Sign In</span>
            </Link>
          </Button>
        </div>
      </div>
    </motion.nav>
  );
};

export default Navbar;
