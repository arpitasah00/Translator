import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Mail, Lock, ArrowLeft, Eye, EyeOff } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSlot,
} from "@/components/ui/input-otp";
import { toast } from "sonner";
import { api } from "@/lib/api";

const AuthForm = ({ showBackLink = true, onBack, onCompleted }) => {
  const navigate = useNavigate();
  const [isSignUp, setIsSignUp] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isVerifyingOtp, setIsVerifyingOtp] = useState(false);
  const [otp, setOtp] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [otpSecondsLeft, setOtpSecondsLeft] = useState(600); // 10 minutes

  // Start / reset OTP timer when modal opens
  useEffect(() => {
    if (!isVerifyingOtp) return;

    setOtpSecondsLeft(600);
    const interval = setInterval(() => {
      setOtpSecondsLeft((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [isVerifyingOtp]);

  const handleAuthSuccess = (data) => {
    if (data?.token) {
      localStorage.setItem("authToken", data.token);
    }
    localStorage.setItem("isLoggedIn", "true");
    if (typeof window !== "undefined") {
      window.dispatchEvent(new Event("auth-changed"));
    }
    if (onCompleted) {
      onCompleted();
    }
    navigate("/", { replace: true });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isLoading) return;

    if (!email || (!otp && !password)) return;

    setIsLoading(true);

    try {
      // Step 3: Verify OTP (in separate dialog)
      if (isVerifyingOtp) {
        const res = await api.post("/auth/verify-otp", { email, otp });
        const data = res.data;
        if (res.status !== 200) {
          toast.error(data?.error || "OTP verification failed");
          return;
        }

        toast.success("OTP verified. You can now sign in.");
        setIsVerifyingOtp(false);
        setOtp("");
        setIsSignUp(false);
        handleAuthSuccess(data);
        return;
      }

      // Step 1: Signup
      if (isSignUp) {
        const res = await api.post("/auth/signup", { email, password });
        const data = res.data;

        if (res.status >= 400) {
          toast.error(data?.error || "Signup failed");
          return;
        }

        if (data?.requires_otp) {
          toast.success("OTP sent to your email. Please verify.");
          setIsVerifyingOtp(true);
          setOtp("");
        } else {
          toast.success("Signup successful.");
          handleAuthSuccess(data);
        }

        return;
      }

      // Step 2: Login
      const res = await api.post("/auth/login", { email, password });
      const data = res.data;

      if (res.status >= 400) {
        toast.error(data?.error || "Login failed");
        return;
      }

      if (data?.requires_otp) {
        toast.message("OTP sent. Please verify to complete login.");
        setIsVerifyingOtp(true);
        setOtp("");
      } else {
        toast.success("Logged in successfully.");
        handleAuthSuccess(data);
      }
    } catch (error) {
      console.error("Auth error", error);
      toast.error("Something went wrong. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  // Google Sign-In integration
  useEffect(() => {
    if (typeof window === "undefined") return;
    const google = window.google;
    if (!google || !google.accounts || !google.accounts.id) return;

    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
    if (!clientId) return;

    google.accounts.id.initialize({
      client_id: clientId,
      callback: async (response) => {
        try {
          const res = await api.post("/auth/google", {
            id_token: response.credential,
          });
          const data = res.data;
          if (res.status >= 400 || !data?.token) {
            toast.error(data?.error || "Google login failed");
            return;
          }
          toast.success("Logged in with Google");
          handleAuthSuccess(data);
        } catch (err) {
          console.error("Google login error", err);
          toast.error("Google login failed");
        }
      },
    });

    const btn = document.getElementById("google-signin-button");
    if (btn) {
      google.accounts.id.renderButton(btn, {
        type: "standard",
        shape: "rectangular",
        theme: "outline",
        text: "continue_with",
        size: "large",
        width: 320,
      });
    }
  }, []);

  return (
    <div>
      {!isVerifyingOtp && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-md"
        >
          {showBackLink && (
            <button
              type="button"
              onClick={() => {
                if (onBack) {
                  onBack();
                } else {
                  navigate("/");
                }
              }}
              className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to translator
            </button>
          )}

          <div className="overflow-hidden rounded-2xl border border-border/60 bg-card shadow-lg">
            {/* Header */}
            <div className="border-b border-border/40 bg-muted/30 px-6 py-8 text-center">
              <div className="mx-auto mb-4 flex items-center justify-center">
                <img
                  src="/logo.png"
                  alt="MultiLingo logo"
                  className="auth-logo w-auto"
                />
              </div>
              <h1 className="font-display text-2xl font-bold text-foreground">
                {isSignUp ? "Create account" : "Welcome back"}
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {isSignUp
                  ? "Sign up to save your translation history"
                  : "Sign in to access your translations"}
              </p>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4 p-6">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="pl-10"
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Password
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pl-10 pr-10"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
              <Button
                type="submit"
                className="w-full"
                size="lg"
                disabled={isLoading}
              >
                {isLoading
                  ? "Please wait..."
                  : isSignUp
                  ? "Create Account"
                  : "Sign In"}
              </Button>

              <div className="relative my-4">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-border" />
                </div>
                <div className="relative flex justify-center">
                  <span className="bg-card px-3 text-xs text-muted-foreground">
                    or continue with
                  </span>
                </div>
              </div>

              <div id="google-signin-button" className="w-full flex justify-center" />

              <div className="border-t border-border/40 pt-4 text-center text-sm text-muted-foreground">
                {isSignUp ? "Already have an account?" : "Don't have an account?"}{" "}
                <button
                  type="button"
                  onClick={() => setIsSignUp(!isSignUp)}
                  className="font-medium text-primary hover:underline"
                >
                  {isSignUp ? "Sign in" : "Sign up"}
                </button>
              </div>
            </form>
          </div>
        </motion.div>
      )}

      {/* OTP Verification Dialog */}
      <Dialog
        open={isVerifyingOtp}
        onOpenChange={(open) => !open && setIsVerifyingOtp(false)}
      >
        <DialogContent className="max-w-md rounded-2xl">
          <DialogHeader className="text-center">
            <DialogTitle className="text-xl font-semibold">
              OTP Verification
            </DialogTitle>
            <DialogDescription>
              Enter the 6 digit verification code received on your email.
            </DialogDescription>
          </DialogHeader>

          <div className="mt-4 flex items-center justify-between text-sm">
            <span className="font-medium text-foreground">
              Verification code
            </span>
            <div className="flex items-center gap-2 text-xs font-medium">
              <span className="text-primary">
                {String(Math.floor(otpSecondsLeft / 60)).padStart(1, "0")}:
                {String(otpSecondsLeft % 60).padStart(2, "0")}
              </span>
              <button
                type="button"
                disabled={otpSecondsLeft === 0 || isLoading}
                onClick={async () => {
                  try {
                    setIsLoading(true);
                    // Reuse login/signup to resend OTP depending on current mode
                    const endpoint = isSignUp ? "/auth/signup" : "/auth/login";
                    const res = await api.post(endpoint, { email, password });
                    const data = res.data;
                    if (res.status >= 400) {
                      toast.error(data?.error || "Failed to resend OTP");
                      return;
                    }
                    toast.success("New OTP sent to your email.");
                    setOtp("");
                    setOtpSecondsLeft(600);
                  } catch (err) {
                    console.error("Resend OTP error", err);
                    toast.error("Failed to resend OTP");
                  } finally {
                    setIsLoading(false);
                  }
                }}
                className="text-xs font-semibold text-primary hover:underline disabled:cursor-not-allowed disabled:opacity-60"
              >
                Resend OTP
              </button>
            </div>
          </div>

          <div className="mt-6 flex justify-center">
            <InputOTP
              maxLength={6}
              value={otp}
              onChange={setOtp}
              containerClassName="justify-center"
            >
              <InputOTPGroup>
                {[0, 1, 2, 3, 4, 5].map((index) => (
                  <InputOTPSlot key={index} index={index} />
                ))}
              </InputOTPGroup>
            </InputOTP>
          </div>

          <Button
            type="button"
            className="mt-6 w-full"
            size="lg"
            disabled={isLoading || otp.length !== 6}
            onClick={handleSubmit}
          >
            {isLoading ? "Verifying..." : "Verify"}
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AuthForm;
