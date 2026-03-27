import { motion } from "framer-motion";
import { Users } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

const About = () => (
  <div className="flex min-h-screen flex-col bg-background">
    <Navbar />
    <main className="container mx-auto max-w-3xl flex-1 px-4 py-12">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent">
            <Users className="h-5 w-5 text-accent-foreground" />
          </div>
          <h1 className="font-display text-2xl font-bold text-foreground">About Us</h1>
        </div>
        <div className="space-y-4 text-muted-foreground leading-relaxed">
          <p>
            LinguaFlow is built with one mission: to break language barriers and make communication seamless across the globe.
          </p>
          <p>
            Our team of linguists and engineers work together to deliver fast, accurate translations across 15+ languages — empowering individuals, businesses, and communities to connect without limits.
          </p>
          <p>
            Whether you're traveling, studying, or collaborating internationally, LinguaFlow is your go-to translation companion.
          </p>
        </div>
      </motion.div>
    </main>
    <Footer />
  </div>
);

export default About;
