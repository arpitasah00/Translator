import { motion } from "framer-motion";
import { Shield } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

const Privacy = () => (
  <div className="flex min-h-screen flex-col bg-background">
    <Navbar />
    <main className="container mx-auto max-w-3xl flex-1 px-4 py-12">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent">
            <Shield className="h-5 w-5 text-accent-foreground" />
          </div>
          <h1 className="font-display text-2xl font-bold text-foreground">Privacy Policy</h1>
        </div>
        <div className="space-y-6 text-muted-foreground leading-relaxed">
          <section>
            <h2 className="mb-2 font-display text-lg font-semibold text-foreground">Data Collection</h2>
            <p>We only collect data necessary to provide translations. Your text inputs are processed in real-time and are not stored permanently unless you opt in to save translation history.</p>
          </section>
          <section>
            <h2 className="mb-2 font-display text-lg font-semibold text-foreground">Cookies</h2>
            <p>We use minimal cookies to remember your preferences such as theme and language selections. No third-party tracking cookies are used.</p>
          </section>
          <section>
            <h2 className="mb-2 font-display text-lg font-semibold text-foreground">Your Rights</h2>
            <p>You can request deletion of your account and all associated data at any time by contacting us. We respect your right to privacy and data ownership.</p>
          </section>
        </div>
      </motion.div>
    </main>
    <Footer />
  </div>
);

export default Privacy;
