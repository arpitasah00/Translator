import { useEffect, useState } from "react";
import { LogIn, History } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import ThemeToggle from "./ThemeToggle";

const Navbar = ({ onAuthClick }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const [isLoggedIn, setIsLoggedIn] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("isLoggedIn") === "true";
  });

  useEffect(() => {
    if (typeof window === "undefined") return;

    const syncAuth = () => {
      setIsLoggedIn(localStorage.getItem("isLoggedIn") === "true");
    };

    const handleStorage = (event) => {
      if (event.key === "isLoggedIn") {
        syncAuth();
      }
    };

    window.addEventListener("storage", handleStorage);
    window.addEventListener("auth-changed", syncAuth);

    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("auth-changed", syncAuth);
    };
  }, []);

  return (
    <motion.nav
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="sticky top-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-xl"
    >
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        <Link to="/" className="flex items-center gap-2.5">
          <img
            src="/logo.png"
            alt="MultiLingo logo"
            className="navbar-logo w-auto"
          />
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
          {isLoggedIn ? (
            <Button
              variant="default"
              size="sm"
              onClick={async () => {
                try {
                  await api.post("/auth/logout");
                } catch (e) {
                  // ignore backend logout errors for now
                } finally {
                  localStorage.removeItem("authToken");
                  localStorage.removeItem("isLoggedIn");
                  setIsLoggedIn(false);
                  navigate("/");
                }
              }}
            >
              <span>Logout</span>
            </Button>
          ) : (
            <Button
              variant="default"
              size="sm"
              className="gap-2"
              onClick={() => {
                if (onAuthClick) {
                  onAuthClick();
                } else {
                  navigate("/");
                }
              }}
            >
              <LogIn className="h-4 w-4" />
              <span>Sign In</span>
            </Button>
          )}
        </div>
      </div>
    </motion.nav>
  );
};

export default Navbar;
