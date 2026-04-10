"use client";

import Link from "next/link";
import { Leaf } from "lucide-react";

const footerLinks = {
  features: [
    { label: "Crop Management", href: "#features" },
    { label: "Pest Control", href: "#features" },
    { label: "Weather Insights", href: "#features" },
    { label: "Government Schemes", href: "#features" },
  ],
  resources: [
    { label: "How It Works", href: "#how-it-works" },
    { label: "Benefits", href: "#benefits" },
    { label: "FAQ", href: "#" },
    { label: "Support", href: "#" },
  ],
  languages: [
    { label: "Hindi", href: "#" },
    { label: "Marathi", href: "#" },
    { label: "Tamil", href: "#" },
    { label: "Telugu", href: "#" },
  ],
};

export function FooterSection() {
  return (
    <footer className="bg-background">
      {/* Main Footer Content */}
      <div className="border-t border-border px-6 py-16 md:px-12 md:py-20 lg:px-20">
        <div className="grid grid-cols-2 gap-12 md:grid-cols-4 lg:grid-cols-5">
          {/* Brand */}
          <div className="col-span-2 md:col-span-1 lg:col-span-2">
            <Link href="/" className="inline-flex items-center gap-2 text-lg font-semibold text-primary">
              <Leaf className="h-5 w-5" />
              VedaKrishi AI
            </Link>
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted-foreground">
              Your AI-powered farming companion. Get instant answers on crop management, pest control, and government schemes in your local language.
            </p>
            <Link 
              href="/chat"
              className="mt-6 inline-flex items-center gap-2 bg-primary text-primary-foreground px-5 py-2.5 rounded-full text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              Start Chatting
            </Link>
          </div>

          {/* Features */}
          <div>
            <h4 className="mb-4 text-sm font-medium text-foreground">Features</h4>
            <ul className="space-y-3">
              {footerLinks.features.map((link) => (
                <li key={link.label}>
                  <Link
                    href={link.href}
                    className="text-sm text-muted-foreground transition-colors hover:text-primary"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h4 className="mb-4 text-sm font-medium text-foreground">Resources</h4>
            <ul className="space-y-3">
              {footerLinks.resources.map((link) => (
                <li key={link.label}>
                  <Link
                    href={link.href}
                    className="text-sm text-muted-foreground transition-colors hover:text-primary"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Languages */}
          <div>
            <h4 className="mb-4 text-sm font-medium text-foreground">Languages</h4>
            <ul className="space-y-3">
              {footerLinks.languages.map((link) => (
                <li key={link.label}>
                  <Link
                    href={link.href}
                    className="text-sm text-muted-foreground transition-colors hover:text-primary"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Bottom Bar */}
      <div className="border-t border-border px-6 py-6 md:px-12 lg:px-20">
        <div className="flex flex-col items-center justify-between gap-4 md:flex-row">
          <p className="text-xs text-muted-foreground">
            2026 VedaKrishi AI. Empowering farmers with knowledge.
          </p>

          {/* Social Links */}
          <div className="flex items-center gap-4">
            <Link
              href="#"
              className="text-xs text-muted-foreground transition-colors hover:text-primary"
            >
              WhatsApp
            </Link>
            <Link
              href="#"
              className="text-xs text-muted-foreground transition-colors hover:text-primary"
            >
              YouTube
            </Link>
            <Link
              href="#"
              className="text-xs text-muted-foreground transition-colors hover:text-primary"
            >
              Telegram
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
