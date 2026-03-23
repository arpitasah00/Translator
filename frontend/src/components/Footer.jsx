import { Languages } from "lucide-react";
import { Link } from "react-router-dom";

const Footer = () => {
  return (
    <footer className="mt-auto border-t border-border/50 bg-muted/30">
      <div className="container mx-auto flex flex-col items-center gap-6 px-4 py-10 sm:flex-row sm:justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <Languages className="h-4 w-4 text-primary-foreground" />
          </div>
          <span className="font-display text-lg font-bold tracking-tight text-foreground">
            LinguaFlow
          </span>
        </div>

        <nav className="flex gap-6 text-sm text-muted-foreground">
          <Link to="/about" className="transition-colors hover:text-foreground">About Us</Link>
          <Link to="/privacy" className="transition-colors hover:text-foreground">Privacy Policy</Link>
          <Link to="/contact" className="transition-colors hover:text-foreground">Contact Us</Link>
        </nav>

        <p className="text-xs text-muted-foreground">
          © {new Date().getFullYear()} LinguaFlow. All rights reserved.
        </p>
      </div>
    </footer>
  );
};

export default Footer;
