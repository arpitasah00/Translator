import { motion } from "framer-motion";
import { X } from "lucide-react";
import AuthForm from "@/components/AuthForm";

const AuthDialog = ({ open, onOpenChange }) => {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/70 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.25 }}
        className="w-full max-w-md"
      >
        <div className="mb-4 flex justify-end">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-muted text-muted-foreground hover:bg-muted/80"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="relative mx-auto w-full max-w-md overflow-hidden rounded-3xl border border-border/60 bg-gradient-to-b from-background/95 via-background/98 to-background/95 shadow-2xl">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.08),_transparent_55%),radial-gradient(circle_at_bottom,_rgba(56,189,248,0.08),_transparent_55%)]" />
          <div className="relative p-1">
            <AuthForm
              showBackLink={false}
              onCompleted={() => onOpenChange(false)}
            />
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default AuthDialog;
